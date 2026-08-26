"""
app/main.py
------------
FastAPI application entrypoint. Middleware, startup events, and the
root health-check live here. This is what `uvicorn` actually runs.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.v1.router import api_router

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
    except Exception as e:
        # IMPORTANT: agar DB connect nahi ho paata (Postgres chalu nahi
        # hai, ya .env me DATABASE_URL galat hai), poora server crash
        # NAHI hoga. Sirf warning dega. Ye critical hai kyunki tera
        # health check aur Colab-bridge endpoints DB pe depend nahi
        # karte — agar sirf isliye poora backend down ho jaaye ki DB
        # nahi chal raha, live demo me ye disaster ban sakta hai.
        logger.warning(f"Startup DB init failed (continuing without DB): {e}")

    logger.info("Startup complete. Ready to accept requests.")
    yield
    logger.info("Shutting down gracefully...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Automated Geospatial AI platform for land parcel boundary extraction and ULPIN generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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
# GLOBAL ERROR HANDLER — catches anything unhandled so the demo never
# shows a raw Python traceback to the audience.
# ---------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Kuch galat ho gaya. Team ko is error ki jaankari mil chuki hai."},
    )


# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Lightweight check — DB ya Colab pe depend nahi karta, sirf "is the
    server alive" batata hai. Tera Colab notebook me bhi tune isi
    pattern ka /health endpoint banaya tha — same idea yahan bhi,
    consistency ke liye.
    """
    return {"status": "ok"}