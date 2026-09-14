"""Allowlisted reference cadastral data providers for V2."""

from __future__ import annotations

from typing import Any

import requests

from app.core.config import settings
from app.core.exceptions import ReconciliationError


def _bounded_bbox(bbox: list[float]) -> tuple[float, float, float, float]:
    if len(bbox) != 4:
        raise ReconciliationError("Reference query bbox must contain four coordinates.")
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in bbox)
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ReconciliationError("Reference query bbox must be ordered WGS84 coordinates.")
    if max_lon - min_lon > 0.1 or max_lat - min_lat > 0.1:
        raise ReconciliationError("Reference query bbox is too large; select a smaller AOI.")
    return min_lon, min_lat, max_lon, max_lat


class TelanganaArcGISReferenceProvider:
    """Fetch a bounded Telangana cadastral query from the configured ArcGIS service."""

    provider_id = "telangana_tgrac_arcgis"

    def __init__(self, session: Any = requests):
        self.session = session
        self.url = f"{settings.TELANGANA_ARCGIS_SERVICE_URL.rstrip('/')}/{settings.TELANGANA_ARCGIS_LAYER_ID}/query"

    def search(self, bbox: list[float]) -> dict[str, Any]:
        min_lon, min_lat, max_lon, max_lat = _bounded_bbox(bbox)
        params = {
            "where": "1=1",
            "geometry": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "geojson",
        }
        try:
            response = self.session.get(self.url, params=params, timeout=settings.REFERENCE_PROVIDER_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ReconciliationError("Telangana reference provider could not be reached or returned invalid JSON.") from exc
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise ReconciliationError("Telangana reference provider returned an unsupported geometry response.")
        return {
            "type": "FeatureCollection",
            "features": [self._normalize_feature(feature) for feature in payload["features"]],
            "provider": self.provider_id,
            "source_url": self.url,
        }

    def _normalize_feature(self, feature: dict[str, Any]) -> dict[str, Any]:
        properties = dict(feature.get("properties") or {})
        reference_id = properties.get("reference_id") or properties.get("OBJECTID") or feature.get("id")
        normalized = {
            "type": "Feature",
            "id": str(reference_id) if reference_id is not None else None,
            "geometry": feature.get("geometry"),
            "properties": {
                "reference_id": str(reference_id) if reference_id is not None else None,
                "parcel_number": properties.get("parcel_number") or properties.get("PLOT_NO") or properties.get("plot_no"),
                "survey_number": properties.get("survey_number") or properties.get("SURVEY_NO") or properties.get("survey_no"),
                "state": "Telangana",
                "source": self.provider_id,
                "source_url": self.url,
                **properties,
            },
        }
        if not normalized["geometry"]:
            raise ReconciliationError("Telangana reference provider returned a feature without geometry.")
        return normalized