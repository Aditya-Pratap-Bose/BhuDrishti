"""
app/api/v1/drone.py
---------------------
Drone / custom raster upload endpoint. Officer apni khud ki georeferenced
GeoTIFF upload karega, aur isi machine pe local SAM engine chalega —
Colab tunnel ki zaroorat NAHI, chahe .env mein PROCESSING_MODE=colab
ho for bbox flow. Poori file Colab tunnel se upload karna practical
nahi hai isliye ye hamesha local engine use karta hai.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.parcel import ParcelGeoJSONResponse
from app.services.ai.sam_engine import SamEngineError, run_local_sam_on_file

logger = logging.getLogger("bhudrishti.drone")

router = APIRouter(prefix="/satellite", tags=["Drone Upload"])

ALLOWED_EXTENSIONS = {".tif", ".tiff"}
MAX_UPLOAD_MB = 200  # kamzor laptop hai — bada file GPU-less machine ko hila dega


@router.post("/process-drone", response_model=ParcelGeoJSONResponse)
async def process_drone_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{suffix or 'unknown'}' file type allowed nahi hai. Sirf .tif/.tiff GeoTIFF upload karein.",
        )

    logger.info(f"User {current_user.email} ne drone raster upload kiya: {file.filename}")

    # rioxarray/rasterio seedha UploadFile stream se nahi khulte — real
    # disk path chahiye hota hai, isliye temp file mein save karte hain.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        size = 0
        chunk_size = 1024 * 1024
        while chunk := await file.read(chunk_size):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File {MAX_UPLOAD_MB}MB se bada hai. Chhota raster crop karke try karein.",
                )
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        raw_geojson = await run_local_sam_on_file(tmp_path)
    except SamEngineError as e:
        logger.error(f"Drone processing error: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)  # temp file kabhi disk pe permanently nahi rehni chahiye

    try:
        validated_response = ParcelGeoJSONResponse.model_validate(raw_geojson)
    except Exception as e:
        logger.error(f"Drone response schema mismatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI engine se aaya data expected format mein nahi tha.",
        )

    logger.info(f"Drone upload se {len(validated_response.features)} parcels mile.")
    return validated_response