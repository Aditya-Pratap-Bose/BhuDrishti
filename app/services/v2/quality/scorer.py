"""
app/services/v2/quality/scorer.py
---------------------------------
Multidimensional cadastral quality scoring engine.
Evaluates raster quality, geometric validity, topological integrity,
AI confidence, and reconciliation agreement.
Provides honest workflow prioritization without fake legal accuracy claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionScore:
    name: str
    score: float           # 0.0 to 100.0
    weight: float          # Contribution weight (e.g. 0.25)
    status: str            # PASS, WARNING, FAIL
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    overall_quality_score: float             # 0 to 100
    review_priority: str                     # LOW, MEDIUM, HIGH, CRITICAL
    dimensions: list[DimensionScore]
    issues_summary: dict[str, int]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_quality_score": round(self.overall_quality_score, 1),
            "review_priority": self.review_priority,
            "dimensions": [
                {
                    "name": d.name,
                    "score": round(d.score, 1),
                    "status": d.status,
                    "details": d.details,
                }
                for d in self.dimensions
            ],
            "issues_summary": self.issues_summary,
            "recommendation": self.recommendation,
        }


def evaluate_cadastral_quality(
    raster_meta: dict[str, Any] | None = None,
    total_features: int = 0,
    invalid_geometry_count: int = 0,
    overlap_count: int = 0,
    duplicate_count: int = 0,
    sliver_count: int = 0,
    mean_ai_confidence: float = 0.75,
    reconciliation_summary: dict[str, int] | None = None,
) -> QualityReport:
    """
    Compute multidimensional quality across 5 pillars:
    1. Raster Quality
    2. Geometry Quality
    3. Topology Quality
    4. AI Model Confidence
    5. Cadastral Reconciliation Alignment
    """
    # 1. Raster Quality (20%)
    raster_score = 100.0
    raster_details: dict[str, Any] = {}
    if raster_meta:
        if not raster_meta.get("crs"):
            raster_score -= 40
        gsd = raster_meta.get("gsd")
        if gsd:
            raster_details["gsd_m"] = gsd
            if gsd > 0.25:  # Sub-25cm GSD is standard for urban cadastral
                raster_score -= min(30, (gsd - 0.25) * 50)
        if raster_meta.get("nodata") is None:
            raster_score -= 10
    else:
        raster_score = 80.0  # Assumed nominal

    raster_score = max(0.0, min(100.0, raster_score))
    raster_dim = DimensionScore(
        name="Raster Quality",
        score=raster_score,
        weight=0.20,
        status="PASS" if raster_score >= 80 else ("WARNING" if raster_score >= 60 else "FAIL"),
        details=raster_details,
    )

    # 2. Geometry Quality (25%)
    geom_score = 100.0
    if total_features > 0:
        invalid_ratio = invalid_geometry_count / total_features
        sliver_ratio = sliver_count / total_features
        geom_score -= (invalid_ratio * 100.0 * 2.0)  # Heavy penalty for invalid polygons
        geom_score -= (sliver_ratio * 100.0)
    geom_score = max(0.0, min(100.0, geom_score))
    geom_dim = DimensionScore(
        name="Geometry Integrity",
        score=geom_score,
        weight=0.25,
        status="PASS" if geom_score >= 85 else ("WARNING" if geom_score >= 70 else "FAIL"),
        details={"invalid_geometries": invalid_geometry_count, "slivers": sliver_count},
    )

    # 3. Topology Quality (25%)
    topo_score = 100.0
    if total_features > 0:
        topo_score -= (overlap_count * 5.0)       # 5 pts per overlap
        topo_score -= (duplicate_count * 15.0)    # 15 pts per duplicate
    topo_score = max(0.0, min(100.0, topo_score))
    topo_dim = DimensionScore(
        name="Cadastral Topology",
        score=topo_score,
        weight=0.25,
        status="PASS" if topo_score >= 85 else ("WARNING" if topo_score >= 65 else "FAIL"),
        details={"overlaps": overlap_count, "duplicates": duplicate_count},
    )

    # 4. AI Confidence (15%)
    ai_score = max(0.0, min(100.0, mean_ai_confidence * 100.0))
    ai_dim = DimensionScore(
        name="AI Model Confidence",
        score=ai_score,
        weight=0.15,
        status="PASS" if ai_score >= 75 else ("WARNING" if ai_score >= 60 else "FAIL"),
        details={"mean_confidence": round(mean_ai_confidence, 4)},
    )

    # 5. Cadastral Reconciliation (15%)
    recon_score = 85.0
    recon_details = reconciliation_summary or {}
    if reconciliation_summary:
        matches = reconciliation_summary.get("matches", 0)
        minors = reconciliation_summary.get("minor_changes", 0)
        conflicts = reconciliation_summary.get("conflicts", 0)
        total_eval = matches + minors + conflicts
        if total_eval > 0:
            agreement_ratio = (matches + (minors * 0.8)) / total_eval
            recon_score = agreement_ratio * 100.0
            recon_score -= (conflicts * 10.0)
    recon_score = max(0.0, min(100.0, recon_score))
    recon_dim = DimensionScore(
        name="Historical Cadastral Reconciliation",
        score=recon_score,
        weight=0.15,
        status="PASS" if recon_score >= 75 else ("WARNING" if recon_score >= 50 else "FAIL"),
        details=recon_details,
    )

    # Calculate overall weighted score
    overall = (
        (raster_dim.score * raster_dim.weight)
        + (geom_dim.score * geom_dim.weight)
        + (topo_dim.score * topo_dim.weight)
        + (ai_dim.score * ai_dim.weight)
        + (recon_dim.score * recon_dim.weight)
    )

    # Review priority for surveyor workflow
    if overall >= 85 and topo_dim.status == "PASS" and geom_dim.status == "PASS":
        priority = "LOW"
        recommendation = "High confidence survey unit. Ready for field ground-truth sampling."
    elif overall >= 70:
        priority = "MEDIUM"
        recommendation = "Acceptable cadastral baseline. Minor surveyor boundary curation recommended."
    elif overall >= 50:
        priority = "HIGH"
        recommendation = "Multiple topological defects or overlaps detected. Mandatory desk review required."
    else:
        priority = "CRITICAL"
        recommendation = "Critical survey defects detected. Requires comprehensive surveyor re-delineation."

    issues = {
        "invalid_geometries": invalid_geometry_count,
        "overlaps": overlap_count,
        "duplicates": duplicate_count,
        "slivers": sliver_count,
        "conflicts": recon_details.get("conflicts", 0),
    }

    return QualityReport(
        overall_quality_score=overall,
        review_priority=priority,
        dimensions=[raster_dim, geom_dim, topo_dim, ai_dim, recon_dim],
        issues_summary=issues,
        recommendation=recommendation,
    )
