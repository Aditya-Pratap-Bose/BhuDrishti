"""
app/schemas/parcel.py
-----------------------
Do kaam is file mein:
  1. BBoxRequest  -> Frontend (Leaflet) se aane wale rectangle (bbox)
     ko validate karta hai, taaki galat/dangerous input Colab GPU
     tak kabhi pahunche hi nahi.
  2. ParcelGeoJSONResponse -> Backend jo final jawab Leaflet ko bhejega,
     uska exact shape define karta hai (blueprint ke GeoJSON format
     se hu-ba-hu match karte hue).

MINDSET: Ye file "bouncer at the club" hai. Andar kaun aa sakta hai
(valid bbox) aur kaun nahi (bahut bada/chhota/ulta) — sab yahin decide
hota hai, request Colab tak pahunchne se pehle.
"""

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------
# CONSTANTS — inko tune karna ho toh sirf yahan badlo, poori file mein
# kahin hardcoded number nahi hai.
# ---------------------------------------------------------------------

# 1 degree latitude ~= 111.32 km hamesha (Earth ke kisi bhi jagah pe
# ye almost constant rehta hai, kyunki latitude lines equally spaced hain).
METERS_PER_DEGREE_LAT = 111_320.0

# Area limits — GPU crash aur empty-STAC-results dono se bachne ke liye.
MAX_AREA_SQ_METERS = 5_000_000     # 5 sq km ceiling
MIN_AREA_SQ_METERS = 1_000         # ~1000 sq m floor (roughly 1-2 ghar)


