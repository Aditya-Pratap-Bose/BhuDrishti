import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.parcel import BBoxRequest, ParcelGeoJSONResponse
from app.services.ai.sam_engine import (
    ColabProcessingError,
    ColabTimeoutError,
    ColabUnreachableError,
    SamEngineError,
    process_bbox,
)

logger = logging.getLogger("bhudrishti.api.v2.satellite")
router = APIRouter(prefix="/satellite", tags=["Satellite Processing v2"])


@router.post("/process-bbox", response_model=ParcelGeoJSONResponse)
async def process_satellite_bbox(
    payload: BBoxRequest,
    current_user: User = Depends(get_current_user),
) -> ParcelGeoJSONResponse:
    bbox = (payload.min_lon, payload.min_lat, payload.max_lon, payload.max_lat)

    if payload.source_type == "isro_bhuvan":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ISRO Bhuvan processing requires an authorized government API token.",
        )

    logger.info("v2 bbox processing requested by %s: %s", current_user.email, bbox)

    try:
        result = await process_bbox(bbox, payload.source_type)
    except ColabUnreachableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ColabTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ColabProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SamEngineError as exc:
        logger.exception("v2 processing failed for bbox %s", bbox)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected v2 processing failure for bbox %s", bbox)
        raise HTTPException(
            status_code=500,
            detail="Satellite processing failed unexpectedly. Check the server logs.",
        ) from exc

    try:
        return ParcelGeoJSONResponse.model_validate(result)
    except Exception as exc:
        logger.exception("Invalid processing response for bbox %s", bbox)
        raise HTTPException(
            status_code=502,
            detail="The processing engine returned an invalid GeoJSON response.",
        ) from exc
