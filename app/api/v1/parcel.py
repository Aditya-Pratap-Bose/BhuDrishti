"""
app/api/v1/parcel.py
----------------------
Saved-parcel CRUD. Ye file "permanent land registry office" hai —
satellite.py sirf AI se boundaries nikalta hai (temporary, session
tak), lekin ye file un boundaries ko HAMESHA ke liye Postgres mein
lock karti hai.

MINDSET: Do responsibilities strictly alag rakhi hain: satellite.py
"detect karo" (read-only AI call), parcel.py "record karo" (permanent
DB writes). Isse kal agar tu AI engine badal de (Colab se kisi aur
provider pe), ye file bilkul touch nahi karni padegi.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user, require_role
from app.core.database import get_db
from app.models.parcel import Parcel
from app.models.user import User
from app.schemas.parcel import (
    BulkSaveResult,
    LandUseUpdateRequest,
    ParcelGeoJSONResponse,
    SavedParcelFeature,
    SavedParcelGeoJSONResponse,
    SavedParcelProperties,
)
from app.services.gis.vector_service import (
    InvalidGeometryError,
    calculate_area_and_perimeter,
    ensure_valid_polygon,
    geometry_to_shapely,
    shapely_to_geometry,
)

logger = logging.getLogger("bhudrishti.parcel")

router = APIRouter(prefix="/parcels", tags=["Parcels"])


def _parcel_to_feature(parcel: Parcel) -> SavedParcelFeature:
    """
    DB row -> API response translator. Isko ek jagah rakha hai kyunki
    4 alag endpoints (save, list, get, update) ko yehi conversion
    chahiye — copy-paste karte toh kal ek jagah bug fix karke doosri
    jagah bhool jaate.
    """
    polygon = to_shape(parcel.geom)
    geometry = shapely_to_geometry(polygon)
    return SavedParcelFeature(
        properties=SavedParcelProperties(
            ulpin=parcel.ulpin,
            # NOTE: DB column Numeric(14,2) hone ki wajah se Python me
            # Decimal type aata hai — Pydantic float field ke liye
            # explicit float() cast zaroori hai, warna serialization
            # mein weird ya inconsistent behaviour aa sakta hai.
            area_sqm=float(parcel.area_sqm),
            perimeter_m=float(parcel.perimeter_m),
            land_use=parcel.land_use_type,
            id=parcel.id,
            created_at=parcel.created_at,
        ),
        geometry=geometry,
    )


# ---------------------------------------------------------------------
# CREATE — bulk save from AI output (or edited Leaflet-Draw output)
# ---------------------------------------------------------------------

@router.post("/save", response_model=BulkSaveResult, status_code=status.HTTP_201_CREATED)
def save_parcels(
    payload: ParcelGeoJSONResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Officer "Save to Registry" button dabayega jab wo Colab se aaye
    (aur maybe reshape kiye) parcels se satisfied ho jaaye.

    GOTCHA HANDLED: Agar 37 parcels bhejo aur unme se 5 already DB mein
    hain (duplicate ULPIN), naive code poori transaction abort kar deta
    aur 37 ke 37 lost ho jaate. SAVEPOINT (db.begin_nested()) se sirf
    wo 5 skip hote hain, baaki 32 fine save hote hain.
    """
    saved_features: list[SavedParcelFeature] = []
    duplicate_ulpins: list[str] = []

    for feature in payload.features:
        try:
            polygon = geometry_to_shapely(feature.geometry)
            polygon = ensure_valid_polygon(polygon)
        except InvalidGeometryError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"ULPIN {feature.properties.ulpin}: {e}",
            )

        # Server khud area/perimeter recompute karta hai — client ka
        # number kabhi trust nahi karte (legal record hai ye).
        area_sqm, perimeter_m = calculate_area_and_perimeter(polygon)

        parcel = Parcel(
            ulpin=feature.properties.ulpin,
            area_sqm=area_sqm,
            perimeter_m=perimeter_m,
            land_use_type=feature.properties.land_use,
            geom=from_shape(polygon, srid=4326),
            created_by=current_user.id,
        )

        try:
            with db.begin_nested():  # SAVEPOINT — sirf isi insert ko isolate karta hai
                db.add(parcel)
                db.flush()
        except IntegrityError:
            # Duplicate ulpin (unique constraint todi) — skip karo,
            # baaki batch pe koi asar nahi padega.
            logger.warning(f"Duplicate ULPIN skip kiya: {feature.properties.ulpin}")
            duplicate_ulpins.append(feature.properties.ulpin)
            continue

        saved_features.append(_parcel_to_feature(parcel))

    db.commit()

    logger.info(
        f"User {current_user.email} ne {len(saved_features)} parcels save kiye, "
        f"{len(duplicate_ulpins)} duplicates skip hue."
    )

    return BulkSaveResult(
        saved_count=len(saved_features),
        duplicate_count=len(duplicate_ulpins),
        duplicate_ulpins=duplicate_ulpins,
        saved_parcels=SavedParcelGeoJSONResponse(features=saved_features),
    )


