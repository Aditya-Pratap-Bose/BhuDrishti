"""Authenticated v2 geometry quality endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from shapely.geometry import shape

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.parcel import ParcelGeoJSONResponse
from app.schemas.quality import TopologyValidationResponse
from app.services.v2.topology import enforce_cadastral_topology, inspect_topology

router = APIRouter(prefix="/quality", tags=["v2 Quality"])


@router.post("/validate")
async def validate_parcels(
    payload: ParcelGeoJSONResponse,
    current_user: User = Depends(get_current_user),
) -> TopologyValidationResponse:
    """Return quality flags and cleaned GeoJSON without persisting changes."""
    del current_user
    geometries = [shape(feature.geometry.model_dump()) for feature in payload.features]
    results = []
    for index, geometry in enumerate(geometries):
        neighbours = geometries[:index] + geometries[index + 1 :]
        try:
            cleaned = enforce_cadastral_topology(geometry, neighbours)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        report = inspect_topology(geometry, neighbours)
        results.append(
            {
                "index": index,
                "valid": report.valid,
                "repaired": report.repaired,
                "overlaps": report.overlaps,
                "overlap_area": report.overlap_area,
                "near_duplicate": report.near_duplicate,
                "sliver": report.sliver,
                "area": report.area,
                "perimeter": report.perimeter,
                "cleaned_geometry": cleaned.__geo_interface__,
            }
        )
    return TopologyValidationResponse(type="TopologyValidation", features=results)
