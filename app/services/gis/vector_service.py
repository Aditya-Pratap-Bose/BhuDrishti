"""
app/services/gis/vector_service.py
------------------------------------
Pure geometry math — no HTTP, no DB session, no AI calls. Sirf Shapely +
pyproj se polygon operations. Ye file kabhi FastAPI ya SQLAlchemy import
nahi karegi — isse tu isko kal kisi CLI script ya batch job mein bhi
reuse kar sakta hai bina poore app ko import kiye.

MINDSET: Jab bhi koi GeoJSON polygon humare system mein aata hai — chahe
Colab se ho ya Leaflet-Draw editing se — ye file uska "translator +
inspector" hai:
  1. Translator: GeoJSON coordinates <-> Shapely Polygon object
  2. Inspector: Kya geometry valid hai? Area/perimeter kitna hai asal
     metric units (meters) mein?
"""

import logging
from functools import lru_cache

from pyproj import Transformer
from shapely.geometry import Polygon, shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import make_valid

from app.schemas.parcel import ParcelGeometry

logger = logging.getLogger("bhudrishti.vector_service")

# Chhattisgarh / Raipur / SSIPMT test area UTM zone. Agar kal koi doosre
# state mein deploy karna ho, ye single constant badalni hogi — poori
# file mein kahin aur UTM number hardcoded nahi hai.
DEFAULT_UTM_EPSG = 32643


class InvalidGeometryError(Exception):
    """Jab koi polygon itna corrupt ho ki fix bhi na ho sake (e.g. sirf 2 points, ya empty)."""
    pass


@lru_cache(maxsize=8)
def _get_transformer(source_epsg: int, target_epsg: int) -> Transformer:
    """
    Transformer banana thoda expensive hai (CRS database lookup) — cache
    kar liya taaki har request pe dobara na banana pade.
    """
    return Transformer.from_crs(
        f"EPSG:{source_epsg}", f"EPSG:{target_epsg}", always_xy=True
    )
    # always_xy=True CRITICAL hai — bina isके pyproj kabhi kabhi (lat, lon)
    # order expect karta hai instead of (lon, lat), jo silently sab
    # coordinates ko swap kar deta hai. Polygon ekdum galat jagah teleport
    # ho jaata (Raipur se kahin aur). Ye sabse khaufnaak kism ka GIS bug
    # hai kyunki crash nahi karta, bas chupke se galat answer deta hai.


def geometry_to_shapely(geometry: ParcelGeometry) -> Polygon:
    """GeoJSON coordinates ko ek real Shapely Polygon object mein badalta hai."""
    geojson_dict = {"type": geometry.type, "coordinates": geometry.coordinates}
    try:
        polygon = shape(geojson_dict)
    except Exception as e:
        raise InvalidGeometryError(f"GeoJSON coordinates se valid geometry nahi bani: {e}")

    if polygon.is_empty:
        raise InvalidGeometryError("Polygon empty hai — koi area nahi hai isme.")

    return polygon


def shapely_to_geometry(polygon: BaseGeometry) -> ParcelGeometry:
    """Wapas Shapely Polygon ko humare Pydantic ParcelGeometry format mein convert karta hai."""
    geojson_dict = mapping(polygon)
    return ParcelGeometry(type="Polygon", coordinates=geojson_dict["coordinates"])


def ensure_valid_polygon(polygon: Polygon) -> Polygon:
    """
    THE SNEAKY BUG THIS PREVENTS: Jab officer Leaflet-Draw se ek AI-detected
    polygon ko manually reshape karta hai, aasani se ek "self-intersecting"
    (figure-8 jaisi) shape ban sakti hai. PostGIS aisi geometry insert karne
    se seedha mana kar dega — ya agar ho bhi jaaye, `.area` silently galat
    number dega (bina kisi error ke). Isliye save hone se pehle hi fix karo.
    """
    if polygon.is_valid:
        return polygon

    logger.warning("Invalid polygon mila — auto-fixing via make_valid().")
    fixed = make_valid(polygon)

    if fixed.geom_type == "Polygon":
        return fixed
    elif fixed.geom_type in ("MultiPolygon", "GeometryCollection"):
        # Sabse bada polygon piece rakho, baaki chhote fragments almost
        # hamesha floating-point noise hote hain, real land nahi.
        candidates = [g for g in getattr(fixed, "geoms", []) if g.geom_type == "Polygon"]
        if not candidates:
            raise InvalidGeometryError(
                "Polygon itna corrupt tha ki fix karne ke baad bhi koi "
                "valid Polygon piece nahi bacha."
            )
        return max(candidates, key=lambda g: g.area)
    else:
        raise InvalidGeometryError(
            f"make_valid() ne unexpected geometry type diya: {fixed.geom_type}"
        )


def calculate_area_and_perimeter(
    polygon: Polygon, utm_epsg: int = DEFAULT_UTM_EPSG
) -> tuple[float, float]:
    """
    IMPORTANT PRINCIPLE: Hum kabhi bhi client se aaya area_sqm/perimeter_m
    "as-is" trust karke DB mein save nahi karte — SERVER khud recompute
    karta hai final geometry se, kyunki ye ek LEGAL RECORD hai. Agar
    officer polygon reshape kare, purana number ab stale ho chuka hai.
    Single source of truth hamesha geometry hi rehti hai.

    Degrees (EPSG:4326) mein `.area` lena meaningless hai — curved earth
    par unequal distances represent karta hai. Isliye flat, metric UTM
    projection mein transform karke hi area/perimeter nikaalte hain.
    """
    transformer = _get_transformer(4326, utm_epsg)
    utm_polygon = transform(transformer.transform, polygon)

    area_sqm = round(utm_polygon.area, 2)
    perimeter_m = round(utm_polygon.length, 2)
    return area_sqm, perimeter_m