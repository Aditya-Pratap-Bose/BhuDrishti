# BhuDrishti — Future Implementation Plan & Strategic Roadmap
### NAKSHA-Aligned Enterprise Cadastral Platform Evolution

---

## 1. Executive Context & Architectural Baseline

BhuDrishti has established a verified, robust computational foundation for cadastral processing under V2. All core spatial, vectorization, topological, reconciliation, quality scoring, and export modules have been implemented with 51 unit tests passing.

The existing V1 implementation (`/api/v1/*`, `parcels`, `users`) remains **100% frozen** and active as the fallback contract.

This document outlines the planned strategic phases remaining for complete production deployment and government stakeholder rollout.

---

## 2. Current Implementation Status Summary

| Phase | Subsystem | Domain | Status |
|---|---|---|---|
| **Phase 0** | Safety Baseline & V1 Freeze | Architecture | **COMPLETED** |
| **Phase 1** | V2 Foundation, Domain Exceptions & Hardening | Core API | **COMPLETED** |
| **Phase 2** | Project, Survey Unit & Dataset Hierarchy | Ingestion | **COMPLETED** |
| **Phase 3** | Advanced Raster & Terrain Engine (ORI + DSM + DTM, nDSM) | Terrain Engine | **COMPLETED** |
| **Phase 4** | Durable Asynchronous Job Subsystem | Execution | **COMPLETED** |
| **Phase 5** | Multimodal AI Feature Extraction Framework | AI Architecture | **COMPLETED** |
| **Phase 6** | Cadastral Vectorization & Orthogonal Simplifier | Vector Engine | **COMPLETED** |
| **Phase 7** | Cadastral Topology & Cross-Layer Validation Engine | Topology | **COMPLETED** |
| **Phase 8** | Existing Cadastral Reconciliation Engine | Reconciliation | **COMPLETED** |
| **Phase 9** | 5-Pillar Multidimensional Quality Scoring Engine | Quality Engine | **COMPLETED** |
| **Phase 10** | WebGIS Cadastral Reviewer UI Enhancement | Frontend UI | **UPCOMING (Phase 10)** |
| **Phase 11** | NAKSHA Export Adapter & Multi-Format Exporters | Integration | **COMPLETED** |
| **Phase 12** | Versioned PostGIS Schema Migrations & Audit Retention | Persistence | **UPCOMING (Phase 12)** |
| **Phase 13** | Ground-Truthing Mobile Data Ingestion | Mobile Sync | **UPCOMING (Phase 13)** |
| **Phase 14** | Distributed Queue & Decoupled Worker Fleet | Infrastructure | **UPCOMING (Phase 14)** |
| **Phase 15** | OIDC & Government Role-Based Access Control (RBAC) | Security | **UPCOMING (Phase 15)** |
| **Phase 16** | Record of Rights (RoR) Matching Assistant | Revenue Integration | **UPCOMING (Phase 16)** |
| **Phase 17** | Prometheus Metrics & Distributed Tracing | Observability | **UPCOMING (Phase 17)** |
| **Phase 18** | Production Docker Containerization & Compose Stack | Packaging | **UPCOMING (Phase 18)** |
| **Phase 19** | Multi-Gigabyte High-Resolution Stress Testing | Performance | **UPCOMING (Phase 19)** |
| **Phase 20** | Government ULB Pilot Deployment & Handover | Field Pilot | **UPCOMING (Phase 20)** |

---

## 3. Detailed Future Phases Specification

### Phase 10: WebGIS & Surveyor Verification UI
**Objective**: Enhance the WebGIS interface to provide interactive decision-support tools for field surveyors and GIS supervisors.
- **Layer Controls**: Dynamic toggle for ORI Orthomosaic, DSM/DTM hillshade, extracted parcels, building footprints, road network, and access corridors.
- **Validation Overlay**: Visual markers for `ValidationIssue` centroids with color-coded severity (`ERROR` red, `WARNING` yellow, `INFO` blue).
- **Interactive Editing Tools**:
  - *Polygon Split*: Draw cutting lines across cadastral parcels to reflect physical subdivisions or boundary disputes.
  - *Polygon Merge*: Select contiguous parcels and merge into a single revenue record with automatic area recalculation.
  - *Vertex Snap & Reshape*: Drag boundary vertices to snap onto high-resolution ortho-imagery features.
