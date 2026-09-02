from fastapi import APIRouter

from app.api.v2.satellite import router as satellite_router

api_router = APIRouter()
api_router.include_router(satellite_router)
