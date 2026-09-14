"""
tests/test_v2_dataset_registry.py
---------------------------------
Unit tests for V2 project, survey, and dataset registration and validation.
"""

import tempfile
import unittest
import uuid
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User, UserRole
from app.models.v2.project import (
    Dataset,
    DatasetFormat,
    DatasetType,
    Project,
    ProjectStatus,
    Survey,
    SurveyMethod,
    ValidationStatus,
)
from app.schemas.v2.dataset import DatasetRegisterRequest
from app.schemas.v2.project import ProjectCreate, SurveyCreate
from app.services.v2.ingestion.dataset_registry import (
    create_project,
    create_survey,
    get_dataset,
    get_project,
    list_datasets,
    list_projects,
    list_surveys,
    update_survey_aoi,
    register_dataset,
    validate_dataset,
)


class V2DatasetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                Project.__table__,
                Survey.__table__,
                Dataset.__table__,
            ],
        )
        self.session = sessionmaker(bind=self.engine)()
        self.user_id = uuid.uuid4()
        self.session.add(
            User(
                id=self.user_id,
                full_name="Survey Officer",
                email=f"officer-{self.user_id}@bhudrishti.local",
                hashed_password="hashed-pass-test",
                role=UserRole.SURVEYOR,
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_project_lifecycle(self) -> None:
        """Create, fetch, and list administrative survey projects."""
        payload = ProjectCreate(
            name="Raipur Urban Survey 2026",
            description="ULB Cadastral Survey Phase 1",
            state="Chhattisgarh",
            district="Raipur",
            ulb="Raipur Municipal Corporation",
        )
        project = create_project(self.session, payload, self.user_id)
        self.assertIsNotNone(project.id)
        self.assertEqual(project.status, ProjectStatus.ACTIVE)
        self.assertEqual(project.state, "Chhattisgarh")

        fetched = get_project(self.session, project.id)
        self.assertEqual(fetched.name, "Raipur Urban Survey 2026")

        projects, total = list_projects(self.session)
        self.assertEqual(total, 1)
        self.assertEqual(projects[0].id, project.id)

    def test_survey_unit_creation(self) -> None:
        """Create and list survey units within a project."""
        project = create_project(
            self.session,
            ProjectCreate(
                name="Durg Urban Land Survey",
                state="Chhattisgarh",
                district="Durg",
                ulb="Durg Municipal Corporation",
            ),
            self.user_id,
        )
        survey = create_survey(
            self.session,
            SurveyCreate(
                project_id=project.id,
                survey_unit="SU-DURG-042",
                survey_method=SurveyMethod.DRONE_AERIAL,
                metadata_info={"gsd_target_cm": 5.0, "drone_model": "Matrice 300 RTK"},
            ),
        )
        self.assertIsNotNone(survey.id)
        self.assertEqual(survey.survey_unit, "SU-DURG-042")

        surveys = list_surveys(self.session, project.id)
        self.assertEqual(len(surveys), 1)
        self.assertEqual(surveys[0].metadata_info["gsd_target_cm"], 5.0)

    def test_survey_aoi_update(self) -> None:
        project = create_project(
            self.session,
            ProjectCreate(name="AOI Project", state="Telangana", district="Hyderabad", ulb="GHMC"),
            self.user_id,
        )
        survey = create_survey(self.session, SurveyCreate(project_id=project.id, survey_unit="SU-AOI-001"))
        updated = update_survey_aoi(self.session, project.id, survey.id, [78.4, 17.3, 78.5, 17.4], "district_selection")
        self.assertEqual(updated.metadata_info["aoi"]["bbox"], [78.4, 17.3, 78.5, 17.4])

        polygon = {"type": "Polygon", "coordinates": [[[78.4, 17.3], [78.5, 17.3], [78.5, 17.4], [78.4, 17.3]]]}
        updated = update_survey_aoi(self.session, project.id, survey.id, [78.4, 17.3, 78.5, 17.4], "polygon", polygon)
        self.assertEqual(updated.metadata_info["aoi"]["type"], "polygon")
        self.assertEqual(updated.metadata_info["aoi"]["geometry"], polygon)

    def test_dataset_registration_and_validation(self) -> None:
        """Register spatial assets and validate GeoTIFF rasters."""
        project = create_project(
            self.session,
            ProjectCreate(
                name="Bilaspur Cadastral Project",
                state="Chhattisgarh",
                district="Bilaspur",
                ulb="Bilaspur Municipal Corporation",
            ),
            self.user_id,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            raster_file = Path(temp_dir) / "ori_sample.tif"
            values = np.ones((10, 10), dtype=np.float32)
            with rasterio.open(
                raster_file,
                "w",
                driver="GTiff",
                width=10,
                height=10,
                count=1,
                dtype="float32",
                crs="EPSG:32643",
                transform=from_origin(100.0, 200.0, 0.1, 0.1),
            ) as ds:
                ds.write(values, 1)

            # Register local GeoTIFF dataset
            reg_payload = DatasetRegisterRequest(
                project_id=project.id,
                name="Bilaspur Sector 4 ORI",
                dataset_type=DatasetType.ORI,
                format=DatasetFormat.GEOTIFF,
                storage_uri=str(raster_file),
            )
            dataset = register_dataset(self.session, reg_payload, self.user_id)
            self.assertEqual(dataset.validation_status, ValidationStatus.VALID)
            self.assertEqual(dataset.crs, "EPSG:32643")
            self.assertIsNotNone(dataset.checksum)
            self.assertEqual(dataset.dimensions, [10, 10])

            # Fetch dataset
            fetched = get_dataset(self.session, dataset.id)
            self.assertEqual(fetched.name, "Bilaspur Sector 4 ORI")

            # Validate dataset
            val_res = validate_dataset(self.session, dataset.id)
            self.assertTrue(val_res.is_valid)
            self.assertEqual(val_res.status, ValidationStatus.VALID)

            # List datasets
            datasets, total = list_datasets(self.session, project.id, dataset_type=DatasetType.ORI)
            self.assertEqual(total, 1)
            self.assertEqual(datasets[0].id, dataset.id)


if __name__ == "__main__":
    unittest.main()
