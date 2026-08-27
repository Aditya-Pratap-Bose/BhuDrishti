"""
app/api/v1/satellite.py
--------------------------
Ye file "waiter" hai — Leaflet frontend se order (bbox) leta hai,
kitchen (sam_engine.py) ko bhejta hai, aur plate (GeoJSON) saja ke
wapas la ke deta hai. Isko khud kabhi pata nahi hota ki kitchen mein
Colab chal raha hai ya local GPU — wo bas `process_bbox()` call karta
hai aur trust karta hai.

MINDSET: Is layer ka EK hi kaam hai — HTTP duniya (requests, status
codes, auth) aur business-logic duniya (sam_engine) ke beech translator
banna. Isme koi AI ya GIS logic NAHI likhna — wo sab neeche services/
mein rehta hai. Agar kal iske andar geometry math dikhe, samajh lena
galat jagah code likha gaya hai.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.parcel import BBoxRequest, ParcelGeoJSONResponse
from app.services.ai.sam_engine import (
    process_bbox,
    ColabUnreachableError,
    ColabTimeoutError,
    ColabProcessingError,
    SamEngineError,
)

logger = logging.getLogger("bhudrishti.satellite")

router = APIRouter(prefix="/satellite", tags=["Satellite Processing"])


@router.post("/process-bbox", response_model=ParcelGeoJSONResponse)
async def process_satellite_bbox(
    payload: BBoxRequest,
    current_user: User = Depends(get_current_user),
):
    """
    MAIN ENDPOINT — Leaflet frontend ye hit karega jab officer
    "Detect Parcels" button dabayega apne drawn rectangle ke saath.

    Flow:
      1. `payload: BBoxRequest` -> FastAPI khud hi Pydantic se validate
         kar chuka hoga is line tak pahunchne se pehle. Agar bbox
         invalid tha (ulta, bahut bada/chhota, out-of-range), user ko
         yahan tak pahunchne se pehle hi clean 422 mil chuka hoga —
         humein manually kuch check nahi karna is function ke andar.
      2. `current_user` -> sirf logged-in officers hi ye endpoint use
         kar sakte hain. Isse random log (anonymous) requests Colab
         GPU ka time waste nahi kar sakte.
      3. `process_bbox()` -> saara heavy lifting sam_engine karega,
         hum bas result ka wait karte hain.
      4. Exceptions -> har SamEngineError type ko apne sahi HTTP status
         code mein map karte hain, taaki frontend ko pata chale
         "user ki galti hai (retry karo)" vs "hamari taraf ka problem
         hai (thodi der baad try karo)".
    """
    bbox_tuple = (payload.min_lon, payload.min_lat, payload.max_lon, payload.max_lat)

    logger.info(
        f"User {current_user.email} ne bbox process request bheja: {bbox_tuple}"
    )

    try:
        raw_geojson = await process_bbox(bbox_tuple)

    except ColabUnreachableError as e:
        # 503 = "Service Unavailable" — humari taraf ka temporary
        # problem hai (tunnel down), user ki galti nahi. Frontend
        # isko dekh ke "AI engine offline hai, thodi der mein try
        # karein" jaisa message dikha sakta hai, retry button ke saath.
        logger.error(f"Colab unreachable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    except ColabTimeoutError as e:
        # 504 = "Gateway Timeout" — waiter ne kitchen se poocha, kitchen
        # itni der tak chup rahi ki humne haar maan li. User ko bolna
        # hai chhota bbox try kare.
        logger.error(f"Colab timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )

    except ColabProcessingError as e:
        # 422 = "Unprocessable Entity" — request format toh sahi tha,
        # lekin AI pipeline khud process nahi kar paayi (e.g. is bbox
        # mein Sentinel-2 ki koi cloud-free image nahi mili). Ye
        # "aapka bbox theek hai lekin data available nahi" wala case hai.
        logger.error(f"Colab processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    except SamEngineError as e:
        # Catch-all safety net — agar koi naya error type future mein
        # add ho aur specific handling bhoolein, ye generic 500 dega
        # instead of raw traceback (jo main.py ka global handler bhi
        # anyway pakad leta, lekin yahan specific message ke saath
        # zyada useful hai).
        logger.error(f"Unexpected SAM engine error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # ---------------------------------------------------------------
    # Colab se aaya raw dict already blueprint-shaped GeoJSON hai,
    # lekin hum isko explicitly ParcelGeoJSONResponse se validate/parse
    # karke bhejte hain — ye ek extra safety layer hai. Agar Colab
    # notebook mein kal koi field add/remove ho jaaye bina humein
    # bataye, ye yahin pakड़ लेगा (clean 500 error ke saath) instead of
    # ek malformed GeoJSON Leaflet tak bhej ke silently map crash karne ke.
    # ---------------------------------------------------------------
    try:
        validated_response = ParcelGeoJSONResponse.model_validate(raw_geojson)
    except Exception as e:
        logger.error(f"Colab response GeoJSON schema se match nahi hua: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI engine se aaya data expected format mein nahi tha. Team ko bata diya gaya hai.",
        )

    logger.info(
        f"Success: {len(validated_response.features)} parcels return kiye "
        f"user {current_user.email} ko."
    )
    return validated_response