"""
app/api/v1/router.py
----------------------
Central aggregator for all v1 routers. main.py sirf isi ek router ko
import karega — jaise-jaise naye modules (drone, satellite, parcel)
banenge, unko bas yahan ek line me add karna hoga.

MINDSET: Ye "single point of wiring" pattern hai. Agar kal koi naya
module aaya (jaise building-footprint detection), sirf yahan ek
`include_router()` line add karni hai — main.py ko touch hi nahi
karna padega.
"""

from fastapi import APIRouter

from app.api.v1 import auth, satellite

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(satellite.router)

# Jaise-jaise files banenge, yahan add hoga:
# from app.api.v1 import drone, parcel
# api_router.include_router(drone.router)
# api_router.include_router(parcel.router)