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

import logging

import httpx
# httpx zaroori hai (requests nahi) kyunki ye FastAPI ke async
# route ke andar bina block kiye chal sakta hai. requests use
# karte toh poora server us ek request ke time freeze ho jaata
# (kyunki requests sync/blocking hai) — baaki saare officers ka
# traffic bhi ruk jaata jab tak Colab jawab na de.

from app.core.config import settings

logger = logging.getLogger("bhudrishti.sam_engine")


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
        async with httpx.AsyncClient(timeout=settings.COLAB_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
    except httpx.ConnectError as e:
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
    except httpx.TimeoutException as e:
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
# ENGINE 2: LOCAL INFERENCE (future — abhi skeleton)
# ---------------------------------------------------------------------

async def run_local_sam_inference(bbox: tuple[float, float, float, float]) -> dict:
    """
    FUTURE ENGINE — jab kabhi apna GPU server mile (ya deploy karna ho
    bina Colab dependency ke), yahan wahi Colab notebook ka pipeline
    (SamGeo load -> Sentinel fetch -> mask -> vectorize -> ULPIN)
    directly Python mein import/likha jayega, koi HTTP call nahi.

    Abhi ke liye jaan-bujh ke NotImplementedError raise kar rahe hain —
    isse agar kisi ne galti se .env mein PROCESSING_MODE=local kar diya
    bina is engine ko implement kiye, use clear error milega, silent
    wrong-behaviour nahi.
    """
    raise NotImplementedError(
        "Local SAM inference abhi implement nahi hui hai. "
        "PROCESSING_MODE=colab rakhein .env mein, ya pehle is function "
        "ko implement karein (Colab notebook ka pipeline yahan port karke)."
    )


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