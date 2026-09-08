"""
app/services/v2/terrain/__init__.py
-----------------------------------
Terrain and elevation processing services (DSM, DTM, nDSM).
"""

from app.services.v2.terrain.ndsm import (
    compute_ndsm,
    compute_terrain_metrics,
    extract_building_height_mask,
)

__all__ = [
    "compute_ndsm",
    "extract_building_height_mask",
    "compute_terrain_metrics",
]
