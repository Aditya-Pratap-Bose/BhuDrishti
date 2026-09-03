"""Focused smoke checks for the database-backed v2 job foundation."""

import uuid
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.job import InvalidJobTransitionError, JobStatus, ProcessingJob
from app.models.user import User, UserRole
from app.services.v2.jobs import create_job, get_job, transition_job


class V2JobSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine, tables=[User.__table__, ProcessingJob.__table__]
        )
        self.session = sessionmaker(bind=self.engine)()
        self.user_id = uuid.uuid4()
        self.session.add(
            User(
                id=self.user_id,
                full_name="Smoke User",
                email=f"{self.user_id}@example.com",
                hashed_password="not-a-real-password-hash",
                role=UserRole.SURVEYOR,
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_job_is_persisted_and_owned(self) -> None:
        job = create_job(
            self.session,
            created_by=self.user_id,
            job_type="satellite_bbox",
            request_payload={"source_type": "esri"},
        )
        self.session.close()
        self.session = sessionmaker(bind=self.engine)()

        loaded = get_job(
            self.session, job_id=job.id, created_by=self.user_id
        )
        self.assertEqual(loaded.status, JobStatus.QUEUED)
        self.assertEqual(loaded.request_payload["source_type"], "esri")

    def test_transitions_are_ordered_and_terminal(self) -> None:
        job = create_job(
            self.session,
            created_by=self.user_id,
            job_type="satellite_bbox",
            request_payload={},
        )
        transition_job(
            self.session,
            job_id=job.id,
            created_by=self.user_id,
            new_status=JobStatus.RUNNING,
        )
        completed = transition_job(
            self.session,
            job_id=job.id,
            created_by=self.user_id,
            new_status=JobStatus.SUCCEEDED,
            result_payload={"features": 2},
        )
        self.assertIsNotNone(completed.started_at)
        self.assertIsNotNone(completed.completed_at)

        with self.assertRaises(InvalidJobTransitionError):
            transition_job(
                self.session,
                job_id=job.id,
                created_by=self.user_id,
                new_status=JobStatus.RUNNING,
            )


if __name__ == "__main__":
    unittest.main()
