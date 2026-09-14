"""
app/core/exceptions.py
----------------------
Domain-specific exception hierarchy for BhuDrishti V2.
Maps domain validation, processing, topology, and integration failures
to clean, predictable HTTP error responses without leaking stack traces.
"""

from __future__ import annotations


class BhuDrishtiError(Exception):
    """Root domain exception for BhuDrishti."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatasetValidationError(BhuDrishtiError, ValueError):
    """Raised when an uploaded spatial dataset or metadata fails validation."""


class RasterValidationError(BhuDrishtiError, ValueError):
    """Raised when a raster (GeoTIFF/COG) fails CRS, bounds, band, or co-registration checks."""


class TopologyValidationError(BhuDrishtiError, ValueError):
    """Raised when geometry or cadastral topology constraints are violated."""


class FeatureExtractionError(BhuDrishtiError, ValueError):
    """Raised when an AI or heuristic feature extraction pipeline fails."""


class JobExecutionError(BhuDrishtiError, RuntimeError):
    """Raised when background job queuing or execution fails."""


class ReconciliationError(BhuDrishtiError, ValueError):
    """Raised when comparing new AI-derived parcels against existing cadastral records fails."""


class ExportValidationError(BhuDrishtiError, ValueError):
    """Raised when a feature layer or package fails export readiness validation."""


class ExportPackageError(BhuDrishtiError, RuntimeError):
    """Raised when cadastral package generation, validation gating, or manifest export fails."""
