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
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import init_db
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