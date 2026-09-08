# BHUDRISHTI V2 — MASTER IMPLEMENTATION & ALIGNMENT PLAN
### Comprehensive 55-Section Technical Blueprint Aligned with NAKSHA (DoLR / DILRMP)

---

## EXECUTIVE SUMMARY & SOURCE OF TRUTH

This document is the authoritative engineering roadmap and progress tracker for **BhuDrishti V2**, fully aligned with the requirements of India's **NAKSHA** (National Geospatial Knowledge-based Land Survey of Habitations in Urban Areas) ecosystem under the Department of Land Resources (DoLR), Ministry of Rural Development.

### Core Non-Negotiable Directives
1. **Preserve V1**: The existing V1 system (`/api/v1/*`, `parcels`, `users`, Colab/SAM bridge) is **100% frozen** and must remain completely untouched as a stable fallback.
2. **NAKSHA Ecosystem Reality**: NAKSHA is not an external AI API with a simple `POST /upload`. It is an administrative government ecosystem (State $\to$ District $\to$ ULB $\to$ Survey Unit $\to$ TPK Rasters $\to$ GDB Features $\to$ CORS GeoJSON/CSV $\to$ Ground Truthing $\to$ Split/Merge/Reshape $\to$ RoR Linkage $\to$ Publication $\to$ Claims Redressal).
3. **BhuDrishti Positioning**: BhuDrishti acts as the **AI/GIS Cadastral Processing & Decision-Support Engine** directly upstream of NAKSHA.
4. **Metric Projection Mandate**: All spatial calculations (areas, perimeters, tolerances, buffers, intersections) must use projected metric coordinates (UTM EPSG:32643 or local UTM zone), never raw geographic degrees.
5. **Storage Separation**: Vector features and validation records are stored in PostgreSQL + PostGIS. Large raster files (ORI, DSM, DTM, COG) are stored in object/filesystem storage (`data/v2/rasters/`), never as database BLOBs.

---

## 55-SECTION MASTER PLAN & IMPLEMENTATION STATUS MATRIX

