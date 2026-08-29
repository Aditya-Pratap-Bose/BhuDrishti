"""
app/services/ai/sam_engine.py
--------------------------------
Ye file "engine room" hai. Upar wala API layer (satellite.py, drone.py)
ko sirf itna pata hona chahiye ki input do, GeoJSON milega — ANDAR
Colab chal raha hai, STAC-Sentinel chal raha hai, ya kisi ne apni drone
GeoTIFF upload ki hai, uska farak upar kabhi nahi dikhna chahiye.
"""

import asyncio
import hashlib
import json
import logging
import threading
import tempfile
from pathlib import Path
from typing import Any

from httpx import AsyncClient, ConnectError, TimeoutException

from app.core.config import settings

logger = logging.getLogger("bhudrishti.sam_engine")

_LOCAL_SAM: Any = None
_LOCAL_SAM_LOCK = threading.Lock()
_LOCAL_INFERENCE_LOCK = threading.Lock()


class SamEngineError(Exception):
    """Base exception — koi bhi AI-engine-level problem isse inherit karti hai."""
    pass


class ColabUnreachableError(SamEngineError):
    pass


class ColabTimeoutError(SamEngineError):
    pass


class ColabProcessingError(SamEngineError):
    pass


# ---------------------------------------------------------------------
# ENGINE 1: COLAB BRIDGE (bilkul unchanged — sirf bbox flow use karta hai)
# ---------------------------------------------------------------------

