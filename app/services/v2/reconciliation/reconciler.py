"""
app/services/v2/reconciliation/reconciler.py
--------------------------------------------
Cadastral parcel reconciliation engine: compares newly extracted AI parcels
against authoritative historical land records / existing GIS cadastral vectors.
Classifies differences into MATCH, MINOR_CHANGE, MAJOR_CHANGE, NEW, MISSING, CONFLICT.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon, mapping, shape


class ReconciliationStatus(str, enum.Enum):
    MATCH = "MATCH"                   # >= 85% IoU overlap, nearly identical boundary
    MINOR_CHANGE = "MINOR_CHANGE"     # 60-85% IoU, boundary adjustment/slight shift
    MAJOR_CHANGE = "MAJOR_CHANGE"     # 15-60% IoU, parcel subdivision or major boundary shift
    NEW = "NEW"                       # No corresponding historical parcel found (< 5% overlap)
    MISSING = "MISSING"               # Historical parcel not detected in new survey
    CONFLICT = "CONFLICT"             # Ambiguous overlap with multiple conflicting parcels


@dataclass
class ParcelReconciliationItem:
    ai_parcel_id: str | None
    existing_parcel_id: str | None
    status: ReconciliationStatus
    iou: float
    area_difference_sqm: float
    description: str
    geometry: dict[str, Any] | None = None


@dataclass
class ReconciliationReport:
    total_ai_parcels: int
    total_existing_parcels: int
    matches_count: int
    minor_changes_count: int
    major_changes_count: int
    new_parcels_count: int
    missing_parcels_count: int
    conflicts_count: int
    items: list[ParcelReconciliationItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_ai_parcels": self.total_ai_parcels,
                "total_existing_parcels": self.total_existing_parcels,
                "matches": self.matches_count,
                "minor_changes": self.minor_changes_count,
                "major_changes": self.major_changes_count,
                "new_parcels": self.new_parcels_count,
                "missing_parcels": self.missing_parcels_count,
                "conflicts": self.conflicts_count,
            },
            "items": [
                {
                    "ai_parcel_id": item.ai_parcel_id,
                    "existing_parcel_id": item.existing_parcel_id,
                    "status": item.status.value,
                    "iou": round(item.iou, 4),
                    "area_difference_sqm": round(item.area_difference_sqm, 2),
                    "description": item.description,
                    "geometry": item.geometry,
                }
                for item in self.items
            ],
        }


def compute_iou(poly_a: Polygon, poly_b: Polygon) -> float:
    """Calculate spatial Intersection over Union (Jaccard Index)."""
    if poly_a.is_empty or poly_b.is_empty:
        return 0.0
    intersection = poly_a.intersection(poly_b).area
    union = poly_a.union(poly_b).area
    if union <= 0:
        return 0.0
    return float(intersection / union)


def reconcile_cadastral_parcels(
    existing_parcels: list[dict[str, Any]],
    ai_parcels: list[dict[str, Any]],
    match_iou_threshold: float = 0.85,
    minor_iou_threshold: float = 0.60,
    major_iou_threshold: float = 0.15,
) -> ReconciliationReport:
    """
    Compare AI-detected parcel geometries with existing cadastral database.
    Outputs structured reconciliation items for surveyor decision support.
    """
    parsed_existing: list[tuple[str, Polygon, dict[str, Any]]] = []
    for idx, feat in enumerate(existing_parcels):
        fid = feat.get("id") or feat.get("properties", {}).get("ulpin") or f"EXT-{idx}"
        geom = shape(feat["geometry"])
        parsed_existing.append((str(fid), geom, feat.get("properties", {})))

    parsed_ai: list[tuple[str, Polygon, dict[str, Any]]] = []
    for idx, feat in enumerate(ai_parcels):
        fid = feat.get("id") or feat.get("properties", {}).get("ulpin") or f"AI-{idx}"
        geom = shape(feat["geometry"])
        parsed_ai.append((str(fid), geom, feat.get("properties", {})))

    matched_existing_ids: set[str] = set()
    items: list[ParcelReconciliationItem] = []

    for ai_id, ai_poly, ai_props in parsed_ai:
        candidates = []
        for ext_id, ext_poly, ext_props in parsed_existing:
            if ai_poly.intersects(ext_poly):
                iou = compute_iou(ai_poly, ext_poly)
                if iou > 0:
                    candidates.append((ext_id, ext_poly, ext_props, iou))

        if not candidates:
            # New plot not present in historical maps
            items.append(
                ParcelReconciliationItem(
                    ai_parcel_id=ai_id,
                    existing_parcel_id=None,
                    status=ReconciliationStatus.NEW,
                    iou=0.0,
                    area_difference_sqm=round(ai_poly.area, 2),
                    description=f"New unmapped parcel {ai_id} detected.",
                    geometry=mapping(ai_poly),
                )
            )
            continue

        # Sort candidates by IoU descending
        candidates.sort(key=lambda c: c[3], reverse=True)
        best_ext_id, best_ext_poly, _, best_iou = candidates[0]

        # Check for multi-overlap conflict
        high_overlap_candidates = [c for c in candidates if c[3] >= 0.30]
        if len(high_overlap_candidates) > 1:
            status = ReconciliationStatus.CONFLICT
            desc = f"Parcel {ai_id} overlaps multiple existing plots: {', '.join(c[0] for c in high_overlap_candidates)}."
        elif best_iou >= match_iou_threshold:
            status = ReconciliationStatus.MATCH
            desc = f"AI parcel {ai_id} accurately matches existing cadastral record {best_ext_id} (IoU={best_iou:.2f})."
        elif best_iou >= minor_iou_threshold:
            status = ReconciliationStatus.MINOR_CHANGE
            desc = f"Minor boundary adjustment detected between {ai_id} and {best_ext_id} (IoU={best_iou:.2f})."
        elif best_iou >= major_iou_threshold:
            status = ReconciliationStatus.MAJOR_CHANGE
            desc = f"Significant boundary deviation or plot subdivision between {ai_id} and {best_ext_id}."
        else:
            status = ReconciliationStatus.NEW
            desc = f"Low correlation with existing records; registered as new candidate {ai_id}."

        matched_existing_ids.add(best_ext_id)
        area_diff = float(abs(ai_poly.area - best_ext_poly.area))

        items.append(
            ParcelReconciliationItem(
                ai_parcel_id=ai_id,
                existing_parcel_id=best_ext_id if status != ReconciliationStatus.NEW else None,
                status=status,
                iou=best_iou,
                area_difference_sqm=area_diff,
                description=desc,
                geometry=mapping(ai_poly),
            )
        )

    # Detect missing historical parcels that were not detected in current survey
    for ext_id, ext_poly, _ in parsed_existing:
        if ext_id not in matched_existing_ids:
            items.append(
                ParcelReconciliationItem(
                    ai_parcel_id=None,
                    existing_parcel_id=ext_id,
                    status=ReconciliationStatus.MISSING,
                    iou=0.0,
                    area_difference_sqm=round(ext_poly.area, 2),
                    description=f"Existing cadastral record {ext_id} was not detected in new survey.",
                    geometry=mapping(ext_poly),
                )
            )

    matches = sum(1 for i in items if i.status == ReconciliationStatus.MATCH)
    minors = sum(1 for i in items if i.status == ReconciliationStatus.MINOR_CHANGE)
    majors = sum(1 for i in items if i.status == ReconciliationStatus.MAJOR_CHANGE)
    news = sum(1 for i in items if i.status == ReconciliationStatus.NEW)
    missings = sum(1 for i in items if i.status == ReconciliationStatus.MISSING)
    conflicts = sum(1 for i in items if i.status == ReconciliationStatus.CONFLICT)

    return ReconciliationReport(
        total_ai_parcels=len(ai_parcels),
        total_existing_parcels=len(existing_parcels),
        matches_count=matches,
        minor_changes_count=minors,
        major_changes_count=majors,
        new_parcels_count=news,
        missing_parcels_count=missings,
        conflicts_count=conflicts,
        items=items,
    )