| Section # | Section Title | Domain / Layer | Status | Key Code Artifacts |
|---|---|---|---|---|
| **01** | Executive Directives & Freeze Policy | Governance | **COMPLETED** | `docs/architecture/v1_v2_boundary.md` |
| **02** | NAKSHA Ecosystem Scope & Boundary | Integration | **COMPLETED** | `docs/architecture/naksha-integration.md` |
| **03** | BhuDrishti Value Proposition & Positioning | Architecture | **COMPLETED** | `docs/architecture/system.md` |
| **04** | Dual Storage Strategy (PostGIS + Object Store) | Data | **COMPLETED** | `app/core/config.py`, `app/core/database.py` |
| **05** | Foundation AI Scope (SAM as Component) | AI | **COMPLETED** | `app/services/v2/ai/base_extractor.py` |
| **06** | Incremental Phased Development Strategy | Project Management | **COMPLETED** | `docs/V2_IMPLEMENTATION_PLAN.md` |
| **07** | Target System Architecture & Subsystems | Architecture | **COMPLETED** | `docs/architecture/system.md` |
| **08** | Data Hierarchy (Project $\to$ Survey $\to$ Unit $\to$ Dataset) | Data Model | **COMPLETED** | `app/models/v2/project.py`, `app/schemas/v2/project.py` |
| **09** | V2 Domain Exception Hierarchy | Error Handling | **COMPLETED** | `app/core/exceptions.py`, `app/main.py` |
| **10** | Health, Liveness & Readiness Probes | Reliability | **COMPLETED** | `app/main.py` (`/health`, `/ready`) |
| **11** | Request ID Tracing & Structured Logging | Observability | **COMPLETED** | `app/core/logging.py`, `app/main.py` |
| **12** | Database Engine Hardening & Alembic Isolation | Persistence | **COMPLETED** | `app/core/database.py` |
| **13** | Dataset Ingestion Registry & Checksumming | Ingestion | **COMPLETED** | `app/services/v2/ingestion/dataset_registry.py` |
| **14** | Dataset Inspection & Bounding Metadata | Ingestion | **COMPLETED** | `app/api/v2/datasets.py`, `app/api/v2/projects.py` |
| **15** | Multi-Raster Co-Registration (ORI + DSM + DTM) | Raster Engine | **COMPLETED** | `app/services/v2/raster.py` (`validate_trio_coregistration`) |
| **16** | Normalized Digital Surface Model (nDSM = DSM - DTM) | Terrain Engine | **COMPLETED** | `app/services/v2/terrain/ndsm.py` |
| **17** | Cloud-Optimized GeoTIFF (COG) & Slippy Tile API | Tile Server | **COMPLETED** | `app/api/v2/raster.py`, `app/services/v2/raster.py` |
| **18** | Durable Asynchronous Job Subsystem | Execution | **COMPLETED** | `app/models/v2/job.py`, `app/services/v2/job_executor.py` |
| **19** | Job Control API (HTTP 202, Status, Cancel) | Execution | **COMPLETED** | `app/api/v2/jobs.py` |
| **20** | Abstract AI Feature Extractor Interface | AI Architecture | **COMPLETED** | `app/services/v2/ai/base_extractor.py` |
| **21** | Central Model Registry & Provenance Catalog | AI Governance | **COMPLETED** | `app/services/v2/ai/model_registry.py` |
| **22** | Cadastral Parcel Extractor (SAM-Guided) | AI Extraction | **COMPLETED** | `app/services/v2/ai/parcel_extractor.py` |
| **23** | Dual-Stream Building Extractor (Optical + nDSM) | AI Extraction | **COMPLETED** | `app/services/v2/ai/building_extractor.py` |
| **24** | Linear Road Network Extractor | AI Extraction | **COMPLETED** | `app/services/v2/ai/road_extractor.py` |
| **25** | Access Corridor & Right-of-Way Extractor | AI Extraction | **COMPLETED** | `app/services/v2/ai/access_corridor_extractor.py` |
| **26** | Controlled Land-Use Classifier (8-Class Revenue Taxonomy) | AI Extraction | **COMPLETED** | `app/services/v2/ai/land_use_classifier.py` |
| **27** | Mask-to-Polygon Affine Vectorizer | Vector Engine | **COMPLETED** | `app/services/v2/vectorization/polygonize.py` |
| **28** | Metric Projected Coordinate Engine (UTM EPSG:32643) | Spatial Math | **COMPLETED** | `app/services/v2/vectorization/metrics.py` |
| **29** | Cadastral Regularization & Orthogonal Simplifier | Vector Engine | **COMPLETED** | `app/services/v2/vectorization/simplification.py` |
| **30** | Geometry Normalization (Holes, Slivers, Self-Intersections) | Vector Engine | **COMPLETED** | `app/services/v2/vectorization/geometry_cleanup.py` |
| **31** | Cadastral Topology Engine (Overlaps, Gaps, Slivers) | Topology | **COMPLETED** | `app/services/v2/topology/engine.py` |
| **32** | Cross-Layer Spatial Validation (Building within Parcel) | Topology | **COMPLETED** | `app/services/v2/topology/engine.py` |
| **33** | Persistent Validation Issue Lifecycle (`ValidationIssue`) | Quality Control | **COMPLETED** | `app/models/v2/validation.py`, `app/api/v2/topology.py` |
| **34** | Legacy Cadastral Map Ingestion | Reconciliation | **COMPLETED** | `app/services/v2/reconciliation/reconciler.py` |
| **35** | Spatial IoU Calculation & Alignment Analysis | Reconciliation | **COMPLETED** | `app/services/v2/reconciliation/reconciler.py` |
| **36** | Reconciliation Categorization (`MATCH`, `NEW`, `CONFLICT`) | Reconciliation | **COMPLETED** | `app/services/v2/reconciliation/reconciler.py` |
| **37** | Reconciliation Review API | Reconciliation | **COMPLETED** | `app/api/v2/reconciliation.py` |
| **38** | 5-Pillar Multidimensional Quality Scoring Architecture | Quality Engine | **COMPLETED** | `app/services/v2/quality/scorer.py` |
| **39** | Quality Grade Assignment (A through F) | Quality Engine | **COMPLETED** | `app/services/v2/quality/scorer.py` |
| **40** | Survey Unit Quality Report API | Quality Engine | **COMPLETED** | `app/api/v2/quality.py` (`/quality/report`) |
| **41** | Surveyor Decision-Support Engine | WebGIS Logic | **COMPLETED** | `app/services/v2/quality/scorer.py`, `app/api/v2/quality.py` |
| **42** | WebGIS Cadastral Reviewer UI Enhancement | Frontend UI | **PLANNED** (Phase 10) | `static/` / React SPA components |
| **43** | Interactive Geometry Editing (Split, Merge, Reshape) | Frontend UI | **PLANNED** (Phase 10) | WebGIS Leaflet/OpenLayers editor |
| **44** | Ground-Truthing & CORS Tagging Interface | Frontend UI | **PLANNED** (Phase 10) | WebGIS attribute inspector |
| **45** | Strict NAKSHA Export Validation Gate | NAKSHA Adapter | **COMPLETED** | `app/services/v2/exports/naksha_adapter.py` |
| **46** | NAKSHA Cadastral Schema Mapping (`naksha_bhu_aadhaar_ulpin`) | NAKSHA Adapter | **COMPLETED** | `app/services/v2/exports/naksha_adapter.py` |
| **47** | Multi-Format Cadastral Exporters (GeoJSON, CSV, Shapefile) | Export Engine | **COMPLETED** | `app/services/v2/exports/geojson_exporter.py`, `csv_exporter.py` |
| **48** | Cryptographic Provenance Manifest Generator (SHA-256) | Security/Audit | **COMPLETED** | `app/services/v2/exports/naksha_adapter.py` |
| **49** | Comprehensive Architectural & Technical Documentation | Documentation | **COMPLETED** | `docs/architecture/` (5 comprehensive specs) |
| **50** | Automated Test Suite (51 / 51 Passing) | Verification | **COMPLETED** | `tests/` (10 focused test modules) |
| **51** | Distributed Worker Adapter (Celery / Redis) | Infrastructure | **PLANNED** (Phase 14) | Scalable queue workers |
| **52** | Role-Based Access Control (RBAC) & OIDC Integration | Security | **PLANNED** (Phase 15) | Keycloak / Government OAuth |
| **53** | Production Docker Containerization & Compose Stack | Deployment | **PLANNED** (Phase 18) | `Dockerfile`, `docker-compose.prod.yml` |
| **54** | Performance Benchmarking & High-Resolution Stress Tests | Performance | **PLANNED** (Phase 19) | Stress testing suite |
| **55** | Final Field Demonstration & Government Stakeholder Handover | Field Pilot | **PLANNED** (Phase 20) | ULB pilot package |

