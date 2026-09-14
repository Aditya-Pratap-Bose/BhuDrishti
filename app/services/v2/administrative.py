"""Cached India state and district catalog for V2 location search."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from shapely.geometry import shape

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "v2" / "india_districts.geojson"
CATALOG_SOURCE = "GADM 4.1 India level-2 administrative boundaries (cached locally)"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split())


def _identifier(value: Any) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def _load_features() -> tuple[dict[str, Any], ...]:
    if not CATALOG_PATH.is_file():
        raise FileNotFoundError(f"Administrative catalog is missing: {CATALOG_PATH}")
    with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        payload = json.load(catalog_file)
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Administrative catalog contains no features")
    return tuple(features)


def _bbox(feature: dict[str, Any]) -> list[float]:
    min_x, min_y, max_x, max_y = shape(feature["geometry"]).bounds
    return [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)]


def _district_item(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties", {})
    state_id = _identifier(properties.get("GID_1"))
    district_id = _identifier(properties.get("GID_2"))
    state_name = _clean(properties.get("NAME_1"))
    district_name = _clean(properties.get("NAME_2"))
    return {
        "id": district_id,
        "name": district_name,
        "level": "district",
        "state_id": state_id,
        "state_name": state_name,
        "district_id": district_id,
        "district_name": district_name,
        "bbox": _bbox(feature),
    }


@lru_cache(maxsize=1)
def _district_items() -> tuple[dict[str, Any], ...]:
    return tuple(_district_item(feature) for feature in _load_features())


def _matches(name: str, query: str) -> bool:
    return not query or query.casefold() in name.casefold()


def list_states(query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for district in _district_items():
        state_id = district["state_id"]
        state = states.setdefault(
            state_id,
            {
                "id": state_id,
                "name": district["state_name"],
                "level": "state",
                "state_id": state_id,
                "state_name": district["state_name"],
                "bbox": list(district["bbox"]),
            },
        )
        state["bbox"] = [
            min(state["bbox"][0], district["bbox"][0]),
            min(state["bbox"][1], district["bbox"][1]),
            max(state["bbox"][2], district["bbox"][2]),
            max(state["bbox"][3], district["bbox"][3]),
        ]
    return [state for state in sorted(states.values(), key=lambda item: item["name"]) if _matches(state["name"], query)][:limit]


def list_districts(state_id: str, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    normalized_id = state_id.strip().casefold()
    districts = [
        district
        for district in _district_items()
        if district["state_id"].casefold() == normalized_id and _matches(district["name"], query)
    ]
    return sorted(districts, key=lambda item: item["name"])[:limit]


def search_places(query: str, limit: int = 20) -> list[dict[str, Any]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    states = list_states(normalized_query, limit=limit)
    districts = [district for district in _district_items() if _matches(district["name"], normalized_query)]
    return (states + sorted(districts, key=lambda item: item["name"]))[:limit]