async def call_colab_bridge(bbox: tuple[float, float, float, float], source_type: str = "sentinel") -> dict:
    url = f"{settings.COLAB_AI_ENDPOINT}/process"
    payload = {
        "min_lon": bbox[0], "min_lat": bbox[1], "max_lon": bbox[2], "max_lat": bbox[3],
        "source_type": source_type,
    }
    logger.info(f"Colab bridge ko call kar rahe hain: {url} | bbox={bbox}")

    try:
        async with AsyncClient(timeout=settings.COLAB_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
    except ConnectError as e:
        logger.error(f"Colab tunnel unreachable: {e}")
        raise ColabUnreachableError(
            "Colab AI engine se connect nahi ho paaya. Tunnel URL expire "
            "ho chuka hoga — Colab notebook check karke naya cloudflared "
            "URL .env ke COLAB_AI_ENDPOINT mein update karein."
        ) from e
    except TimeoutException as e:
        logger.error(f"Colab request timed out after {settings.COLAB_REQUEST_TIMEOUT_SECONDS}s: {e}")
        raise ColabTimeoutError(
            f"SAM inference {settings.COLAB_REQUEST_TIMEOUT_SECONDS} seconds ke andar "
            "poora nahi hua. Bbox chhota karke dobara try karein."
        ) from e

    if response.status_code != 200:
        logger.error(f"Colab returned HTTP {response.status_code}: {response.text}")
        raise ColabProcessingError(
            f"Colab AI engine ne error diya (HTTP {response.status_code})."
        )

    data = response.json()
    if "error" in data:
        logger.error(f"Colab pipeline internal error: {data['error']}")
        raise ColabProcessingError(f"Colab processing failed: {data['error']}")

    logger.info(f"Colab se {len(data.get('features', []))} parcels mile.")
    return data


# ---------------------------------------------------------------------
# ENGINE 2: LOCAL INFERENCE — STAC(bbox) aur direct-upload(drone) dono
# isi shared core (_run_sam_on_image) se guzarte hain.
# ---------------------------------------------------------------------

def _get_local_sam() -> Any:
    global _LOCAL_SAM
    if _LOCAL_SAM is not None:
        return _LOCAL_SAM

    checkpoint = Path(settings.LOCAL_SAM_CHECKPOINT).expanduser()
    if not checkpoint.is_absolute():
        checkpoint = Path.cwd() / checkpoint
    if not checkpoint.is_file():
        raise SamEngineError(
            f"Local SAM checkpoint nahi mila: {checkpoint}. "
            "LOCAL_SAM_CHECKPOINT ko .env mein valid sam_vit_b.pth path par set karein."
        )

    try:
        from samgeo import SamGeo
    except ImportError as exc:
        raise SamEngineError(
            "Local SAM dependencies missing hain. requirements.txt se "
            "segment-geospatial install karein."
        ) from exc

    with _LOCAL_SAM_LOCK:
        if _LOCAL_SAM is None:
            _LOCAL_SAM = SamGeo(model_type="vit_b", checkpoint=str(checkpoint), sam_kwargs=None)
    return _LOCAL_SAM


def _local_ulpin(geometry: Any) -> str:
    centroid = geometry.centroid
    value = f"{centroid.x:.7f}:{centroid.y:.7f}"
    return f"LOCAL-{hashlib.sha256(value.encode()).hexdigest()[:20].upper()}"


def _generate_preview_png_base64(image, max_dim: int = 512) -> str | None:
    """
    Chhota base64 PNG banata hai raw imagery dikhane ke liye — Leaflet
    ImageOverlay isse seedha bina kisi tile-server ke render kar sakta hai.
    Downsample isliye kiya hai taaki response bloat na ho — tunnel aur
    kamzor laptop dono ke liye halka rakhna zaroori hai.

    Pillow/numpy missing hone par (ya kisi bhi wajah se preview fail ho)
    ye None return karta hai — poora detection pipeline crash nahi hona
    chahiye sirf isliye ki ek "nice to have" preview nahi ban paayi.
    """
    try:
        import base64
        from io import BytesIO
        import numpy as np
        from PIL import Image
    except ImportError:
        logger.warning("Pillow/numpy missing hain — preview image skip kar rahe hain.")
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
        logger.warning(f"Preview image generate nahi ho payi: {e}")
        return None


def _vector_to_feature_collection(vector_path: Path, utm_epsg: int) -> list[dict]:
    """
    Shared post-processing: raw vectorized SAM output ko clean, simplified,
    ULPIN-tagged features ki list mein badalta hai. STAC-bbox flow aur
    drone-upload flow dono isko use karte hain — ek jagah rakha hai.
    """
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

    gdf["geometry"] = gdf.geometry.simplify(0.2, preserve_topology=True)
    gdf["area_sqm"] = gdf.geometry.area
    gdf = gdf[gdf["area_sqm"] > gdf["area_sqm"].quantile(0.25)].copy()
    gdf["perimeter_m"] = gdf.geometry.length
    gdf["ulpin"] = gdf.geometry.apply(_local_ulpin)
    gdf = gdf.to_crs(epsg=4326)

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
    """
    Shared core: ek already-EPSG:4326 rioxarray `image` leke SAM chalata
    hai aur poora FeatureCollection (+ preview) banata hai. Caller sirf
    guarantee kare ki image already 4326 mein hai — baaki sab yahin hota hai.
    """
    sam = _get_local_sam()
    preview_b64 = _generate_preview_png_base64(image)
    bounds = image.rio.bounds()  # (minx, miny, maxx, maxy) — already 4326

    with tempfile.TemporaryDirectory(prefix="bhudrishti-sam-") as work_dir:
        work_path = Path(work_dir)
        tif_path = work_path / "input.tif"
        mask_path = work_path / "mask.tif"
        vector_path = work_path / "output.geojson"

        image.rio.to_raster(tif_path)

        with _LOCAL_INFERENCE_LOCK:
            sam.generate(str(tif_path), output=str(mask_path))
            sam.tiff_to_vector(str(mask_path), str(vector_path))

        features = _vector_to_feature_collection(vector_path, utm_epsg)

    return {
        "type": "FeatureCollection",
        "features": features,
        "preview_image_base64": preview_b64,
        "preview_bounds": list(bounds) if bounds else None,
    }


def _run_local_sam_from_sentinel(bbox: tuple[float, float, float, float]) -> dict:
    """STAC discovery + crop + SAM — 'sentinel' source-type ka path."""
    try:
        import planetary_computer
        import pystac_client
        import rioxarray
    except ImportError as exc:
        raise SamEngineError(
            "Local engine dependencies missing hain. requirements.txt install karein."
        ) from exc

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
        raise SamEngineError("Is area/date range mein suitable Sentinel-2 image nahi mili.")

    selected_item = min(items, key=lambda item: item.properties.get("eo:cloud_cover", 100))
    visual_asset = selected_item.assets.get("visual")
    if visual_asset is None:
        raise SamEngineError("Selected Sentinel-2 scene mein visual asset nahi mila.")

    image = rioxarray.open_rasterio(visual_asset.href)
    try:
        cropped = image.rio.clip_box(
            minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs="EPSG:4326",
        )
        # Sentinel COG ka native CRS aksar UTM hota hai — preview/bounds
        # Leaflet (lat/lon) ke liye seedha usable rahein isliye yahin
        # 4326 mein reproject kar dete hain.
        cropped_4326 = cropped.rio.reproject("EPSG:4326")
        return _run_sam_on_image(cropped_4326, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


def _run_local_sam_on_upload(file_path: Path) -> dict:
    """Drone/custom raster upload — bbox/STAC ki zaroorat nahi, poori file hi area hai."""
    try:
        import rioxarray
    except ImportError as exc:
        raise SamEngineError(
            "Local engine dependencies missing hain. requirements.txt install karein."
        ) from exc

    image = rioxarray.open_rasterio(str(file_path))
    try:
        if image.rio.crs is None:
            raise SamEngineError(
                "Uploaded raster mein CRS/geo-referencing missing hai. "
                "Sirf georeferenced GeoTIFF upload karein."
            )
        if image.rio.crs.to_epsg() != 4326:
            image = image.rio.reproject("EPSG:4326")
        return _run_sam_on_image(image, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


async def run_local_sam_inference(bbox: tuple[float, float, float, float], source_type: str = "sentinel") -> dict:
    return await asyncio.to_thread(_run_local_sam_inference, bbox, source_type)


async def run_local_sam_on_file(file_path: Path) -> dict:
    """satellite/process-drone endpoint ka public entrypoint."""
    return await asyncio.to_thread(_run_local_sam_on_upload, file_path)


# ---------------------------------------------------------------------
# PUBLIC ENTRYPOINT — sirf bbox flow ke liye. Drone upload isse bypass
# karta hai (drone.py seedha run_local_sam_on_file call karta hai)
# kyunki wahan koi bbox hi nahi hota.
# ---------------------------------------------------------------------

async def process_bbox(bbox: tuple[float, float, float, float], source_type: str = "sentinel") -> dict:
    mode = settings.PROCESSING_MODE.lower()
    if mode == "colab":
        return await call_colab_bridge(bbox, source_type)
    elif mode == "local":
        return await run_local_sam_inference(bbox, source_type)
    else:
        raise SamEngineError(
            f"Invalid PROCESSING_MODE='{settings.PROCESSING_MODE}' in .env. "
            "Allowed values: 'colab' or 'local'."
        )


def _run_local_sam_from_oam(bbox: tuple[float, float, float, float]) -> dict:
    """
    OpenAerialMap discovery + crop + SAM — 'openaerialmap' source-type ka path.
    """
    try:
        import leafmap
        import rioxarray
    except ImportError as exc:
        raise SamEngineError(
            "OpenAerialMap engine ke liye 'leafmap' install nahi hai. "
            "requirements.txt install karein."
        ) from exc

    gdf = leafmap.oam_search(bbox=list(bbox), return_gdf=True)
    if gdf is None or gdf.empty:
        raise SamEngineError(
            "Is bbox ke liye OpenAerialMap par koi drone/aerial imagery "
            "available nahi hai (OAM crowd-sourced hai aur coverage mostly "
            "disaster-response zones tak limited hai). Sentinel-2 source "
            "try karein."
        )

    # Sabse chhota file pehle — badi drone mosaics (100s MB) kamzor
    # laptop/network pe realistically download nahi hongi.
    if "file_size" in gdf.columns:
        gdf = gdf.sort_values("file_size")
    asset_url = gdf.iloc[0]["uuid"]  # leafmap convention: 'uuid' column = downloadable GeoTIFF URL

    image = rioxarray.open_rasterio(asset_url)
    try:
        if image.rio.crs is None:
            raise SamEngineError("Selected OAM image mein CRS missing hai.")
        cropped = image.rio.clip_box(
            minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs="EPSG:4326",
        )
        if cropped.rio.crs.to_epsg() != 4326:
            cropped = cropped.rio.reproject("EPSG:4326")
        return _run_sam_on_image(cropped, settings.LOCAL_UTM_EPSG)
    finally:
        image.close()


def _run_local_sam_inference(bbox: tuple[float, float, float, float], source_type: str = "sentinel") -> dict:
    """bbox flow ka local dispatcher — source_type ke hisaab se sahi imagery loader chunta hai."""
    if source_type == "openaerialmap":
        return _run_local_sam_from_oam(bbox)
    return _run_local_sam_from_sentinel(bbox)