---

## DETAILED COMPLETED PHASES BREAKDOWN

### Phase 0: Safety Baseline & V1 Freeze
- Audited all existing V1 API endpoints (`/api/v1/auth`, `/api/v1/satellite`, `/api/v1/drone`, `/api/v1/parcel`), database tables (`users`, `parcels`), schemas, and static frontend code.
- Established strict architectural boundaries documented in `docs/architecture/v1_v2_boundary.md`.
- Verified that all V1 tests continue to pass without side effects.

### Phase 1: V2 Foundation & Hardening
- Created domain exception hierarchy in `app/core/exceptions.py` with custom exceptions: `BhuDrishtiError`, `ValidationError`, `TopologyError`, `RasterProcessingError`, `DatasetNotFoundError`, `CoRegistrationError`, `QualityThresholdError`, `NAKSHAValidationError`.
- Configured exception handlers in `app/main.py` mapping domain errors to HTTP 422/503 without leaking stack traces.
- Implemented `/ready` endpoint with database ping alongside the `/health` liveness probe.
- Validated via `tests/test_v2_foundation.py`.

### Phase 2: Project, Survey Unit & Dataset Hierarchy
- Defined hierarchical models in `app/models/v2/project.py`: `Project`, `Survey`, `SurveyUnit`, `Dataset`, and `ValidationStatus`.
- Created Pydantic V2 schemas in `app/schemas/v2/project.py` and `app/schemas/v2/dataset.py`.
- Developed `DatasetRegistryService` (`app/services/v2/ingestion/dataset_registry.py`) providing automated inspection of CRS, GSD, spatial bounds, and SHA-256 integrity checksums.
- Exposed REST endpoints in `app/api/v2/projects.py` and `app/api/v2/datasets.py`.
- Validated via `tests/test_v2_dataset_registry.py`.

### Phase 3: Raster & Terrain Engine (ORI + DSM + DTM)
- Enhanced `app/services/v2/raster.py` with `validate_trio_coregistration` validating pixel-alignment, coordinate congruence, and matching affine transforms.
- Built `app/services/v2/terrain/ndsm.py` computing $nDSM = \max(0, DSM - DTM)$, building height candidate mask extraction ($h \ge 2.0\text{ m}$), terrain slope and aspect.
- Validated via `tests/test_v2_raster_terrain.py`.

### Phase 4: Durable Asynchronous Job Subsystem
- Implemented `app/models/v2/job.py` and `app/services/v2/job_executor.py` managing state transitions (`queued` $\to$ `running` $\to$ `succeeded` / `failed` / `cancelled`).
- Exposed asynchronous endpoints returning HTTP 202 Accepted with job status and cancellation support in `app/api/v2/jobs.py`.
- Supported background execution of both `satellite_bbox` and `raster_extract` jobs.
- Validated via `tests/test_v2_job_executor.py`.

### Phase 5: AI Feature Extraction Architecture
- Built `BaseExtractor` abstract interface (`app/services/v2/ai/base_extractor.py`) mandating execution provenance metadata.
- Implemented specialized extractors:
  - `ParcelExtractor`: SAM-guided cadastral boundary extraction.
  - `BuildingExtractor`: Dual-stream optical spectral features + $nDSM$ elevation candidate mask fusion.
  - `RoadExtractor`: Transport network segmentation.
  - `AccessCorridorExtractor`: Narrow access pathway extraction for landlocked parcels.
  - `LandUseClassifier`: Controlled 8-class revenue taxonomy (`RESIDENTIAL`, `COMMERCIAL`, `INDUSTRIAL`, etc.) with `UNKNOWN` fallback.
