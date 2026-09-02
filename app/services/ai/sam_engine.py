"""
app/services/ai/sam_engine.py
--------------------------------
Geospatial AI segmentation engine for automated cadastral boundary extraction.
Supports hybrid execution via remote GPU (Google Colab Cloudflare tunnel)
and optimized local Segment Anything Model (SAM ViT-B) inference.
"""

import asyncio
import gc
import json
import logging
import math
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from httpx import AsyncClient, ConnectError, TimeoutException

from app.core.config import settings
from app.services.ulpin_generator import generate_ulpin_from_geometry

logger = logging.getLogger("bhudrishti.sam_engine")

_LOCAL_SAM: Any = None
_LOCAL_SAM_LOCK = threading.Lock()
_LOCAL_INFERENCE_LOCK = threading.Lock()


class SamEngineError(Exception):
    """Base exception for AI engine failures."""
    pass


class ColabUnreachableError(SamEngineError):
    pass


class ColabTimeoutError(SamEngineError):
    pass


class ColabProcessingError(SamEngineError):
    pass


# ---------------------------------------------------------------------
# REMOTE GPU BRIDGE (Google Colab via Cloudflare Tunnel)
# ---------------------------------------------------------------------

async def call_colab_bridge(bbox: tuple[float, float, float, float], source_type: str = "esri") -> dict:
    endpoint = settings.COLAB_AI_ENDPOINT.strip().rstrip("/")
    url = f"{endpoint}/process"
    payload = {
        "min_lon": bbox[0], "min_lat": bbox[1], "max_lon": bbox[2], "max_lat": bbox[3],
        "source_type": source_type,
    }
    logger.info(f"Invoking remote Colab GPU bridge: {url} | bbox={bbox}")

    try:
        async with AsyncClient(timeout=settings.COLAB_REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.post(url, json=payload)
    except ConnectError as e:
        logger.error(f"Colab tunnel connection failed: {e}")
        raise ColabUnreachableError(
            "Could not connect to Colab AI engine. The Cloudflare tunnel may have expired. "
            "Please update COLAB_AI_ENDPOINT in .env with the active tunnel URL."
        ) from e
    except TimeoutException as e:
        logger.error(f"Colab request timed out after {settings.COLAB_REQUEST_TIMEOUT_SECONDS}s: {e}")
        raise ColabTimeoutError(
            f"SAM inference timed out after {settings.COLAB_REQUEST_TIMEOUT_SECONDS}s. "
            "Please reduce the bounding box area and retry."
        ) from e

    if response.status_code in (502, 503, 530) or "cloudflare" in response.text.lower() or "<html" in response.text.lower():
        logger.error(f"Colab tunnel returned error status {response.status_code}")
        raise ColabUnreachableError(
            f"Colab tunnel is offline (HTTP {response.status_code}). "
            "Ensure the Colab notebook server and cloudflared tunnel are actively running."
        )

    if response.status_code != 200:
        logger.error(f"Colab returned HTTP {response.status_code}: {response.text[:200]}")
        raise ColabProcessingError(f"Colab AI engine returned HTTP {response.status_code}.")

    try:
        data = response.json()
    except Exception as e:
        logger.error(f"Colab returned invalid JSON: {e}")
        raise ColabProcessingError(f"Invalid JSON received from Colab: {e}")

    if "error" in data:
        logger.error(f"Colab pipeline error: {data['error']}")
        raise ColabProcessingError(f"Colab processing failed: {data['error']}")

    logger.info(f"Colab extraction successful: {len(data.get('features', []))} parcels detected.")
    return data


# ---------------------------------------------------------------------
# LOCAL SAM ENGINE (Optimized CPU/GPU ViT-B Segmentation)
# ---------------------------------------------------------------------

OFFICIAL_SAM_VIT_B_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"


def _resolve_local_sam_device() -> str:
    """Prefer CUDA for local inference when the machine exposes a usable GPU."""
    explicit = (settings.LOCAL_SAM_DEVICE or "auto").strip().lower()
    if explicit in {"cpu", "cuda"}:
        return explicit

    try:
        import torch
    except Exception:
        return "cpu"

    if settings.LOCAL_SAM_USE_CUDA_IF_AVAILABLE and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _ensure_sam_checkpoint_exists(checkpoint_path: Path) -> Path:
    """
    Ensures the SAM model checkpoint exists locally on disk.
    If already present (>100MB), reuses it directly without downloading.
    If missing, downloads it once and permanently caches it to disk.
    """
    if checkpoint_path.is_file() and checkpoint_path.stat().st_size > 100_000_000:
        return checkpoint_path

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"SAM checkpoint not found at {checkpoint_path}. Downloading one-time model weights (375 MB)...")
    
    import urllib.request
    try:
        urllib.request.urlretrieve(OFFICIAL_SAM_VIT_B_URL, str(checkpoint_path))
        logger.info(f"Successfully cached SAM model weights permanently at {checkpoint_path}")
    except Exception as e:
        logger.error(f"Failed to auto-download SAM model weights: {e}")
        if checkpoint_path.exists():
            checkpoint_path.unlink(missing_ok=True)
        raise SamEngineError(
            f"Could not auto-download SAM model weights: {e}. "
            f"Please download manually from {OFFICIAL_SAM_VIT_B_URL} and place at {checkpoint_path}"
        )
    return checkpoint_path


