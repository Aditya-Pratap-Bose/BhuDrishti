"""Persistence checks for durable topology review issues."""

import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.api.v2.topology import _persist_issues
from app.core.database import Base
from app.models.user import User, UserRole
from app.models.v2.project import Project
from app.models.v2.validation import ValidationIssue
from app.schemas.v2.validation import ValidationIssueCreate, ValidationIssueResolve
from app.models.v2.validation import IssueSeverity, IssueType


class ValidationPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[User.__table__, Project.__table__, ValidationIssue.__table__])
        self.session = sessionmaker(bind=self.engine)()
        self.user_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.session.add(User(id=self.user_id, full_name="Reviewer", email=f"reviewer-{self.user_id}@example.gov", hashed_password="hashed", role=UserRole.SURVEYOR))
        self.session.add(Project(id=self.project_id, name="Review Project", state="Telangana", district="Hyderabad", ulb="GHMC", created_by=self.user_id))
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_generated_issue_is_persisted(self) -> None:
        issue = ValidationIssueCreate(
            project_id=self.project_id,
            issue_type=IssueType.PARCEL_OVERLAP,
            severity=IssueSeverity.ERROR,
            description="Two AI parcels overlap.",
            geometry={"type": "Point", "coordinates": [78.4, 17.3]},
        )
        records = _persist_issues(self.session, [issue])
        self.assertEqual(len(records), 1)
        stored = self.session.query(ValidationIssue).one()
        self.assertIsNone(stored.resolved_at)
        self.assertEqual(stored.severity, IssueSeverity.ERROR)

    def test_resolution_note_requires_meaningful_text(self) -> None:
        with self.assertRaises(ValidationError):
            ValidationIssueResolve(resolution_note=" ")


if __name__ == "__main__":
    unittest.main()
