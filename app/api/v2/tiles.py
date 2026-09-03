"""Authenticated XYZ tile delivery for v2 Cloud Optimized GeoTIFFs."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger("bhudrishti.api.v2.tiles")

router = APIRouter(prefix="/tiles", tags=["v2 Raster Tiles"])


def _raster_path(asset_id: str) -> Path:
    """Resolve an asset only inside the configured v2 raster directory."""
    if Path(asset_id).name != asset_id or Path(asset_id).suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid raster asset id.")
    root = Path(settings.V2_RASTER_DIR).resolve()
    candidate = (root / asset_id).resolve()
    if candidate.parent != root or not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raster asset not found.")
    return candidate


@router.get("/{asset_id}/{z}/{x}/{y}.png", response_class=Response)
def get_raster_tile(
    asset_id: str,
    z: int,
    x: int,
    y: int,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Render one 256px Web Mercator tile from a v2 COG."""
    del current_user
    if z < 0 or z > settings.V2_MAX_TILE_ZOOM:
        raise HTTPException(status_code=400, detail="Zoom is outside the supported v2 range.")
    tile_limit = 2**z
    if x < 0 or x >= tile_limit or y < 0 or y >= tile_limit:
        raise HTTPException(status_code=400, detail="Tile coordinates are outside the zoom range.")

    path = _raster_path(asset_id)
    try:
        with COGReader(str(path)) as cog:
            image = cog.tile(x, y, z)
            body = image.render(img_format="PNG")
    except TileOutsideBounds as exc:
        raise HTTPException(status_code=404, detail="Tile is outside raster bounds.") from exc
    except (OSError, ValueError) as exc:
        logger.exception("Unable to render v2 raster tile for %s", asset_id)
        raise HTTPException(status_code=422, detail="Raster asset could not be read as a COG.") from exc
    return Response(content=body, media_type="image/png")
