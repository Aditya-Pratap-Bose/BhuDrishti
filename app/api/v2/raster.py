"""Authenticated ORI/DTM ingestion endpoint for v2."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.raster import RasterUploadResponse
from app.services.v2.raster import RasterValidationError
from app.services.v2.upload import (
    UploadProcessingError,
    UploadTooLargeError,
    UploadValidationError,
    prepare_ori_dtm_upload,
)

logger = logging.getLogger("bhudrishti.api.v2.raster")

router = APIRouter(prefix="/raster", tags=["v2 Raster Ingestion"])


@router.post(
    "/upload",
    response_model=RasterUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_ori_dtm(
    ori_file: UploadFile = File(..., description="Orthorectified imagery GeoTIFF"),
    dtm_file: UploadFile = File(..., description="Digital terrain model GeoTIFF"),
    current_user: User = Depends(get_current_user),
) -> RasterUploadResponse:
    """Validate and publish a co-registered ORI/DTM pair as v2 COG assets."""
    logger.info(
        "v2 ORI/DTM upload requested by %s (%s, %s)",
        current_user.email,
        ori_file.filename,
        dtm_file.filename,
    )
    max_bytes = settings.V2_MAX_UPLOAD_MB * 1024 * 1024
    total_bytes = settings.V2_MAX_TOTAL_UPLOAD_MB * 1024 * 1024
    try:
        result = await prepare_ori_dtm_upload(
            ori_file,
            dtm_file,
            settings.V2_RASTER_DIR,
            max_upload_bytes=max_bytes,
            max_total_bytes=total_bytes,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except (UploadValidationError, RasterValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except UploadProcessingError as exc:
        logger.exception("v2 ORI/DTM COG preparation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    finally:
        # The service closes streams after reading; this also covers rejected
        # descriptors and failures before either stream is read.
        await ori_file.close()
        await dtm_file.close()
    return RasterUploadResponse.model_validate(result)
