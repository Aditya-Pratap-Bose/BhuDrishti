"""
app/schemas/parcel.py
-----------------------
Teen kaam is file mein:
  1. BBoxRequest  -> Frontend se aane wale rectangle ko validate karta hai.
  2. ParcelGeoJSONResponse -> AI pipeline (Colab/local) ka raw output shape.
  3. Saved-parcel schemas -> DB mein save/fetch hone wale parcels ka shape.

MINDSET: Ye file "bouncer at the club" hai. Andar kaun aa sakta hai
aur kis format mein — sab yahin decide hota hai.
"""

import math
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


METERS_PER_DEGREE_LAT = 111_320.0
MAX_AREA_SQ_METERS = 5_000_000
MIN_AREA_SQ_METERS = 1_000


class BBoxRequest(BaseModel):
    min_lon: float = Field(..., description="Rectangle ka left edge (West)")
    min_lat: float = Field(..., description="Rectangle ka bottom edge (South)")
    max_lon: float = Field(..., description="Rectangle ka right edge (East)")
    max_lat: float = Field(..., description="Rectangle ka top edge (North)")

    source_type: Literal["esri", "sentinel", "openaerialmap", "osm", "isro_bhuvan"] = "esri"
    # "esri": High-resolution Esri World Imagery (sub-meter, sharp boundaries).
    # "sentinel": 10m Sentinel-2 STAC imagery (macro / agricultural).
    # "openaerialmap": Crowd-sourced drone/aerial imagery.
    # "osm": OpenStreetMap street/cadastral tile layout.
    # "isro_bhuvan": Mock NSDI Cartosat-3 locked endpoint.

    @model_validator(mode="after")
    def validate_bbox(self) -> "BBoxRequest":
        if self.min_lon >= self.max_lon:
            raise ValueError(
                "Bbox invalid: min_lon, max_lon se chota hona chahiye. "
                "(Lagta hai rectangle ulti direction mein draw hua.)"
            )
        if self.min_lat >= self.max_lat:
            raise ValueError("Bbox invalid: min_lat, max_lat se chota hona chahiye.")

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
# RAW AI OUTPUT SCHEMAS
# ---------------------------------------------------------------------

class ParcelProperties(BaseModel):
    ulpin: str
    area_sqm: float
    perimeter_m: float
    land_use: str = "Unclassified"
    owner_name: str | None = None


class ParcelGeometry(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class ParcelFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: ParcelProperties
    geometry: ParcelGeometry


class ParcelGeoJSONResponse(BaseModel):
    """
    Colab/local se jo raw response aata hai — aur yehi shape /parcels/save
    ke REQUEST BODY ke roop mein bhi reuse hoti hai.
    """
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ParcelFeature]

    # Raw imagery preview — Leaflet ImageOverlay ke liye. Optional isliye
    # hai kyunki purana Colab notebook (agar update na kiya ho) ye fields
    # nahi bhejega — response phir bhi valid rahega, bas preview layer
    # frontend pe silently skip ho jaayegi.
    preview_image_base64: str | None = None
    preview_bounds: list[float] | None = None  # [min_lon, min_lat, max_lon, max_lat]


# ---------------------------------------------------------------------
# SAVED PARCEL SCHEMAS
# ---------------------------------------------------------------------

class SavedParcelProperties(ParcelProperties):
    id: uuid.UUID
    created_at: datetime


class SavedParcelFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: SavedParcelProperties
    geometry: ParcelGeometry


class SavedParcelGeoJSONResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SavedParcelFeature]


class BulkSaveResult(BaseModel):
    saved_count: int
    duplicate_count: int
    duplicate_ulpins: list[str]
    saved_parcels: SavedParcelGeoJSONResponse


class ParcelAttributeUpdateRequest(BaseModel):
    """
    Attribute Inspector drawer ka 'Save Changes' — land_use aur/ya
    owner_name update karta hai, ek hi call mein, jo bhi diya ho.
    """
    land_use_type: str | None = Field(default=None, min_length=2, max_length=50)
    owner_name: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ParcelAttributeUpdateRequest":
        if self.land_use_type is None and self.owner_name is None:
            raise ValueError("Kam se kam land_use_type ya owner_name mein se ek dena zaroori hai.")
        return self