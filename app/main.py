"""
app/main.py
------------
FastAPI application entrypoint. Middleware, startup events, and the
root health-check live here. This is what `uvicorn` actually runs.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine, init_db
from app.core.exceptions import (
    BhuDrishtiError,
    DatasetValidationError,
    ExportValidationError,
    FeatureExtractionError,
    JobExecutionError,
    NakshaIntegrationError,
    RasterValidationError,
    ReconciliationError,
    TopologyValidationError,
)
from app.api.v1.router import api_router
from app.api.v2.router import api_router as api_v2_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bhudrishti.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI startup/shutdown pattern (replaces the old
    @app.on_event("startup") — that's deprecated). Code before `yield`
    runs on startup, code after runs on shutdown.
    """
    logger.info(f"Starting {settings.APP_NAME}...")
    try:
        init_db()
    except SQLAlchemyError as exc:
        logger.critical(
            "Database startup check failed. Configure DATABASE_URL and ensure "
            "PostgreSQL/PostGIS is reachable before starting the API."
        )
        raise RuntimeError(
            "BhuDrishti cannot start because the configured PostgreSQL/PostGIS "
            "database is unavailable. Check DATABASE_URL and the database service."
        ) from exc

    if settings.PROCESSING_MODE.lower() == "local":
        try:
            from app.services.ai.sam_engine import warmup_local_sam
            warmup_local_sam()
            logger.info("Local SAM model warmed up at startup; it will be reused for subsequent requests.")
        except Exception as exc:
            logger.warning(f"Local SAM warm-up failed at startup: {exc}")

    # Re-submit jobs that were durably queued before a process restart. The
    # worker uses independent sessions and lifecycle transitions are locked.
    try:
        from app.services.v2.job_executor import recover_queued_jobs

        recovered = recover_queued_jobs()
        if recovered:
            logger.info("Recovered %s queued v2 processing job(s).", recovered)
    except Exception as exc:
        logger.warning("Queued v2 job recovery unavailable: %s", exc)

    logger.info("Startup complete. Ready to accept requests.")
    yield
    logger.info("Shutting down gracefully...")
    try:
        from app.services.v2.job_executor import shutdown_executor

        shutdown_executor()
    except Exception:
        logger.exception("Unable to shut down the v2 processing worker cleanly.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Automated Geospatial AI platform for land parcel boundary extraction and ULPIN generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="frontend-js")
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="frontend-css")

# ---------------------------------------------------------------------
# CORS — Leaflet frontend (running from a different port/origin during
# local dev, e.g. Live Server on :5500) needs explicit permission to
# call this API from the browser.
# ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# GLOBAL ERROR HANDLER
# ---------------------------------------------------------------------
@app.exception_handler(DatasetValidationError)
@app.exception_handler(RasterValidationError)
@app.exception_handler(TopologyValidationError)
@app.exception_handler(FeatureExtractionError)
@app.exception_handler(ReconciliationError)
@app.exception_handler(ExportValidationError)
async def domain_validation_handler(request: Request, exc: BhuDrishtiError):
    logger.warning("Domain validation failed on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.message,
            "error_type": exc.__class__.__name__,
            "details": exc.details,
        },
    )


@app.exception_handler(JobExecutionError)
@app.exception_handler(NakshaIntegrationError)
async def domain_runtime_handler(request: Request, exc: BhuDrishtiError):
    logger.error("Domain operational error on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": exc.message,
            "error_type": exc.__class__.__name__,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. The technical team has been notified."},
    )


# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_v2_router, prefix="/api/v2")


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def root():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard.html", include_in_schema=False)
def dashboard_page():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/workspace", include_in_schema=False)
@app.get("/workspace.html", include_in_schema=False)
def workspace_page():
    return FileResponse(FRONTEND_DIR / "workspace.html")


@app.get("/health", tags=["Health"])
def health_check():
    """
    Lightweight liveness check. Database connectivity is verified during
    startup, while this endpoint confirms that the API process is serving.
    """
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def readiness_check():
    """
    Readiness probe for orchestration and health monitoring.
    Verifies database accessibility and storage folder availability.
    """
    checks = {"database": "ok", "storage": "ok"}
    is_ready = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness database check failed: %s", exc)
        checks["database"] = "unreachable"
        is_ready = False

    try:
        for storage_dir in [settings.V2_RASTER_DIR, settings.V2_DATASET_DIR, settings.V2_EXPORT_DIR]:
            Path(storage_dir).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("Readiness storage check failed: %s", exc)
        checks["storage"] = "inaccessible"
        is_ready = False

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if is_ready else "not_ready", "checks": checks},
    )