def warmup_local_sam() -> Any:
    """Load the local SAM model once and cache it for all future requests in this process."""
    return _get_local_sam()


def _get_local_sam() -> Any:
    """
    Returns the in-memory singleton instance of SamGeo.
    Loaded exactly once per Python process and reused for all subsequent inference requests.
    """
    global _LOCAL_SAM
    if _LOCAL_SAM is not None:
        return _LOCAL_SAM

    checkpoint = Path(settings.LOCAL_SAM_CHECKPOINT).expanduser()
    if not checkpoint.is_absolute():
        checkpoint = Path.cwd() / checkpoint

    checkpoint = _ensure_sam_checkpoint_exists(checkpoint)

    try:
        from samgeo import SamGeo
    except ImportError as exc:
        raise SamEngineError(
            "Local SAM dependencies missing. Please install segment-geospatial from requirements.txt."
        ) from exc

    device = _resolve_local_sam_device()
    sam_kwargs = None

    with _LOCAL_SAM_LOCK:
        if _LOCAL_SAM is None:
            logger.info(f"Loading local SAM model from {checkpoint} into memory using device='{device}'...")
            _LOCAL_SAM = SamGeo(
                model_type="vit_b",
                checkpoint=str(checkpoint),
                device=device,
                sam_kwargs=sam_kwargs,
            )
            logger.info("SAM model loaded successfully into memory on %s. Cached singleton ready for inference.", device)
    return _LOCAL_SAM


def _generate_preview_png_base64(image, max_dim: int = 512) -> str | None:
    """Generates downsampled base64 PNG thumbnail for Leaflet ImageOverlay."""
    try:
        import base64
        from io import BytesIO
        import numpy as np
        from PIL import Image
    except ImportError:
        return None

    try:
        arr = image.values
        bands = arr[:3] if arr.shape[0] >= 3 else arr
        rgb = np.transpose(bands, (1, 2, 0))

        if rgb.dtype != np.uint8:
            rgb = rgb.astype("float32")
            rgb = rgb - rgb.min()
            max_val = rgb.max()
            if max_val > 0:
                rgb = (rgb / max_val) * 255
            rgb = rgb.astype("uint8")

        pil_img = Image.fromarray(rgb)
        pil_img.thumbnail((max_dim, max_dim))

        buffer = BytesIO()
        pil_img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to generate preview image: {e}")
        return None


