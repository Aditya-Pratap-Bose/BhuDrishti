"""Validation tests for the V2 project and dataset data contracts."""

import unittest
import uuid

from pydantic import ValidationError

from app.models.v2.project import DatasetType, DatasetFormat
from app.schemas.v2.dataset import DatasetRegisterRequest
from app.schemas.v2.project import ProjectCreate, SurveyCreate


class V2DataContractTests(unittest.TestCase):
    def test_project_labels_are_normalized(self) -> None:
        project = ProjectCreate(
            name="  Raipur   Urban Survey ",
            state=" Chhattisgarh ",
            district=" Raipur ",
            ulb=" Raipur Municipal Corporation ",
        )
        self.assertEqual(project.name, "Raipur Urban Survey")
        self.assertEqual(project.ulb, "Raipur Municipal Corporation")

    def test_blank_project_label_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectCreate(
                name=" ",
                state="Chhattisgarh",
                district="Raipur",
                ulb="Raipur Municipal Corporation",
            )

    def test_dataset_spatial_metadata_is_checked(self) -> None:
        payload = DatasetRegisterRequest(
            project_id=uuid.uuid4(),
            name="  Survey ORI ",
            dataset_type=DatasetType.ORI,
            format=DatasetFormat.GEOTIFF,
            storage_uri=" /data/ori.tif ",
            bounds=[80.0, 21.0, 80.1, 21.1],
            resolution=[0.05, 0.05],
            dimensions=[1000, 1000],
            band_count=3,
            gsd=0.05,
            checksum="A" * 64,
        )
        self.assertEqual(payload.name, "Survey ORI")
        self.assertEqual(payload.storage_uri, "/data/ori.tif")
        self.assertEqual(payload.checksum, "a" * 64)

    def test_invalid_bounds_and_checksum_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DatasetRegisterRequest(
                project_id=uuid.uuid4(),
                name="Survey ORI",
                dataset_type=DatasetType.ORI,
                format=DatasetFormat.GEOTIFF,
                storage_uri="/data/ori.tif",
                bounds=[80.1, 21.0, 80.0, 21.1],
                checksum="not-a-sha256",
            )

    def test_survey_unit_is_normalized(self) -> None:
        survey = SurveyCreate(
            project_id=uuid.uuid4(),
            survey_unit="  SU-RAIPUR-001  ",
        )
        self.assertEqual(survey.survey_unit, "SU-RAIPUR-001")


if __name__ == "__main__":
    unittest.main()
