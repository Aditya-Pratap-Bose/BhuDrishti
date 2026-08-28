"""
app/services/ai/sam_engine.py
--------------------------------
Ye file "engine room" hai. Upar wala API layer (satellite.py) ko
sirf itna pata hona chahiye: "bbox do, GeoJSON milega" — ANDAR
Colab chal raha hai ya kal ko koi local GPU, uska farak upar
kabhi nahi dikhna chahiye. Isi principle ko "engine-agnostic
design" bolte hain.

MINDSET: Socho ye ek electricity switch board hai. Ghar ke andar
(satellite.py) sirf switch on/off karna aata hai. Bijli generator
se aa rahi hai ya solar panel se — wahi is board (sam_engine.py)
ka kaam hai decide karna, ghar ke baaki logo ko fark nahi padta.
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
# httpx zaroori hai (requests nahi) kyunki ye FastAPI ke async
# route ke andar bina block kiye chal sakta hai. requests use
# karte toh poora server us ek request ke time freeze ho jaata
# (kyunki requests sync/blocking hai) — baaki saare officers ka
# traffic bhi ruk jaata jab tak Colab jawab na de.

from app.core.config import settings

logger = logging.getLogger("bhudrishti.sam_engine")

_LOCAL_SAM: Any = None
_LOCAL_SAM_LOCK = threading.Lock()
_LOCAL_INFERENCE_LOCK = threading.Lock()


# ---------------------------------------------------------------------
# CUSTOM EXCEPTIONS — taaki upar wala layer (satellite.py) clean
# HTTP error codes de sake, raw Python traceback kabhi na dikhe.
# ---------------------------------------------------------------------

class SamEngineError(Exception):
    """Base exception — koi bhi AI-engine-level problem isse inherit karti hai."""
    pass


class ColabUnreachableError(SamEngineError):
    """Cloudflare tunnel expire ho gaya, ya Colab session band ho gaya."""
    pass


class ColabTimeoutError(SamEngineError):
    """SAM inference itna time le raha hai ki humari patience khatam ho gayi."""
    pass


class ColabProcessingError(SamEngineError):
    """Colab notebook khud ne apni try/except mein error pakda aur bataya."""
    pass


# ---------------------------------------------------------------------
# ENGINE 1: COLAB BRIDGE (abhi active)
# ---------------------------------------------------------------------

async def call_colab_bridge(bbox: tuple[float, float, float, float]) -> dict:
    """
    Tere Cloudflare-tunneled Colab /process endpoint ko call karta hai.

    bbox = (min_lon, min_lat, max_lon, max_lat)

    Teen cheezein specifically handle ki hain, kyunki teeno already
    tere saath live-testing mein ho chuki hain:
      1. Tunnel expire / unreachable  -> ColabUnreachableError
      2. Timeout (SAM slow hota hai)  -> ColabTimeoutError
      3. Colab ne khud error bheja    -> ColabProcessingError
    """
    url = f"{settings.COLAB_AI_ENDPOINT}/process"
    payload = {
        "min_lon": bbox[0],
        "min_lat": bbox[1],
        "max_lon": bbox[2],
        "max_lat": bbox[3],
    }

    logger.info(f"Colab bridge ko call kar rahe hain: {url} | bbox={bbox}")

    try:
        async with AsyncClient(timeout=settings.COLAB_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
    except ConnectError as e:
        # Tunnel URL galat hai, ya Colab session band ho chuka hai.
        # Ye SABSE COMMON failure hai demo ke din — Colab session
        # 12 ghante mein auto-disconnect ho jaata hai agar naya
        # tunnel URL .env mein update na kiya ho.
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
            "poora nahi hua. Bbox chhota karke dobara try karein, ya Colab "
            "GPU busy/slow ho sakta hai."
        ) from e

    # HTTP-level errors (404, 500 etc from Colab's own FastAPI/uvicorn)
    if response.status_code != 200:
        logger.error(f"Colab returned HTTP {response.status_code}: {response.text}")
        raise ColabProcessingError(
            f"Colab AI engine ne error diya (HTTP {response.status_code}). "
            "Colab notebook ke logs check karein."
        )

    data = response.json()

    # Tera Colab notebook already apni khud ki try/except se
    # {"error": "..."} format mein error bhejta hai agar andar kuch
    # fail ho (e.g. STAC empty results, invalid crop). Ye "fake success"
    # avoid karta hai — warna hum ek error-dict ko GeoJSON samajh ke
    # aage bhej dete, jo Leaflet mein silently crash karta.
    if "error" in data:
        logger.error(f"Colab pipeline internal error: {data['error']}")
        raise ColabProcessingError(f"Colab processing failed: {data['error']}")

    logger.info(f"Colab se {len(data.get('features', []))} parcels mile.")
    return data


# ---------------------------------------------------------------------
# ENGINE 2: LOCAL INFERENCE
# ---------------------------------------------------------------------

def _get_local_sam() -> Any:
    """Load the local model once, only when the local engine is selected."""
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
            _LOCAL_SAM = SamGeo(
                model_type="vit_b",
                checkpoint=str(checkpoint),
                sam_kwargs=None,
            )
    return _LOCAL_SAM


def _local_ulpin(geometry: Any) -> str:
    """Create a deterministic engine-scoped ID until official ULPIN rules apply."""
    centroid = geometry.centroid
    value = f"{centroid.x:.7f}:{centroid.y:.7f}"
    return f"LOCAL-{hashlib.sha256(value.encode()).hexdigest()[:20].upper()}"


def _run_local_sam_inference(bbox: tuple[float, float, float, float]) -> dict:
    """
    Local pipeline: STAC scene discovery, signed raster crop, SAM mask
    generation, vectorization, metric geometry calculation, and GeoJSON.
    Heavy optional imports stay inside this function so colab mode does not
    load the local ML/GIS stack during API startup.
    """
    try:
        import geopandas as gpd
        import planetary_computer
        import pystac_client
        import rioxarray
        from shapely.geometry import mapping
    except ImportError as exc:
        raise SamEngineError(
            "Local engine dependencies missing hain. requirements.txt install karein."
        ) from exc

    catalog = pystac_client.Client.open(
        settings.STAC_API_URL,
        modifier=planetary_computer.sign_inplace,
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

    selected_item = min(
        items,
        key=lambda item: item.properties.get("eo:cloud_cover", 100),
    )
    visual_asset = selected_item.assets.get("visual")
    if visual_asset is None:
        raise SamEngineError("Selected Sentinel-2 scene mein visual asset nahi mila.")

    sam = _get_local_sam()
    with tempfile.TemporaryDirectory(prefix="bhudrishti-sam-") as work_dir:
        work_path = Path(work_dir)
        tif_path = work_path / "sentinel_tile.tif"
        mask_path = work_path / "mask.tif"
        vector_path = work_path / "output.geojson"

        image = rioxarray.open_rasterio(visual_asset.href)
        try:
            image.rio.clip_box(
                minx=bbox[0],
                miny=bbox[1],
                maxx=bbox[2],
                maxy=bbox[3],
                crs="EPSG:4326",
            ).rio.to_raster(tif_path)
        finally:
            image.close()

        # One model instance is shared by requests. Serialize inference so
        # concurrent map requests cannot contend for model/device state.
        with _LOCAL_INFERENCE_LOCK:
            sam.generate(str(tif_path), output=str(mask_path))
            sam.tiff_to_vector(str(mask_path), str(vector_path))

        gdf = gpd.read_file(vector_path)
        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        gdf = gdf.to_crs(epsg=settings.LOCAL_UTM_EPSG)
        gdf = gdf.explode(index_parts=False, ignore_index=True)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        gdf = gdf[gdf.geometry.geom_type == "Polygon"].copy()
        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}

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

        return {"type": "FeatureCollection", "features": features}


async def run_local_sam_inference(bbox: tuple[float, float, float, float]) -> dict:
    """Run CPU/GPU-bound inference off the async event loop."""
    return await asyncio.to_thread(_run_local_sam_inference, bbox)


# ---------------------------------------------------------------------
# PUBLIC ENTRYPOINT — satellite.py SIRF isko call karega
# ---------------------------------------------------------------------

async def process_bbox(bbox: tuple[float, float, float, float]) -> dict:
    """
    Ye function "traffic controller" hai. PROCESSING_MODE dekh ke
    decide karta hai kaunsa engine chalana hai. Upar ka API layer
    (satellite.py) ko is decision se koi lena-dena nahi — wo sirf
    process_bbox(bbox) call karega aur GeoJSON dict wapas paayega.
    """
    mode = settings.PROCESSING_MODE.lower()

    if mode == "colab":
        return await call_colab_bridge(bbox)
    elif mode == "local":
        return await run_local_sam_inference(bbox)
    else:
        # Agar .env mein typo ho gaya (e.g. "Colab" ya "clab"), turant
        # pakad lo — silently galat engine chalne se behtar hai clean crash.
        raise SamEngineError(
            f"Invalid PROCESSING_MODE='{settings.PROCESSING_MODE}' in .env. "
            "Allowed values: 'colab' or 'local'."
        )