- **Ground-Truth Tagging**: Attach CORS GNSS point observations and field photos to parcel records.
- **Single-Click NAKSHA Export**: Action button triggering the validation gate and downloading the signed survey unit ZIP archive.

### Phase 12: Versioned PostGIS Schema Migrations & Audit Retention
**Objective**: Establish automated Alembic database migrations and spatial history tables.
- Versioned Alembic migrations for `v2_projects`, `v2_surveys`, `v2_survey_units`, `v2_datasets`, `v2_validation_issues`, and `v2_cadastral_features`.
- Geometry change audit table (`v2_cadastral_audit`) tracking every vertex alteration with user ID, timestamp, and previous WKB geometry.

### Phase 13: Ground-Truthing Mobile Sync
**Objective**: Seamless field-to-office data synchronization.
- Support offline GeoPackage ingestion containing surveyor ground-truth point observations and field notes.
- Spatial snapping of AI-extracted parcel boundaries to surveyor-verified CORS coordinate points.

### Phase 14: Distributed Celery & Redis Worker Fleet
**Objective**: Scale processing to handle state-wide drone survey campaigns.
- Decouple GPU inference nodes (PyTorch SAM segmentation) from CPU GIS nodes (GDAL, rasterio, Shapely vectorization).
- Redis-backed Celery worker pools with automatic retries, task priority, and dead-letter queues.
- Integration with Kubernetes Event-driven Autoscaling (KEDA).

### Phase 15: OIDC & Enterprise RBAC
**Objective**: Secure multi-tenant access for government survey administrative structures.
- Keycloak / Government OAuth2 provider integration.
- Standardized roles:
  - `ULB_ADMIN`: Project creation, survey unit allocation, final publication sign-off.
  - `GIS_SUPERVISOR`: Validation exception approvals, quality audit review, export approval.
  - `FIELD_SURVEYOR`: Polygon editing, ground-truth tagging, issue remediation.
  - `PUBLIC_VIEWER`: Read-only access to published cadastral maps.

### Phase 16: Record of Rights (RoR) Matching Assistant
**Objective**: Accelerate revenue record linkage to physical parcels.
- Automated matching of legacy Khata/Khasra textual records with modern 14-character Bhu-Aadhaar / ULPIN identifiers based on spatial centroids and owner name fuzzy matching.

### Phase 17: Observability & Operational Runbooks
**Objective**: Production-grade health monitoring and alerting.
- Prometheus `/metrics` endpoint collecting inference latency, vectorization duration, and queue depth.
- Grafana dashboards for survey progress, quality distributions, and processing throughput.

### Phase 18: Production Containerization & Packaging (Final Phase)
**Objective**: Turnkey deployment across on-premise government datacenters and cloud environments.
- Optimized multi-stage `Dockerfile` with CUDA, GDAL, GEOS, and Python dependencies.
- Production `docker-compose.prod.yml` coordinating:
  - Reverse proxy / SSL termination (Nginx)
  - API Gateway (FastAPI)
  - GPU Inference Worker
  - CPU GIS Worker
  - Task Broker & Cache (Redis)
  - Spatial Database (PostgreSQL 15 + PostGIS 3.3)
  - Object Storage (MinIO)
- Health probe automation and automated backup scripts.

### Phase 19: High-Resolution Scaled Stress Testing
**Objective**: Validate platform resilience under large real-world survey datasets.
- Benchmark processing of 500+ megapixel drone orthomosaics.
- Measure peak memory usage, COG generation throughput, and parallel vectorization performance.

### Phase 20: Government ULB Pilot Deployment & Handover
**Objective**: Field demonstration and deployment in an active Urban Local Body survey unit.
- Deploy in a pilot ULB (e.g., Bilaspur or Raipur).
- Conduct end-to-end verification from drone flight ingestion to NAKSHA WebGIS publication.
- Deliver operator manuals and API documentation to government survey officers.
