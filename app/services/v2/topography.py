"""DTM-derived structural prompts for the v2 multimodal pipeline."""

from __future__ import annotations

import numpy as np


def extract_dtm_structural_prompts(dtm_raster: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """Return a binary edge matrix from a single-band elevation array.

    A gradient magnitude is used instead of absolute elevation so the result
    highlights terraces, banks, and ridges across different vertical datums.
    """
    values = np.asarray(dtm_raster, dtype=np.float32)
    if values.ndim != 2 or min(values.shape) < 3:
        raise ValueError("DTM input must be a two-dimensional array at least 3x3.")
    grad_y, grad_x = np.gradient(values)
    slope = np.hypot(grad_x, grad_y)
    cutoff = float(threshold) if threshold > 0 else float(np.percentile(slope, 90))
    return slope >= cutoff


def prompt_coordinates(structural_edges: np.ndarray) -> list[tuple[int, int]]:
    """Convert a structural edge matrix into (x, y) prompt coordinates."""
    edges = np.asarray(structural_edges, dtype=bool)
    if edges.ndim != 2:
        raise ValueError("Structural edges must be a two-dimensional matrix.")
    rows, columns = np.nonzero(edges)
    return [(int(column), int(row)) for row, column in zip(rows, columns)]
