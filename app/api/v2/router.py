from fastapi import APIRouter

from app.api.v2.jobs import router as jobs_router
from app.api.v2.quality import router as quality_router
from app.api.v2.raster import router as raster_router
from app.api.v2.satellite import router as satellite_router
from app.api.v2.tiles import router as tiles_router
from app.api.v2.features import router as features_router

api_router = APIRouter()
api_router.include_router(satellite_router)
api_router.include_router(raster_router)
api_router.include_router(quality_router)
api_router.include_router(tiles_router)
api_router.include_router(jobs_router)
api_router.include_router(features_router)
