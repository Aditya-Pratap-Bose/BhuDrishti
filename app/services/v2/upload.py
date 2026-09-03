"""Safe, synchronous-ready ORI/DTM upload orchestration for v2."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.services.v2.raster import (
    RasterValidationError,
    convert_to_cog,
    inspect_raster,
    validate_coregistration,
)

ALLOWED_EXTENSIONS = frozenset({".tif", ".tiff"})
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/geotiff",
        "application/geo+tiff",
        "application/x-geotiff",
        "image/tiff",
        "application/octet-stream",
    }
)


class UploadValidationError(ValueError):
    """Raised when an upload does not satisfy the v2 ingestion contract."""


class UploadTooLargeError(UploadValidationError):
    """Raised when a raster exceeds the configured upload limit."""


class UploadProcessingError(RuntimeError):
    """Raised when a validated raster cannot be prepared for v2 use."""


def _format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.0f} MB"
    return f"{size} bytes"


def _validate_upload_descriptor(upload: UploadFile, role: str) -> str:
    filename = upload.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"{role.upper()} must be a GeoTIFF file with a .tif or .tiff extension."
        )
    content_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise UploadValidationError(
            f"{role.upper()} has unsupported content type '{content_type}'. "
            "Upload a GeoTIFF (image/tiff)."
        )
    return suffix


async def _write_upload(upload: UploadFile, destination: Path, max_bytes: int) -> int:
    """Copy an UploadFile in bounded chunks without trusting Content-Length."""
    size = 0
    try:
        with destination.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise UploadTooLargeError(
                        f"Each raster upload must be no larger than {_format_size(max_bytes)}."
                    )
                output.write(chunk)
    finally:
        await upload.close()
    return size


async def prepare_ori_dtm_upload(
    ori_upload: UploadFile,
    dtm_upload: UploadFile,
    output_dir: str | Path,
    *,
    max_upload_bytes: int,
    max_total_bytes: int,
) -> dict[str, Any]:
    """Validate two uploads, check co-registration, and publish two COG assets.

    Source files only exist inside a private temporary directory under the
    configured raster root (never the system-wide temp directory). COGs are
    written to hidden partial files and atomically renamed so a failed request
    cannot leave a tile endpoint pointing at an incomplete asset.
    """
    ori_suffix = _validate_upload_descriptor(ori_upload, "ori")
    dtm_suffix = _validate_upload_descriptor(dtm_upload, "dtm")
    if max_upload_bytes <= 0 or max_total_bytes <= 0:
        raise ValueError("Upload size limits must be positive.")

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    upload_id = uuid.uuid4().hex
    published: list[Path] = []

    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{upload_id}-upload-", dir=root
        ) as temp_dir:
            temp_root = Path(temp_dir)
            ori_source = temp_root / f"ori{ori_suffix}"
            dtm_source = temp_root / f"dtm{dtm_suffix}"
            ori_size = await _write_upload(ori_upload, ori_source, max_upload_bytes)
            dtm_size = await _write_upload(dtm_upload, dtm_source, max_upload_bytes)
            if ori_size + dtm_size > max_total_bytes:
                raise UploadTooLargeError(
                    f"The combined ORI and DTM upload must be no larger than "
                    f"{_format_size(max_total_bytes)}."
                )

            try:
                ori_metadata = inspect_raster(ori_source)
                dtm_metadata = inspect_raster(dtm_source)
                validate_coregistration(ori_source, dtm_source)
            except RasterValidationError:
                raise

            assets = {
                "ori": (ori_source, root / f"{upload_id}-ori.tif", ori_metadata),
                "dtm": (dtm_source, root / f"{upload_id}-dtm.tif", dtm_metadata),
            }
            for source, destination, _metadata in assets.values():
                partial = root / f".{destination.name}.part"
                try:
                    convert_to_cog(source, partial)
                    partial.replace(destination)
                finally:
                    partial.unlink(missing_ok=True)
                published.append(destination)
                # Confirm the artifact, not just its source, is readable.
                inspect_raster(destination)

            return {
                "type": "RasterUpload",
                "upload_id": upload_id,
                "status": "ready",
                "ori": {
                    "asset_id": published[0].name,
                    "role": "ori",
                    "format": "COG",
                    "metadata": ori_metadata,
                },
                "dtm": {
                    "asset_id": published[1].name,
                    "role": "dtm",
                    "format": "COG",
                    "metadata": dtm_metadata,
                },
                "co_registration": {
                    "valid": True,
                    "crs": ori_metadata["crs"],
                    "overlapping": True,
                },
            }
    except (UploadValidationError, RasterValidationError):
        for path in published:
            path.unlink(missing_ok=True)
        raise
    except (OSError, RuntimeError) as exc:
        for path in published:
            path.unlink(missing_ok=True)
        raise UploadProcessingError(
            "The validated rasters could not be converted to Cloud Optimized GeoTIFFs."
        ) from exc