def _vector_to_feature_collection(vector_path: Path, utm_epsg: int) -> list[dict]:
    """Post-processes raw polygon vectors: topological simplification, metric calculation, and standard ULPIN tagging."""
    import geopandas as gpd
    from shapely.geometry import mapping

    gdf = gpd.read_file(vector_path)
    if gdf.empty:
        return []
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    gdf = gdf.to_crs(epsg=utm_epsg)
    gdf = gdf.explode(index_parts=False, ignore_index=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf[gdf.geometry.geom_type == "Polygon"].copy()
    if gdf.empty:
        return []

    # Simplify boundary noise and filter out tiny non-parcel artifacts
    gdf["geometry"] = gdf.geometry.simplify(0.3, preserve_topology=True)
    gdf["area_sqm"] = gdf.geometry.area
    
    # Filter out sliver polygons and small noise (< 20 m²)
    gdf = gdf[gdf["area_sqm"] > 20.0].copy()
    if gdf.empty:
        return []

    gdf["perimeter_m"] = gdf.geometry.length
    
    # Reproject back to standard WGS84 for GeoJSON output and ULPIN coordinate derivation
    gdf = gdf.to_crs(epsg=4326)
    gdf["ulpin"] = gdf.geometry.apply(lambda geom: generate_ulpin_from_geometry(geom))

    features = []
    for _, row in gdf.iterrows():
        geometry = row.geometry
        features.append({
            "type": "Feature",
            "properties": {
                "ulpin": row["ulpin"],
                "area_sqm": float(row["area_sqm"]),
                "perimeter_m": float(row["perimeter_m"]),
                "land_use": "Unclassified",
            },
            "geometry": json.loads(json.dumps(mapping(geometry))),
        })
    return features


def _run_sam_on_image(image, utm_epsg: int) -> dict:
    """Executes SAM inference pipeline with memory cleanup and fast temporary file lifecycle."""
    sam = _get_local_sam()
    preview_b64 = _generate_preview_png_base64(image)
    bounds = image.rio.bounds()

    work_dir = tempfile.mkdtemp(prefix="bhudrishti-sam-")
    work_path = Path(work_dir)
    tif_path = work_path / "input.tif"
    mask_path = work_path / "mask.tif"
    vector_path = work_path / "output.geojson"

    try:
        # Save raster input
        image.rio.to_raster(str(tif_path))

        with _LOCAL_INFERENCE_LOCK:
            sam.generate(str(tif_path), output=str(mask_path))
            sam.tiff_to_vector(str(mask_path), str(vector_path))

        features = _vector_to_feature_collection(vector_path, utm_epsg)
    finally:
        gc.collect()
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

    return {
        "type": "FeatureCollection",
        "features": features,
        "preview_image_base64": preview_b64,
        "preview_bounds": list(bounds) if bounds else None,
    }


def _calculate_zoom_for_bbox(bbox: tuple[float, float, float, float]) -> int:
    """Calculates optimal tile zoom level capped at 18 to maximize speed while maintaining sub-meter clarity."""
    min_lon, min_lat, max_lon, max_lat = bbox
    avg_lat = (min_lat + max_lat) / 2
    width_m = abs(max_lon - min_lon) * 111320 * math.cos(math.radians(avg_lat))
    height_m = abs(max_lat - min_lat) * 111320
    max_dim = max(width_m, height_m)
    
    if max_dim < 400:
        return 18  # Sub-meter ~0.6m/px (Fast & Sharp)
    elif max_dim < 1200:
        return 17  # ~1.2m/px
    else:
        return 16  # ~2.4m/px


def _run_local_sam_from_tiles(bbox: tuple[float, float, float, float], source_type: str = "esri") -> dict:
    """Fetches high-resolution satellite imagery tiles, stitches georeferenced raster, and runs SAM."""
    import rioxarray
    from app.services.gis.raster_service import stitch_tms_to_geotiff

    zoom = _calculate_zoom_for_bbox(bbox)
    tile_source = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

    tmp_dir = tempfile.mkdtemp(prefix="bhudrishti-tile-")
    out_tif = Path(tmp_dir) / "stitched_tile.tif"
    try:
        try:
            stitch_tms_to_geotiff(
                bbox=bbox,
                zoom=zoom,
                source_url=tile_source,
                output_path=str(out_tif),
                overwrite=True,
            )
        except Exception as e:
            logger.warning(f"Esri tile fetch failed: {e}. Attempting fallback satellite source.")
            fallback_source = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
            stitch_tms_to_geotiff(
                bbox=bbox,
                zoom=zoom,
                source_url=fallback_source,
                output_path=str(out_tif),
                overwrite=True,
            )
            
        image = rioxarray.open_rasterio(str(out_tif))
        try:
            if image.rio.crs is None:
                image = image.rio.write_crs("EPSG:4326")
            if image.rio.crs.to_epsg() != 4326:
                image = image.rio.reproject("EPSG:4326")
            result = _run_sam_on_image(image, settings.LOCAL_UTM_EPSG)
            return result
        finally:
            image.close()
    finally:
        gc.collect()
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _run_local_sam_from_sentinel(bbox: tuple[float, float, float, float]) -> dict:
    """Queries Planetary Computer STAC catalog for Sentinel-2 visual band imagery."""
    try:
        import planetary_computer
        import pystac_client
        import rioxarray
    except ImportError as exc:
        raise SamEngineError("Planetary Computer STAC dependencies missing.") from exc

    catalog = pystac_client.Client.open(
        settings.STAC_API_URL, modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=[settings.STAC_COLLECTION],
        bbox=list(bbox),
        datetime=settings.STAC_DATE_RANGE,
        query={"eo:cloud_cover": {"lt": settings.STAC_MAX_CLOUD_COVER}},
    )
    items = list(search.items())
    if not items:
        raise SamEngineError("No cloud-free Sentinel-2 scene found for the selected bounding box.")

    selected_item = min(items, key=lambda item: item.properties.get("eo:cloud_cover", 100))
    visual_asset = selected_item.assets.get("visual")
    if visual_asset is None:
        raise SamEngineError("Visual asset band missing in selected Sentinel-2 scene.")

    image = rioxarray.open_rasterio(visual_asset.href)
    try:
        cropped = image.rio.clip_box(
            minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs="EPSG:4326",
        )
        cropped_4326 = cropped.rio.reproject("EPSG:4326")
        return _run_sam_on_image(cropped_4326, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


def _run_local_sam_on_upload(file_path: Path) -> dict:
    """Direct drone orthophoto GeoTIFF segmentation without STAC querying."""
    try:
        import rioxarray
    except ImportError as exc:
        raise SamEngineError("RasterIO dependencies missing.") from exc

    image = rioxarray.open_rasterio(str(file_path))
    try:
        if image.rio.crs is None:
            raise SamEngineError("Uploaded GeoTIFF lacks CRS metadata. Please upload georeferenced ortho.")
        if image.rio.crs.to_epsg() != 4326:
            image = image.rio.reproject("EPSG:4326")
        return _run_sam_on_image(image, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


def _run_local_sam_from_oam(bbox: tuple[float, float, float, float]) -> dict:
    """OpenAerialMap discovery and segmentation."""
    try:
        import leafmap
        import rioxarray
    except ImportError as exc:
        raise SamEngineError("Leafmap dependency missing.") from exc

    gdf = leafmap.oam_search(bbox=list(bbox), return_gdf=True)
    if gdf is None or gdf.empty:
        raise SamEngineError("No OpenAerialMap drone mosaic available in this bounding box.")

    if "file_size" in gdf.columns:
        gdf = gdf.sort_values("file_size")
    asset_url = gdf.iloc[0]["uuid"]

    image = rioxarray.open_rasterio(asset_url)
    try:
        if image.rio.crs is None:
            raise SamEngineError("Selected OpenAerialMap raster missing CRS.")
        cropped = image.rio.clip_box(
            minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs="EPSG:4326",
        )
        if cropped.rio.crs.to_epsg() != 4326:
            cropped = cropped.rio.reproject("EPSG:4326")
        return _run_sam_on_image(cropped, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


def _run_local_sam_inference(bbox: tuple[float, float, float, float], source_type: str = "esri") -> dict:
    if source_type in ("esri", "osm"):
        return _run_local_sam_from_tiles(bbox, source_type)
    elif source_type == "openaerialmap":
        return _run_local_sam_from_oam(bbox)
    return _run_local_sam_from_sentinel(bbox)


async def run_local_sam_inference(bbox: tuple[float, float, float, float], source_type: str = "esri") -> dict:
    return await asyncio.to_thread(_run_local_sam_inference, bbox, source_type)


async def run_local_sam_on_file(file_path: Path) -> dict:
    return await asyncio.to_thread(_run_local_sam_on_upload, file_path)


async def process_bbox(bbox: tuple[float, float, float, float], source_type: str = "esri") -> dict:
    mode = settings.PROCESSING_MODE.lower()
    if mode == "colab":
        return await call_colab_bridge(bbox, source_type)
    elif mode == "local":
        return await run_local_sam_inference(bbox, source_type)
    else:
        raise SamEngineError(
            f"Invalid PROCESSING_MODE='{settings.PROCESSING_MODE}' in .env. Allowed values: 'colab' or 'local'."
        )