# ---------------------------------------------------------------------
# READ — list (with optional map-viewport bbox filter) + single lookup
# ---------------------------------------------------------------------

@router.get("", response_model=SavedParcelGeoJSONResponse)
def list_parcels(
    min_lon: float | None = Query(None, description="Viewport filter — bottom-left corner"),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None, description="Viewport filter — top-right corner"),
    max_lat: float | None = Query(None),
    limit: int = Query(500, ge=1, le=2000, description="Ek baar mein max kitne parcels"),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GOTCHA HANDLED: Agar kal poore Chhattisgarh state ka data DB mein
    ho (lakhs of parcels), aur Leaflet map poora table fetch kare, ya
    toh browser tab crash hoga ya request minutes le lega. Isliye:
      1. `limit` hard-capped hai 2000 pe (default 500).
      2. Bbox filter diya gaya hai — Leaflet apna current visible map
         area bhejega, aur hum PostGIS ke ST_Intersects + GIST spatial
         index (blueprint mein already defined) use karke SIRF wahi
         parcels fetch karte hain jo abhi screen pe dikhne chahiye.
    """
    bbox_values = [min_lon, min_lat, max_lon, max_lat]
    bbox_given = [v is not None for v in bbox_values]

    if any(bbox_given) and not all(bbox_given):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Bbox filter ke liye min_lon, min_lat, max_lon, max_lat "
                "sabhi 4 dene honge — ya koi bhi mat do (poori list milegi)."
            ),
        )

    query = db.query(Parcel)

    if all(bbox_given):
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = query.filter(func.ST_Intersects(Parcel.geom, envelope))

    parcels = (
        query.order_by(Parcel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return SavedParcelGeoJSONResponse(features=[_parcel_to_feature(p) for p in parcels])


@router.get("/{parcel_id}", response_model=SavedParcelFeature)
def get_parcel(
    parcel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcel {parcel_id} nahi mila.",
        )
    return _parcel_to_feature(parcel)


# ---------------------------------------------------------------------
# UPDATE — officer classifies land use (Residential / Agricultural / etc.)
# ---------------------------------------------------------------------

@router.patch("/{parcel_id}/land-use", response_model=SavedParcelFeature)
def update_land_use(
    parcel_id: uuid.UUID,
    payload: LandUseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcel {parcel_id} nahi mila.",
        )

    parcel.land_use_type = payload.land_use_type
    db.commit()
    db.refresh(parcel)

    return _parcel_to_feature(parcel)


# ---------------------------------------------------------------------
# DELETE — sirf Admin/Tehsildar (Surveyor ko official record delete
# karne ki permission nahi — government audit-trail ka basic principle)
# ---------------------------------------------------------------------

@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(
    parcel_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "tehsildar")),
    db: Session = Depends(get_db),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcel {parcel_id} nahi mila.",
        )

    db.delete(parcel)
    db.commit()
    logger.info(f"User {current_user.email} ne parcel {parcel_id} delete kiya.")
    return None