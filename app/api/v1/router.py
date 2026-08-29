"""
app/api/v1/router.py
----------------------
Central aggregator for all v1 routers.
"""

from fastapi import APIRouter

from app.api.v1 import auth, drone, parcel, satellite

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(satellite.router)
api_router.include_router(drone.router)
api_router.include_router(parcel.router)