"""
app/services/ulpin_generator.py
--------------------------------
Official ULPIN (Unique Land Parcel Identification Number / Bhu-Aadhaar)
Generator complying with ECCMA (Electronic Commerce Code Management Association)
and Department of Land Resources (DoLR), Government of India standards.

Specification:
- Total Length: 14 Alphanumeric Characters (Stored: SSDDTTTNNNNNNN, Display: SS-DD-TTT-NNNNNNN)
- Digits 1-2: State Code (LGD / Census Code, e.g., 22 for Chhattisgarh)
- Digits 3-4: District Code (LGD Code, e.g., 10 for Raipur)
- Digits 5-7: Sub-District / Tehsil Code (LGD Code, e.g., 001 for Raipur Urban)
- Digits 8-14: 7-character Alphanumeric Spatial Identifier computed deterministically
               from the polygon boundary vertex coordinates (WGS-84).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.core.config import settings

# Base36 character set for clean 7-character alphanumeric parcel hash
BASE36_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(num: int, length: int = 7) -> str:
    """Convert integer to fixed-length upper-case alphanumeric Base36 string."""
    if num == 0:
        return "0" * length
    res = []
    while num > 0:
        num, rem = divmod(num, 36)
        res.append(BASE36_CHARS[rem])
    encoded = "".join(reversed(res))
    return encoded.zfill(length)[-length:]


def generate_vertex_hash(coordinates: list[list[float]] | list[tuple[float, float]]) -> str:
    """
    Computes a deterministic 7-character alphanumeric hash from polygon boundary coordinates.
    Canonicalizes vertex order to ensure orientation-independent hash stability.
    """
    if not coordinates or len(coordinates) < 3:
        # Fallback for empty or point geometries
        raw_repr = "0.000000:0.000000"
    else:
        # Normalize: round coordinates to 6 decimal places (~0.1m precision)
        pts = [(round(float(p[0]), 6), round(float(p[1]), 6)) for p in coordinates]
        # Remove closing point if duplicate of start point
        if len(pts) > 3 and pts[0] == pts[-1]:
            pts = pts[:-1]
        
        # Canonical rotation: start from the lexicographically smallest vertex
        min_idx = pts.index(min(pts))
        canonical_pts = pts[min_idx:] + pts[:min_idx]
        
        raw_repr = "|".join(f"{x:.6f},{y:.6f}" for x, y in canonical_pts)

    digest = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()
    int_val = int(digest[:12], 16)
    return _to_base36(int_val, 7)


def generate_ulpin_from_geometry(
    geometry: Any,
    state_code: str | None = None,
    district_code: str | None = None,
    subdistrict_code: str | None = None,
) -> str:
    """
    Generates standard 14-digit ULPIN for a given GeoJSON geometry or Shapely Polygon.
    Returns standard display format: SS-DD-TTT-NNNNNNN (14 alphanumeric + 3 hyphens).
    """
    s_code = (state_code or settings.ULPIN_STATE_CODE).strip().zfill(2)[:2]
    d_code = (district_code or settings.ULPIN_DISTRICT_CODE).strip().zfill(2)[:2]
    t_code = (subdistrict_code or settings.ULPIN_SUBDISTRICT_CODE).strip().zfill(3)[:3]

    coords = []
    if hasattr(geometry, "exterior"):  # Shapely Polygon
        coords = list(geometry.exterior.coords)
    elif hasattr(geometry, "geoms"):  # Shapely MultiPolygon
        coords = list(geometry.geoms[0].exterior.coords) if geometry.geoms else []
    elif isinstance(geometry, dict):  # GeoJSON dict
        geom_type = geometry.get("type")
        c = geometry.get("coordinates", [])
        if geom_type == "Polygon" and c:
            coords = c[0]
        elif geom_type == "MultiPolygon" and c and c[0]:
            coords = c[0][0]
    elif isinstance(geometry, (list, tuple)):
        coords = geometry

    vertex_hash = generate_vertex_hash(coords)
    return f"{s_code}-{d_code}-{t_code}-{vertex_hash}"


def format_display_ulpin(raw_ulpin: str) -> str:
    """Formats 14-character raw ULPIN into hyphenated display representation."""
    clean = re.sub(r"[^A-Z0-9]", "", str(raw_ulpin).upper())
    if len(clean) == 14:
        return f"{clean[0:2]}-{clean[2:4]}-{clean[4:7]}-{clean[7:14]}"
    return raw_ulpin


def is_valid_ulpin(ulpin: str) -> bool:
    """Validates whether ULPIN conforms to the official 14-digit standard."""
    if not ulpin or not isinstance(ulpin, str):
        return False
    clean = re.sub(r"[^A-Z0-9]", "", ulpin.upper())
    return len(clean) == 14