class BBoxRequest(BaseModel):
    """
    Officer Leaflet map pe zoom karke jo rectangle draw karega,
    uske 4 corners yahan aayenge.

    NOTE: Naming convention (min_lon, min_lat, max_lon, max_lat) jaan-bujh
    ke explicit rakhi hai — sirf "bbox: list[float]" nahi, kyunki
    list mein order galat hone ka risk hota hai (kaunsa index kya hai,
    bhoolna aasan hai). Named fields self-documenting hain.
    """

    min_lon: float = Field(..., description="Rectangle ka left edge (West)")
    min_lat: float = Field(..., description="Rectangle ka bottom edge (South)")
    max_lon: float = Field(..., description="Rectangle ka right edge (East)")
    max_lat: float = Field(..., description="Rectangle ka top edge (North)")

    @model_validator(mode="after")
    def validate_bbox(self) -> "BBoxRequest":
        """
        Pydantic v2 ka model_validator(mode="after") — matlab pehle sab
        4 fields individually valid float ban chuke hain, ab humein
        unko EK SAATH check karna hai (kyunki "area" ek single field ka
        property nahi hai, chaaron ka combined result hai).

        Teen checks, isi order mein (order matter karta hai — pehle
        sabse basic cheez check karo, phir complex):
        """

        # --------------------------------------------------------
        # CHECK 1: Coordinate inversion
        # --------------------------------------------------------
        # Agar officer ne rectangle "ulta" drag kiya (right-to-left ya
        # bottom-to-top), toh min > max ho sakta hai. Bina is check ke,
        # neeche ka area-calculation negative ya galat number dega,
        # aur STAC API ko bhi ulta bbox samajh nahi aayega.
        if self.min_lon >= self.max_lon:
            raise ValueError(
                "Bbox invalid: min_lon, max_lon se chota hona chahiye. "
                "(Lagta hai rectangle ulti direction mein draw hua — "
                "left se right drag karke dobara try karein.)"
            )
        if self.min_lat >= self.max_lat:
            raise ValueError(
                "Bbox invalid: min_lat, max_lat se chota hona chahiye. "
                "(Rectangle bottom se top drag karke dobara try karein.)"
            )

        # --------------------------------------------------------
        # CHECK 2: Real-world sanity range
        # --------------------------------------------------------
        # Longitude -180 se +180 ke bahar, ya Latitude -90 se +90 ke
        # bahar — ye Earth pe exist hi nahi karta. Agar frontend mein
        # koi bug ho aur galti se swapped lat/lon bhej de, ye pakड़ लेगा.
        for value, name in [
            (self.min_lon, "min_lon"), (self.max_lon, "max_lon")
        ]:
            if not (-180.0 <= value <= 180.0):
                raise ValueError(f"{name}={value} invalid hai. Range: -180 to 180.")
        for value, name in [
            (self.min_lat, "min_lat"), (self.max_lat, "max_lat")
        ]:
            if not (-90.0 <= value <= 90.0):
                raise ValueError(f"{name}={value} invalid hai. Range: -90 to 90.")

        # --------------------------------------------------------
        # CHECK 3: Area ceiling & floor (the OOM-crash guard)
        # --------------------------------------------------------
        # Yahan hi wo "cosine correction" wala trick use ho raha hai
        # jo humne discuss kiya tha. Simple deduction (max_lon - min_lon)
        # sirf DEGREES ka fark deta hai, METERS ka nahi — aur 21°N
        # (Raipur) pe 1 degree longitude, 1 degree latitude jitni
        # doori cover nahi karta (Earth gol hai, poles ki taraf
        # longitude lines paas aati hain — equator pe sabse door hoti hain).
        #
        # Formula: meters-per-degree-longitude = meters-per-degree-latitude
        #          * cos(latitude in radians)
        avg_lat_rad = math.radians((self.min_lat + self.max_lat) / 2)
        meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(avg_lat_rad)

        width_meters = (self.max_lon - self.min_lon) * meters_per_degree_lon
        height_meters = (self.max_lat - self.min_lat) * METERS_PER_DEGREE_LAT
        area_sq_meters = width_meters * height_meters

        if area_sq_meters > MAX_AREA_SQ_METERS:
            raise ValueError(
                f"Bbox bahut bada hai ({area_sq_meters / 1_000_000:.2f} sq km). "
                f"Maximum allowed: {MAX_AREA_SQ_METERS / 1_000_000:.1f} sq km. "
                "Chhota area select karein — bada area Colab GPU crash "
                "kar sakta hai (out-of-memory)."
            )
        if area_sq_meters < MIN_AREA_SQ_METERS:
            raise ValueError(
                f"Bbox bahut chhota hai ({area_sq_meters:.0f} sq m). "
                f"Minimum required: {MIN_AREA_SQ_METERS} sq m. "
                "Itne chhote area mein satellite imagery (Sentinel-2, "
                "10m/pixel) se koi useful parcel detect nahi ho payega."
            )

        return self


# ---------------------------------------------------------------------
# OUTPUT SCHEMAS — blueprint ke GeoJSON format se exactly match
# ---------------------------------------------------------------------

class ParcelProperties(BaseModel):
    """Har detected parcel ke non-geometric attributes."""
    ulpin: str
    area_sqm: float
    perimeter_m: float
    land_use: str = "Unclassified"


class ParcelGeometry(BaseModel):
    """
    GeoJSON spec ke hisaab se geometry ka shape. type hamesha
    "Polygon" hoga humare case mein (Literal se enforce kiya hai —
    galti se koi aur string nahi ja sakta).
    """
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]
    # Structure: [ [ [lon, lat], [lon, lat], ... ] ]
    # Outer list = polygon rings (hum sirf 1 ring use karenge, koi hole nahi)
    # Middle list = us ring ke saare points
    # Inner list = [longitude, latitude] pair


class ParcelFeature(BaseModel):
    """Ek single detected parcel = ek GeoJSON Feature."""
    type: Literal["Feature"] = "Feature"
    properties: ParcelProperties
    geometry: ParcelGeometry


class ParcelGeoJSONResponse(BaseModel):
    """
    Poora response jo /process-bbox endpoint se wapas jayega.
    Leaflet.js `L.geoJSON(response)` seedha isi format ko samajhta hai —
    koi transformation frontend mein nahi karni padegi.
    """
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ParcelFeature]