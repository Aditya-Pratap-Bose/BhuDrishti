"""
app/services/v2/topology/engine.py
----------------------------------
Cadastral topology and cross-layer validation engine.
Identifies and logs structural cadastral defects as non-destructive ValidationIssues.
"""

from __future__ import annotations

import uuid
from typing import Any

from shapely.geometry import Polygon, mapping, shape
from shapely.ops import snap
from shapely.validation import make_valid

from app.models.v2.validation import IssueSeverity, IssueType
from app.schemas.v2.validation import ValidationIssueCreate


class CadastralTopologyEngine:
    """Validates parcel boundaries, internal rings, and cross-layer spatial relationships."""

    def __init__(self, tolerance: float = 0.00001) -> None:
        self.tolerance = tolerance

    def validate_parcels(
        self,
        parcels: list[dict[str, Any]],
        project_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        min_area_sqm: float = 5.0,
    ) -> list[ValidationIssueCreate]:
        """Inspect a set of parcel features for invalid geometry, overlaps, slivers, and duplicates."""
        issues: list[ValidationIssueCreate] = []
        parsed_geoms: list[tuple[str, Polygon]] = []

        for idx, feat in enumerate(parcels):
            fid = feat.get("id") or feat.get("properties", {}).get("ulpin") or f"P-{idx}"
            geom_dict = feat.get("geometry")
            if not geom_dict:
                continue
            geom = shape(geom_dict)

            # 1. Geometry validity check
            if not geom.is_valid:
                issues.append(
                    ValidationIssueCreate(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        feature_id=str(fid),
                        issue_type=IssueType.INVALID_GEOMETRY,
                        severity=IssueSeverity.ERROR,
                        description=f"Parcel {fid} has self-intersections or invalid boundary topology.",
                        geometry=geom_dict,
                    )
                )
                geom = make_valid(geom)

            # 2. Sliver check
            if geom.area < min_area_sqm:
                issues.append(
                    ValidationIssueCreate(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        feature_id=str(fid),
                        issue_type=IssueType.SLIVER,
                        severity=IssueSeverity.WARNING,
                        description=f"Parcel {fid} is smaller than minimum cadastral threshold ({round(geom.area, 2)} sqm).",
                        geometry=geom_dict,
                    )
                )

            if isinstance(geom, Polygon):
                parsed_geoms.append((str(fid), geom))

        # 3. Inter-parcel overlap and duplicate check
        for i, (fid_a, poly_a) in enumerate(parsed_geoms):
            for j in range(i + 1, len(parsed_geoms)):
                fid_b, poly_b = parsed_geoms[j]
                if not poly_a.intersects(poly_b):
                    continue

                intersection = poly_a.intersection(poly_b)
                if intersection.is_empty or intersection.area <= 0:
                    continue

                # Near-duplicate check (symmetric difference ratio <= 1%)
                max_area = max(poly_a.area, poly_b.area)
                sym_diff = poly_a.symmetric_difference(poly_b).area
                if max_area > 0 and (sym_diff / max_area) <= 0.01:
                    issues.append(
                        ValidationIssueCreate(
                            project_id=project_id,
                            dataset_id=dataset_id,
                            feature_id=fid_a,
                            issue_type=IssueType.DUPLICATE,
                            severity=IssueSeverity.CRITICAL,
                            description=f"Parcel {fid_a} is a duplicate of {fid_b}.",
                            geometry=mapping(intersection),
                        )
                    )
                else:
                    # Genuine overlap conflict
                    issues.append(
                        ValidationIssueCreate(
                            project_id=project_id,
                            dataset_id=dataset_id,
                            feature_id=fid_a,
                            issue_type=IssueType.PARCEL_OVERLAP,
                            severity=IssueSeverity.ERROR,
                            description=f"Parcel {fid_a} overlaps parcel {fid_b} by {round(intersection.area, 2)} sqm.",
                            geometry=mapping(intersection),
                        )
                    )

        return issues

    def validate_cross_layer(
        self,
        parcels: list[dict[str, Any]],
        buildings: list[dict[str, Any]],
        project_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
    ) -> list[ValidationIssueCreate]:
        """Validate cross-layer constraints: buildings must not cross parcel boundaries."""
        issues: list[ValidationIssueCreate] = []
        parcel_shapes = [shape(p["geometry"]) for p in parcels if p.get("geometry")]

        for b_idx, bldg in enumerate(buildings):
            bid = bldg.get("id") or bldg.get("properties", {}).get("building_id") or f"B-{b_idx}"
            b_geom = shape(bldg["geometry"])
            if not b_geom.is_valid:
                b_geom = make_valid(b_geom)

            # Count intersecting parcels
            intersecting_parcels = [p for p in parcel_shapes if p.intersects(b_geom) and p.intersection(b_geom).area > 0.1]

            if not intersecting_parcels:
                issues.append(
                    ValidationIssueCreate(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        feature_id=str(bid),
                        issue_type=IssueType.BUILDING_OUTSIDE_PARCEL,
                        severity=IssueSeverity.WARNING,
                        description=f"Building {bid} does not fall within any registered land parcel boundary.",
                        geometry=bldg.get("geometry"),
                    )
                )
            elif len(intersecting_parcels) > 1:
                # Straddles multiple parcels - serious cadastral encroachment/dispute flag
                issues.append(
                    ValidationIssueCreate(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        feature_id=str(bid),
                        issue_type=IssueType.BUILDING_CROSSING_BOUNDARY,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Building {bid} crosses boundary between multiple parcels (encroachment risk).",
                        geometry=bldg.get("geometry"),
                    )
                )

        return issues
