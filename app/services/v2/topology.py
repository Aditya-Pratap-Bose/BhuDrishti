"""Cadastral topology checks and deterministic polygon cleanup."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry
from shapely.ops import snap
from shapely.validation import make_valid


@dataclass(frozen=True)
class TopologyReport:
    valid: bool
    repaired: bool
    overlaps: int
    overlap_area: float
    near_duplicate: bool
    sliver: bool
    area: float
    perimeter: float


def enforce_cadastral_topology(
    target_polygon: BaseGeometry,
    existing_parcels: list[BaseGeometry] | None = None,
    tolerance: float = 0.00001,
) -> BaseGeometry:
    """Repair a polygon, snap it to neighbours, and remove overlaps."""
    if target_polygon.is_empty:
        raise ValueError("Target geometry is empty.")
    cleaned = make_valid(target_polygon) if not target_polygon.is_valid else target_polygon
    for neighbour in existing_parcels or []:
        if neighbour.is_empty:
            continue
        cleaned = snap(cleaned, neighbour, tolerance)
        cleaned = cleaned.difference(neighbour)
    if cleaned.is_empty or not cleaned.is_valid:
        raise ValueError("Topology cleanup could not produce a valid geometry.")
    return cleaned


def inspect_topology(geometry: BaseGeometry, neighbours: list[BaseGeometry] | None = None) -> TopologyReport:
    neighbours = neighbours or []
    intersections = [
        geometry.intersection(neighbour)
        for neighbour in neighbours
        if not neighbour.is_empty and geometry.intersects(neighbour)
    ]
    overlap_areas = [
        intersection.area
        for intersection in intersections
        if intersection.area > 0
    ]
    near_duplicate = any(
        max(geometry.area, neighbour.area) > 0
        and geometry.symmetric_difference(neighbour).area
        / max(geometry.area, neighbour.area)
        <= 0.01
        for neighbour in neighbours
        if not neighbour.is_empty
    )
    return TopologyReport(
        valid=geometry.is_valid,
        repaired=not geometry.is_valid,
        overlaps=len(overlap_areas),
        overlap_area=sum(overlap_areas),
        near_duplicate=near_duplicate,
        sliver=geometry.area < 1e-10,
        area=geometry.area,
        perimeter=geometry.length,
    )
