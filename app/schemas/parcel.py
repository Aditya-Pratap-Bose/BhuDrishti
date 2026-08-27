"""
app/schemas/parcel.py
-----------------------
Teen kaam is file mein:
  1. BBoxRequest  -> Frontend se aane wale rectangle ko validate karta hai.
  2. ParcelGeoJSONResponse -> AI pipeline (Colab) ka raw output shape.
  3. Saved-parcel schemas -> DB mein save/fetch hone wale parcels ka shape
     (in mein extra fields hain: id, created_at — jo unsaved AI output
     mein nahi hote).

MINDSET: Ye file "bouncer at the club" hai. Andar kaun aa sakta hai
aur kis format mein — sab yahin decide hota hai.
"""

import math
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

METERS_PER_DEGREE_LAT = 111_320.0
MAX_AREA_SQ_METERS = 5_000_000
MIN_AREA_SQ_METERS = 1_000


class BBoxRequest(BaseModel):
    min_lon: float = Field(..., description="Rectangle ka left edge (West)")
    min_lat: float = Field(..., description="Rectangle ka bottom edge (South)")
    max_lon: float = Field(..., description="Rectangle ka right edge (East)")
    max_lat: float = Field(..., description="Rectangle ka top edge (North)")

    @model_validator(mode="after")
    def validate_bbox(self) -> "BBoxRequest":
        if self.min_lon >= self.max_lon:
            raise ValueError(
                "Bbox invalid: min_lon, max_lon se chota hona chahiye. "
                "(Lagta hai rectangle ulti direction mein draw hua.)"
            )
        if self.min_lat >= self.max_lat:
            raise ValueError(
                "Bbox invalid: min_lat, max_lat se chota hona chahiye."
            )

        for value, name in [(self.min_lon, "min_lon"), (self.max_lon, "max_lon")]:
            if not (-180.0 <= value <= 180.0):
                raise ValueError(f"{name}={value} invalid hai. Range: -180 to 180.")
        for value, name in [(self.min_lat, "min_lat"), (self.max_lat, "max_lat")]:
            if not (-90.0 <= value <= 90.0):
                raise ValueError(f"{name}={value} invalid hai. Range: -90 to 90.")

        avg_lat_rad = math.radians((self.min_lat + self.max_lat) / 2)
        meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(avg_lat_rad)

        width_meters = (self.max_lon - self.min_lon) * meters_per_degree_lon
        height_meters = (self.max_lat - self.min_lat) * METERS_PER_DEGREE_LAT
        area_sq_meters = width_meters * height_meters

        if area_sq_meters > MAX_AREA_SQ_METERS:
            raise ValueError(
                f"Bbox bahut bada hai ({area_sq_meters / 1_000_000:.2f} sq km). "
                f"Maximum allowed: {MAX_AREA_SQ_METERS / 1_000_000:.1f} sq km."
            )
        if area_sq_meters < MIN_AREA_SQ_METERS:
            raise ValueError(
                f"Bbox bahut chhota hai ({area_sq_meters:.0f} sq m). "
                f"Minimum required: {MIN_AREA_SQ_METERS} sq m."
            )

        return self


# ---------------------------------------------------------------------
# RAW AI OUTPUT SCHEMAS (unsaved — matches Colab GeoJSON exactly)
# ---------------------------------------------------------------------

class ParcelProperties(BaseModel):
    ulpin: str
    area_sqm: float
    perimeter_m: float
    land_use: str = "Unclassified"


class ParcelGeometry(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class ParcelFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: ParcelProperties
    geometry: ParcelGeometry


class ParcelGeoJSONResponse(BaseModel):
    """
    Colab se jo raw response aata hai — aur yehi shape hum /parcels/save
    ke REQUEST BODY ke roop mein bhi reuse karte hain (DRY — officer
    Leaflet pe review karke, edit karke, wahi FeatureCollection wapas
    /parcels/save ko bhej dega).
    """
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ParcelFeature]


# ---------------------------------------------------------------------
# SAVED PARCEL SCHEMAS (DB se aane wala data — id + timestamps ke saath)
# ---------------------------------------------------------------------

class SavedParcelProperties(ParcelProperties):
    """
    ParcelProperties se hi inherit kiya (ulpin, area_sqm, perimeter_m,
    land_use sab already aa gaye) — sirf DB-specific fields add kiye.
    """
    id: uuid.UUID
    created_at: datetime


class SavedParcelFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: SavedParcelProperties
    geometry: ParcelGeometry


class SavedParcelGeoJSONResponse(BaseModel):
    """GET /parcels ka response — Leaflet ko seedha L.geoJSON() mein daal sakte ho."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SavedParcelFeature]


class BulkSaveResult(BaseModel):
    """POST /parcels/save ka response — kitne save hue, kitne duplicate skip hue."""
    saved_count: int
    duplicate_count: int
    duplicate_ulpins: list[str]
    saved_parcels: SavedParcelGeoJSONResponse


class LandUseUpdateRequest(BaseModel):
    """Officer ka manual classification — e.g. AI ne 'Unclassified' diya, officer 'Residential Plot' set karta hai."""
    land_use_type: str = Field(min_length=2, max_length=50)