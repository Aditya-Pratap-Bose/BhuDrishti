from fastapi import APIRouter

from app.api.v2.datasets import router as datasets_router
from app.api.v2.administrative import router as administrative_router
from app.api.v2.exports import router as exports_router
from app.api.v2.features import router as features_router
from app.api.v2.jobs import router as jobs_router
from app.api.v2.projects import router as projects_router
from app.api.v2.quality import router as quality_router
from app.api.v2.raster import router as raster_router
from app.api.v2.reference_data import router as reference_data_router
from app.api.v2.reconciliation import router as reconciliation_router
from app.api.v2.satellite import router as satellite_router
from app.api.v2.tiles import router as tiles_router
from app.api.v2.topology import router as topology_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(administrative_router)
api_router.include_router(datasets_router)
api_router.include_router(satellite_router)
api_router.include_router(raster_router)
api_router.include_router(reference_data_router)
api_router.include_router(quality_router)
api_router.include_router(topology_router)
api_router.include_router(reconciliation_router)
api_router.include_router(exports_router)
api_router.include_router(tiles_router)
api_router.include_router(jobs_router)
api_router.include_router(features_router)

