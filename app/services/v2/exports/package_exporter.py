"""
app/services/v2/exports/package_exporter.py
-------------------------------------------
Standalone cadastral export package service for BhuDrishti V2.
Enforces pre-flight validation gates, standard GeoJSON packaging,
cryptographic SHA-256 provenance manifests, and structured delivery.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from app.core.config import settings


def run_export_validation_gate(
    features: list[dict[str, Any]],
    crs: str | None,
    unresolved_topology_errors: int = 0,
) -> dict[str, Any]:
    """
    Evaluate whether cadastral dataset is ready for export packaging.
    Returns status READY or BLOCKED with specific audit reasons.
    """
    reasons: list[str] = []

    # 1. CRS Validation
    if not crs:
        reasons.append("CRS missing: Dataset must have a valid Coordinate Reference System.")

    # 2. Geometry Validity
    invalid_count = 0
    for f in features:
        geom_dict = f.get("geometry")
        if not geom_dict:
            invalid_count += 1
            continue
        try:
            poly = shape(geom_dict)
            if not poly.is_valid:
                invalid_count += 1
        except Exception:
            invalid_count += 1

    if invalid_count > 0:
        reasons.append(f"{invalid_count} feature(s) have invalid geometries or self-intersections.")

    # 3. Topology Errors
    if unresolved_topology_errors > 0:
        reasons.append(
            f"{unresolved_topology_errors} unresolved cadastral topology error(s) detected (overlaps/conflicts)."
        )

    # 4. Mandatory attributes check
    missing_attrs_count = 0
    for f in features:
        props = f.get("properties", {})
        has_id = bool(props.get("ulpin") or props.get("id") or props.get("plot_id"))
        has_area = "area_sqm" in props or "area_estimated" in props
        if not (has_id and has_area):
            missing_attrs_count += 1

    if missing_attrs_count > 0:
        reasons.append(
            f"{missing_attrs_count} feature(s) missing mandatory cadastral identifiers or area attributes."
        )

    is_ready = len(reasons) == 0
    return {
        "status": "READY" if is_ready else "BLOCKED",
        "is_ready": is_ready,
        "reasons": reasons,
    }


def generate_cadastral_export_package(
    project_meta: dict[str, Any],
    survey_unit: str,
    features: list[dict[str, Any]],
    crs: str = "EPSG:32643",
    unresolved_topology_errors: int = 0,
    model_version: str = "2.0.0",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Generate a standalone cadastral export package with cryptographic provenance manifest.
    Reports READY or BLOCKED.
    """
    gate = run_export_validation_gate(
        features, crs=crs, unresolved_topology_errors=unresolved_topology_errors
    )

    package_id = f"BHU-PKG-{uuid.uuid4().hex[:12].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "package_id": package_id,
        "generated_at": timestamp,
        "package_version": "BhuDrishti-Cadastral-Package/v2.0",
        "project": {
            "name": project_meta.get("name", "Unknown Project"),
            "state": project_meta.get("state", settings.ULPIN_STATE_CODE),
            "district": project_meta.get("district", settings.ULPIN_DISTRICT_CODE),
            "ulb": project_meta.get("ulb", "Municipal Corporation"),
        },
        "survey_unit": survey_unit,
        "crs": crs,
        "feature_count": len(features),
        "ai_model_provenance": {
            "model_version": model_version,
            "pipeline": "BhuDrishti Cadastral AI + Topology Engine",
        },
        "validation_gate": gate,
    }

    if not gate["is_ready"]:
        return {
            "package_id": package_id,
            "status": "BLOCKED",
            "manifest": manifest,
            "blocking_reasons": gate["reasons"],
        }

    # Clean standardized feature collection
    feature_collection = {
        "type": "FeatureCollection",
        "metadata": manifest,
        "features": features,
    }

    # Compute checksum of payload
    payload_str = json.dumps(feature_collection, sort_keys=True)
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    manifest["sha256_checksum"] = checksum

    # Save to disk if output_dir provided or using default export dir
    target_dir = Path(output_dir or settings.V2_EXPORT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{package_id}.json"
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2)
    saved_path = str(file_path)

    return {
        "package_id": package_id,
        "status": "READY",
        "manifest": manifest,
        "file_path": saved_path,
        "feature_count": len(features),
    }