- Implemented `ModelRegistry` cataloging available models, versioning, and weight hashes.
- Validated via `tests/test_v2_ai_extractors.py`.

### Phase 6: Cadastral Vectorization Engine
- Authored vectorization pipeline in `app/services/v2/vectorization/`:
  - `polygonize.py`: Mask-to-polygon transformation with affine georeferencing.
  - `metrics.py`: Metric UTM coordinate conversion (EPSG:32643) and geodesic area/perimeter computation.
  - `simplification.py`: Douglas-Peucker and orthogonal right-angle regularizer.
  - `geometry_cleanup.py`: Hole collapse, sliver removal, and topological repair.
- Validated via `tests/test_v2_vectorization.py`.

### Phase 7: Cadastral Topology & Cross-Layer Validation
- Created persistent `ValidationIssue` model in `app/models/v2/validation.py`.
- Developed `CadastralTopologyEngine` (`app/services/v2/topology/engine.py`):
  - Planar topology rules: overlap detection ($ST\_Overlaps$), near-duplicates, slivers.
  - Cross-layer spatial rules: building footprints crossing parcel boundaries flagged as `ERROR`.
- Exposed endpoints in `app/api/v2/topology.py` for listing and resolving validation issues.
- Validated via `tests/test_v2_topology_engine.py` and `tests/test_v2_topology.py`.

### Phase 8: Existing Cadastral Reconciliation
- Built `CadastralReconciler` (`app/services/v2/reconciliation/reconciler.py`) comparing AI-extracted parcels with legacy revenue boundaries.
- Computed spatial Intersection-over-Union ($IoU$) and categorized into `MATCH`, `MINOR_CHANGE`, `MAJOR_CHANGE`, `NEW`, `MISSING`, and `CONFLICT`.
- Exposed reconciliation REST endpoints in `app/api/v2/reconciliation.py`.
- Validated via `tests/test_v2_reconciliation.py`.

### Phase 9: Multidimensional Quality Scoring Engine
- Implemented `MultidimensionalQualityScorer` (`app/services/v2/quality/scorer.py`) evaluating the 5 quality pillars: Raster Quality (20%), Geometric Quality (25%), AI Confidence (20%), Cadastral Topology (20%), and Reconciliation Alignment (15%).
- Assigned letter grades ($A, B, C, D, F$) and identified priority review parcels.
- Exposed `/api/v2/quality/report` endpoint in `app/api/v2/quality.py`.
- Validated via `tests/test_v2_quality_scorer.py`.

### Phase 11: NAKSHA Integration Adapter & Multi-Format Exporter
- Implemented `NAKSHAAdapter` (`app/services/v2/exports/naksha_adapter.py`):
  - Strict validation gate enforcing zero unreviewed `ERROR` issues and minimum quality threshold.
  - Standardized schema mapping to `naksha_bhu_aadhaar_ulpin`.
  - Cryptographic provenance manifest generation with SHA-256 layer checksums.
- Created `GeoJSONExporter` and `CSVExporter`.
- Exposed export endpoints in `app/api/v2/exports.py`.
- Validated via `tests/test_v2_exports_naksha.py`.

---

## REMAINING PHASES & ROADMAP

### Phase 10: WebGIS & Surveyor Verification UI (Upcoming)
- Connect WebGIS frontend to V2 endpoints:
  - Vector layers overlay (`parcels`, `buildings`, `roads`, `corridors`).
  - Validation issues layer with clickable error centroids.
  - Interactive polygon editing tools (Split polygon, Merge polygons, Reshape boundary, Vertex snap).
  - Ground-truth tagging and CORS coordinate overlay.
  - Single-click NAKSHA export package download.

### Phase 14: Scalable Queue & Worker Fleet (Upcoming)
- Replace in-process background worker with distributed Celery + Redis broker.
- Decouple GPU worker pool (SAM model inference) from CPU worker pool (GDAL/Shapely vectorization).

### Phase 15: OIDC & Enterprise RBAC (Upcoming)
- Implement Keycloak / Government OAuth2 provider integration.
- Enforce role-based permission scopes (`ulb_admin`, `gis_supervisor`, `field_surveyor`).

### Phase 18: Production Containerization & Packaging (Final Phase)
- Author multi-stage `Dockerfile` with optimized GDAL/GEOS/PyTorch CUDA layers.
- Author `docker-compose.prod.yml` orchestrating API, Celery workers, Redis, PostgreSQL + PostGIS, and MinIO storage.
