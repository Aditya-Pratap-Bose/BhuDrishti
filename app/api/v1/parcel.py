"""
app/api/v1/parcel.py
----------------------
Saved-parcel CRUD.
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
    ParcelAttributeUpdateRequest,
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
    polygon = to_shape(parcel.geom)
    geometry = shapely_to_geometry(polygon)
    return SavedParcelFeature(
        properties=SavedParcelProperties(
            ulpin=parcel.ulpin,
            area_sqm=float(parcel.area_sqm),
            perimeter_m=float(parcel.perimeter_m),
            land_use=parcel.land_use_type,
            owner_name=parcel.owner_name,
            id=parcel.id,
            created_at=parcel.created_at,
        ),
        geometry=geometry,
    )


@router.post("/save", response_model=BulkSaveResult, status_code=status.HTTP_201_CREATED)
def save_parcels(
    payload: ParcelGeoJSONResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

        area_sqm, perimeter_m = calculate_area_and_perimeter(polygon)

        parcel = Parcel(
            ulpin=feature.properties.ulpin,
            area_sqm=area_sqm,
            perimeter_m=perimeter_m,
            land_use_type=feature.properties.land_use,
            owner_name=feature.properties.owner_name,
            geom=from_shape(polygon, srid=4326),
            created_by=current_user.id,
        )

        try:
            with db.begin_nested():
                db.add(parcel)
                db.flush()
        except IntegrityError:
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


@router.get("", response_model=SavedParcelGeoJSONResponse)
def list_parcels(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bbox_values = [min_lon, min_lat, max_lon, max_lat]
    bbox_given = [v is not None for v in bbox_values]

    if any(bbox_given) and not all(bbox_given):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bbox filter ke liye min_lon, min_lat, max_lon, max_lat sabhi 4 dene honge — ya koi bhi mat do.",
        )

    query = db.query(Parcel)

    if all(bbox_given):
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = query.filter(func.ST_Intersects(Parcel.geom, envelope))

    parcels = query.order_by(Parcel.created_at.desc()).offset(offset).limit(limit).all()

    return SavedParcelGeoJSONResponse(features=[_parcel_to_feature(p) for p in parcels])


@router.get("/{parcel_id}", response_model=SavedParcelFeature)
def get_parcel(
    parcel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel {parcel_id} nahi mila.")
    return _parcel_to_feature(parcel)


@router.patch("/{parcel_id}", response_model=SavedParcelFeature)
def update_parcel_attributes(
    parcel_id: uuid.UUID,
    payload: ParcelAttributeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Attribute Inspector drawer ka 'Save changes' — land_use aur owner_name
    dono (ya sirf ek) update kar sakta hai ek hi call mein.

    NOTE: purana route yahan tha '/parcels/{id}/land-use' — ab isi route
    (bare '/{parcel_id}') se dono fields update hoti hain. Frontend already
    naye route se hi call karta hai.
    """
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel {parcel_id} nahi mila.")

    if payload.land_use_type is not None:
        parcel.land_use_type = payload.land_use_type
    if payload.owner_name is not None:
        parcel.owner_name = payload.owner_name

    db.commit()
    db.refresh(parcel)
    return _parcel_to_feature(parcel)


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(
    parcel_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "tehsildar")),
    db: Session = Depends(get_db),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel {parcel_id} nahi mila.")

    db.delete(parcel)
    db.commit()
    logger.info(f"User {current_user.email} ne parcel {parcel_id} delete kiya.")
    return None