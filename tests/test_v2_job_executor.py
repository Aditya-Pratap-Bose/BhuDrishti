"""Tests for v2 worker execution and durable failure reporting."""

import uuid
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.job import JobStatus, ProcessingJob
from app.models.user import User, UserRole
from app.services.v2.job_executor import _run_satellite_bbox_job
from app.services.v2.jobs import create_job, get_job


class V2JobExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine, tables=[User.__table__, ProcessingJob.__table__]
        )
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        self.user_id = uuid.uuid4()
        self.session.add(
            User(
                id=self.user_id,
                full_name="Worker User",
                email=f"{self.user_id}@example.com",
                hashed_password="not-a-real-password-hash",
                role=UserRole.SURVEYOR,
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _job(self):
        return create_job(
            self.session,
            created_by=self.user_id,
            job_type="satellite_bbox",
            request_payload={
                "min_lon": 81.60,
                "min_lat": 21.20,
                "max_lon": 81.61,
                "max_lat": 21.21,
                "source_type": "sentinel",
            },
        )

    def test_worker_runs_existing_processing_service_and_persists_result(self):
        job = self._job()

        async def fake_process(bbox, source_type):
            self.assertEqual(source_type, "sentinel")
            self.assertEqual(bbox, (81.60, 21.20, 81.61, 21.21))
            return {"type": "FeatureCollection", "features": []}

        with patch(
            "app.services.v2.job_executor.SessionLocal", self.session_factory
        ), patch("app.services.v2.job_executor.process_bbox", fake_process):
            _run_satellite_bbox_job(job.id, self.user_id)

        self.session.expire_all()
        completed = get_job(
            self.session, job_id=job.id, created_by=self.user_id
        )
        self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        self.assertEqual(completed.result_payload["type"], "FeatureCollection")
        self.assertIsNotNone(completed.started_at)
        self.assertIsNotNone(completed.completed_at)

    def test_worker_records_engine_error_as_failed_job(self):
        job = self._job()

        async def fake_process(_bbox, _source_type):
            raise RuntimeError("upstream unavailable")

        with patch(
            "app.services.v2.job_executor.SessionLocal", self.session_factory
        ), patch("app.services.v2.job_executor.process_bbox", fake_process):
            _run_satellite_bbox_job(job.id, self.user_id)

        self.session.expire_all()
        failed = get_job(self.session, job_id=job.id, created_by=self.user_id)
        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(
            failed.error_message,
            "Satellite processing failed unexpectedly. Check the server logs.",
        )
        self.assertIsNotNone(failed.completed_at)


if __name__ == "__main__":
    unittest.main()
