"""
app/services/ulpin_generator.py
--------------------------------
ULPIN generation utilities for land parcel records.

ULPIN is a unique parcel identifier. In a production government workflow this
would be generated according to the official revenue office rules, but for an
MVP this helper keeps it deterministic and auditable.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime


def normalize_code(value: str | int, width: int = 4) -> str:
    """Convert a value into a zero-padded code string."""
    return str(value).strip().upper().replace(" ", "").zfill(width)


def generate_ulpin(
    district_code: str | int,
    village_code: str | int,
    plot_number: str | int,
    year: int | None = None,
    suffix: str | None = None,
) -> str:
    """Generate a deterministic ULPIN string.

    Example output:
        24-0101-0012-2026-AB
    """
    if year is None:
        year = datetime.now().year

    district = normalize_code(district_code, 4)
    village = normalize_code(village_code, 4)
    plot = normalize_code(plot_number, 6)
    year_str = str(year)

    base = f"{district}-{village}-{plot}-{year_str}"
    if suffix:
        suffix_clean = re.sub(r"[^A-Z0-9]", "", str(suffix).upper())
        base = f"{base}-{suffix_clean[:4]}"

    # Add a small checksum to avoid accidental collisions without making the ID
    # unreadable for officers and inspectors.
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:4].upper()
    return f"{base}-{digest}"


def is_valid_ulpin(ulpin: str) -> bool:
    """Basic validation to confirm the identifier is in the expected pattern."""
    if not ulpin or not isinstance(ulpin, str):
        return False
    pattern = r"^[A-Z0-9-]{12,40}$"
    return bool(re.fullmatch(pattern, ulpin))
