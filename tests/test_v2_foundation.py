"""Unit tests for BhuDrishti V2 foundation, exceptions, and readiness probe."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import (
    BhuDrishtiError,
    DatasetValidationError,
    ExportValidationError,
    FeatureExtractionError,
    JobExecutionError,
    NakshaIntegrationError,
    RasterValidationError,
    ReconciliationError,
    TopologyValidationError,
)
from app.main import app


class V2FoundationTests(unittest.TestCase):
    def test_exception_hierarchy(self) -> None:
        """Domain exceptions should inherit from BhuDrishtiError and relevant builtins."""
        self.assertTrue(issubclass(DatasetValidationError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(RasterValidationError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(TopologyValidationError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(FeatureExtractionError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(ReconciliationError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(ExportValidationError, (BhuDrishtiError, ValueError)))
        self.assertTrue(issubclass(JobExecutionError, (BhuDrishtiError, RuntimeError)))
        self.assertTrue(issubclass(NakshaIntegrationError, (BhuDrishtiError, RuntimeError)))

    def test_v2_storage_config(self) -> None:
        """V2 storage paths must be configured."""
        self.assertTrue(settings.V2_RASTER_DIR.endswith("rasters"))
        self.assertTrue(settings.V2_DATASET_DIR.endswith("datasets"))
        self.assertTrue(settings.V2_EXPORT_DIR.endswith("exports"))

    def test_health_check_endpoint(self) -> None:
        """Liveness probe should return 200 ok."""
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_probe_success(self) -> None:
        """Readiness probe should check database and storage."""
        client = TestClient(app)
        # Mock engine.connect to simulate reachable database
        with patch("app.main.engine.connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value = None
            response = client.get("/ready")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["checks"]["database"], "ok")
            self.assertEqual(data["checks"]["storage"], "ok")

    def test_readiness_probe_database_down(self) -> None:
        """Readiness probe should return 503 when database is unreachable."""
        client = TestClient(app)
        with patch("app.main.engine.connect", side_effect=RuntimeError("Connection refused")):
            response = client.get("/ready")
            self.assertEqual(response.status_code, 503)
            data = response.json()
            self.assertEqual(data["status"], "not_ready")
            self.assertEqual(data["checks"]["database"], "unreachable")


if __name__ == "__main__":
    unittest.main()
