# Project Report: BhuDrishti AI
### *AI-assisted cadastral preprocessing and WebGIS decision-support prototype*

---

## 1. Executive Summary & Problem Context

Cadastral land surveying in developing nations has historically relied on labor-intensive manual boundary tracing, total station measurements, and fragmented local revenue registers. These manual processes introduce:
1. **Prolonged Survey Cycles:** Months required to survey municipal sectors or agricultural blocks.
2. **Boundary Discrepancies & Encroachments:** Lack of sub-meter vector precision leading to litigations and land disputes.
3. **Identifier Inconsistencies:** Use of localized plot numbers rather than unified, deterministic spatial identifiers.

**BhuDrishti AI** is a student-built prototype that combines computer vision, raster/GIS processing, and a browser-based WebGIS workspace. It is intended for experimentation, preprocessing, comparison, and review of cadastral-style data. It is not an official land-record system and does not replace a government survey or approval process.

V2 expands the earlier single-AOI experiment into a fuller GIS workspace with projects, administrative search, raster datasets, AOI selection, AI outputs, reference comparison, topology checks, accuracy calculations, and map-based review. Standard ULPIN and cadastral conventions are followed; BhuDrishti is designed as a standalone system with no official government integration claimed.

---

## 2. Technology Stack & Architectural Overview

```
Frontend:
├── Vanilla ES6+ Modular Javascript (No bloated frameworks)
├── Leaflet.js 1.9.4 (Spatial rendering engine & Tile layers)
├── Tailwind CSS (Light Frosted Glassmorphic Design System)
├── geotiff.js & proj4.js (Client-side raster parsing & CRS transformation)
└── jsPDF (Cadastral Certificate generation)

Backend:
├── FastAPI 0.110+ (Asynchronous ASGI Web Framework)
├── SQLAlchemy 2.0 + GeoAlchemy2 (ORM & Spatial Engine)
├── PostgreSQL 15+ & PostGIS 3.3+ (Spatial Database)
├── RasterIO, GDAL & Pillow (High-Performance Multi-Band Raster Engine)
├── Segment-Geospatial / SamGeo / PyTorch (Meta SAM Foundation Segmentation)
├── Shapely 2.0 & Pyproj (Metric UTM EPSG:32643 Reprojection & Planar Topology)
├── rio-tiler & titiler.core (Cloud-Optimized GeoTIFF Dynamic Tile Serving)
└── Pydantic V2 (Strict Schema Enforcement & Data Validation)
```

---

## 3. Data Flow Diagrams (DFD) — V1 Baseline Workflow

### 3.1 DFD Level 0: Context Diagram

```mermaid
graph TD
    User([👤 Cadastral Surveyor / Officer])
    System[🛰️ BhuDrishti AI System]
    Satellite[🛰️ High-Res Esri / Drone Imagery]
    PostGIS[(🗄️ PostGIS Spatial Database)]
    PDFExport[📄 Prototype Report / Export]

    User -->|1. Authenticates & Draws AOI / Bounding Box| System
    Satellite -->|2. High-Res Rasters / XYZ Tiles| System
    System -->|3. Segmented Polygons & 14-Digit ULPIN| User
    User -->|4. Curates / Reshapes Boundary Vertices| System
    System -->|5. Commit Verified Land Records| PostGIS
    PostGIS -->|6. Query Land Registry & Spatial Envelopes| System
    System -->|7. Generate Prototype GIS Report / Export| PDFExport
```

---

### 3.2 DFD Level 1: Core Subsystem Data Flow

```mermaid
flowchart TD
    subgraph Client [Client-Side WebGIS Workspace]
        A1[User Selects BBox or Drops Drone GeoTIFF] --> A2[Compute Telemetry HUD: Area & Extents]
        A2 --> A3[Dispatch POST Request to API]
        A4[Render FeatureCollection Polygons on Map]
        A5[Interactive Vertex Reshaper: Drag Corner Points]
        A6[Recalculate 14-Digit ULPIN & Geodesic Metrics]
        A5 --> A6 --> A4
    end

    subgraph Backend [FastAPI Application Engine]
        B1[BBox / Drone Router: /api/v1/satellite]
        B2[Raster Ingestion: stitch_tms_to_geotiff]
        B3[AI Inference: Meta SAM ViT-B Segmentation]
        B4[Topological Cleanup: Shapely simplify & filter]
        B5[Deterministic ULPIN Generator: ECCMA Vertex Hashing]
    end

    subgraph Persistence [PostGIS Database Layer]
        C1[(parcels: ST_Polygon, ULPIN, Owner, LandUse)]
        C2[(users: RBAC Admin/Surveyor)]
    end

    A3 --> B1
    B1 --> B2 --> B3 --> B4 --> B5
    B5 -->|GeoJSON FeatureCollection| A4
    A4 -->|Commit Verified Parcel: POST /parcels/save| C1
    C1 -->|Query Parcels / Registry| Client
```

---

### 3.3 DFD Level 2: Detailed AI Boundary Extraction & ULPIN Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Surveyor as 👤 Surveyor
    participant UI as 💻 Leaflet Workspace
    participant API as ⚡ FastAPI Endpoint
    participant Raster as 🗺️ Raster Stitcher
    participant SAM as 🧠 SAM ViT-B Model
    participant ULPIN as 🔢 ULPIN Engine
    participant DB as 🗄️ PostGIS DB

    Surveyor->>UI: Drags Bounding Box (e.g. 200m x 200m)
    UI->>API: POST /api/v1/satellite/process-bbox
    API->>Raster: Download Esri XYZ tiles (Zoom 18 ~0.6m/px)
    Raster->>Raster: Crop to sub-tile boundary & write GeoTIFF
    Raster->>SAM: Run ViT-B Embedding & Mask Generation
    SAM->>API: Raw polygon vector shapefile
    API->>API: Reproject to UTM (EPSG:32643) & Shapely simplify(0.3m)
    API->>ULPIN: Generate 14-Digit ULPIN from Vertex Ring
    ULPIN-->>API: SS-DD-TTT-NNNNNNN (e.g. 22-10-001-ZTSHS9D)
    API-->>UI: Return GeoJSON FeatureCollection
    UI->>UI: Render Parcels & Populate Inspector Drawer
    Surveyor->>UI: Reshape boundary vertices (client-side)
    UI->>UI: Deterministic vertex hash recalculation
    Surveyor->>UI: Click "Save to DB"
    UI->>DB: POST /api/v1/parcels/save (Validated Polygon)
    DB-->>UI: 201 Created (Committed to PostGIS Registry)
```

---

## 4. ULPIN-Style Identifier Used in the Prototype

BhuDrishti implements the **Unique Land Parcel Identification Number (ULPIN)** standard defined by the Department of Land Resources (DoLR) and the Electronic Commerce Code Management Association (ECCMA):

### Structure:
- **Total Length:** 14 Alphanumeric Characters (Stored: `SSDDTTTNNNNNNN`, Display: `SS-DD-TTT-NNNNNNN`)
- **Characters 1–2 (SS):** State Code from Local Government Directory (e.g., `22` for Chhattisgarh).
- **Characters 3–4 (DD):** District Code (e.g., `10` for Raipur).
- **Characters 5–7 (TTT):** Sub-District / Tehsil Code (e.g., `001` for Raipur Urban).
- **Characters 8–14 (NNNNNNN):** 7-character deterministic Base36 alphanumeric string derived from canonical polygon vertex coordinates in WGS-84 coordinate reference system.

### Mathematical Properties:
$$\text{ULPIN} = \text{State} \parallel \text{District} \parallel \text{Tehsil} \parallel \text{Base36}\left(\operatorname{SHA256}(\text{CanonicalVertices})\right)[0..6]$$

- **Orientation Invariant:** Canonical vertex rotation ensures clockwise/counter-clockwise rings yield identical identifiers.
- **Partition Sensitivity:** A boundary change produces a different prototype identifier. This should not be treated as a legal land identifier without official validation.

---

## 5. V1 Database Schema & Spatial Entity Modeling

```mermaid
erDiagram
    USERS ||--o{ PARCELS : registers
    USERS {
        uuid id PK
        string email UK
        string full_name
        string hashed_password
        enum role "admin, tehsildar, surveyor"
        datetime created_at
    }

    PARCELS {
        uuid id PK
        string ulpin UK "14-digit standard identifier"
        geometry geom "PostGIS Polygon EPSG:4326"
        float area_sqm "Metric area in UTM EPSG:32643"
        float perimeter_m "Metric perimeter in meters"
        string land_use_type "Residential, Commercial, Agri..."
        string owner_name "Owner field supplied by the user"
        uuid created_by FK
        datetime created_at
        datetime updated_at
    }
```

---

## 6. V1 Performance & Scalability Enhancements

1. **Adaptive Zoom Capping:** Bounding box zoom is dynamically capped at Level 18 (~0.6m ground resolution), reducing tile download payloads by over 60% compared to Level 19 with negligible boundary variance.
2. **Concurrent Multi-Threaded Tile Fetching:** Python `ThreadPoolExecutor` downloads XYZ tiles concurrently across pooled HTTP connections.
3. **Windows File Lock Safety:** Explicit garbage collection and safe cleanup prevent file handle locks with rasterio and GDAL C-extensions.
4. **Client-Side Heavy Operations:** Geodesic area, perimeter calculations, GeoTIFF parsing, and live vertex reshaping run entirely in client JavaScript, reducing server compute loads.

---

## 7. BhuDrishti V2 Standalone Architecture & Scope

BhuDrishti V2 is designed as a standalone AI-assisted cadastral preprocessing and WebGIS platform. It does not depend on, nor does it claim official integration with, external government survey portals. It focuses on solving the core computational, spatial, and decision-support challenges of cadastral surveying:

1. **Multi-Raster Ingestion**: Validates co-registration of Orthorectified Imagery (ORI), Digital Surface Models (DSM), and Digital Terrain Models (DTM).
2. **Multimodal AI Extraction**: Uses foundation segmentation (SAM) guided by optical and $nDSM$ height data ($nDSM = DSM - DTM$) to distinguish buildings from ground plots.
3. **Metric Cadastral Vectorization**: Automatically converts masks to metric UTM (EPSG:32643) geometries with cadastral orthogonal regularization (90° right angles).
4. **Planar Cadastral Topology**: Enforces no-overlap rules and cross-layer containment (buildings must reside completely within parcels).
5. **Cadastral Reconciliation**: Quantifies discrepancies between AI-extracted parcels and historical revenue maps via spatial Intersection-over-Union ($IoU$).
6. **5-Pillar Quality Scoring**: Scores survey units across Raster, Geometry, AI, Topology, and Reconciliation pillars.
7. **Validated Export Packaging**: Produces standardized GeoJSON, CSV registers, and delivery packages with cryptographic SHA-256 provenance manifests.

External systems or government departments can independently consume these standard deliverables without requiring bespoke platform coupling.

---

## 8. V2 GIS Data Flow and Subsystems

```mermaid
flowchart TB
    subgraph Ingestion ["1. Multi-Modal Ingestion & Terrain Engine"]
        RAW_ORI["Drone / Aerial ORI GeoTIFF"]
        RAW_DSM["Digital Surface Model (DSM)"]
        RAW_DTM["Digital Terrain Model (DTM)"]
        REGISTRY["Dataset Registry Service\n(CRS, GSD, Affine, SHA-256 Checksum)"]
        NDSM_ENGINE["Terrain Engine: nDSM = max(0, DSM - DTM)\nSlope & Aspect Derivatives"]
        COG_TILES["COG Converter & Slippy XYZ Tile Server\n(/api/v2/tiles/{asset_id}/{z}/{x}/{y}.png)"]
    end

    subgraph AsyncJobs ["2. Background Job Subsystem"]
        JOB_API["Job Controller (HTTP 202 Accepted)"]
        JOB_DB[("processing_jobs Table\n(queued -> running -> succeeded)")]
        JOB_WORKER["Asynchronous Pipeline Worker"]
    end

    subgraph AIExtraction ["3. AI Feature Extraction"]
        SAM_EXTRACT["Cadastral Parcel Extractor\n(Meta SAM Foundation Embeddings)"]
        BLDG_EXTRACT["Dual-Stream Building Extractor\n(Spectral + nDSM Height h >= 2.0m)"]
        ROAD_EXTRACT["Linear Road Network Extractor"]
        CORRIDOR_EXTRACT["Access Corridor Extractor\n(Landlocked Parcel Detection)"]
        LU_EXTRACT["Controlled Land-Use Classifier\n(8-Class Revenue Taxonomy + UNKNOWN)"]
        MODEL_REG["Model Registry & Provenance Catalog"]
    end

    subgraph VectorEngine ["4. Cadastral Vectorization Engine"]
        POLYGONIZER["Mask-to-Polygon Affine Vectorizer"]
        UTM_TRANS["Metric Projected CRS Engine\n(EPSG:32643 Metric Precision)"]
        SIMPLIFIER["Orthogonal 90° Cadastral Regularizer\n& Douglas-Peucker Simplifier"]
        CLEANER["Geometry Normalization\n(Hole collapse, sliver removal, buffer(0))"]
    end

    subgraph ValidationAndQA ["5. Topology and Quality Checks"]
        TOPO_RULES["Cadastral Topology Rules\n(Overlaps > 0.05m², Duplicates, Slivers)"]
        CROSS_LAYER_RULES["Cross-Layer Rules\n(Building ST_Within Parcel, Road ROW)"]
        RECONCILER["Cadastral Reconciler: AI vs Legacy\n(MATCH >= 85%, MINOR, MAJOR, NEW, CONFLICT)"]
        SCORER["5-Pillar Quality Scorer\n(Raster 20%, Geom 25%, AI 20%, Topo 20%, Recon 15%)"]
        ISSUE_STORE[("v2_validation_issues Table\n(ERROR, WARNING, INFO)")]
    end

    subgraph Exports ["6. Cadastral Package Export"]
        GATE{"Validation checks\nbefore export"}
        MANIFEST_GEN["SHA-256 provenance manifest"]
        EXPORTERS["GeoJSON, CSV, and Validated Packages"]
    end

    RAW_ORI & RAW_DSM & RAW_DTM --> REGISTRY
    REGISTRY --> NDSM_ENGINE --> COG_TILES
    REGISTRY --> JOB_API
    JOB_API --> JOB_DB --> JOB_WORKER

    JOB_WORKER --> SAM_EXTRACT & BLDG_EXTRACT & ROAD_EXTRACT & CORRIDOR_EXTRACT & LU_EXTRACT
    NDSM_ENGINE -.->|Height Mask Gating| BLDG_EXTRACT
    MODEL_REG -.->|Model Provenance| AIExtraction

    AIExtraction --> POLYGONIZER --> UTM_TRANS --> SIMPLIFIER --> CLEANER
    CLEANER --> TOPO_RULES & CROSS_LAYER_RULES
    TOPO_RULES & CROSS_LAYER_RULES --> ISSUE_STORE
    CLEANER --> RECONCILER
    RECONCILER & ISSUE_STORE --> SCORER

    SCORER --> GATE
    GATE -->|Passed| MANIFEST_GEN --> EXPORTERS
    GATE -.->|Failed: Reject Export| ISSUE_STORE
```

---

## 9. V2 Extended Database Schema & Entity Hierarchy

```mermaid
erDiagram
    PROJECTS ||--o{ SURVEYS : contains
    SURVEYS ||--o{ SURVEY_UNITS : divides
    SURVEY_UNITS ||--o{ DATASETS : holds
    SURVEY_UNITS ||--o{ VALIDATION_ISSUES : flags
    USERS ||--o{ PROJECTS : manages
    USERS ||--o{ PROCESSING_JOBS : triggers

    PROJECTS {
        uuid id PK
        string name "e.g. Durg Urban Land Survey"
        string state_code "e.g. 22 (Chhattisgarh)"
        string district_code "e.g. 10 (Durg)"
        string ulb_code "e.g. DURG-ULB-01"
        datetime created_at
    }

    SURVEYS {
        uuid id PK
        uuid project_id FK
        string survey_number "SURVEY-2026-01"
        string methodology "DRONE_LIDAR_ORTHO"
        datetime survey_date
    }

    SURVEY_UNITS {
        uuid id PK
        uuid survey_id FK
        string unit_code "SU-DURG-042"
        geometry boundary "PostGIS MultiPolygon EPSG:4326"
        float total_area_sqm
        string status "DRAFT, VERIFIED, PUBLISHED"
    }

    DATASETS {
        uuid id PK
        uuid survey_unit_id FK
        string dataset_type "ORI, DSM, DTM, LEGACY_PARCELS, CORS"
        string file_path "data/v2/rasters/..."
        string sha256_checksum "Immutable digest"
        string crs "EPSG:32643"
        float gsd_m "0.05m"
    }

    VALIDATION_ISSUES {
        uuid id PK
        uuid survey_unit_id FK
        string issue_type "PARCEL_OVERLAP, BUILDING_CROSSING, SLIVER"
        string severity "ERROR, WARNING, INFO"
        geometry location "PostGIS Point/Polygon EPSG:4326"
        string review_status "UNREVIEWED, RESOLVED, ACCEPTED_EXCEPTION"
        string resolution_notes
        uuid reviewed_by FK
    }

    PROCESSING_JOBS {
        uuid id PK
        uuid user_id FK
        string job_type "raster_extract, satellite_bbox"
        string status "queued, running, succeeded, failed, cancelled"
        float progress "0.0 - 1.0"
        json parameters
        json result_metadata
        datetime created_at
        datetime completed_at
    }
```

---

## 10. Architectural Boundary & V1 Preservation Guarantee

To guarantee stability, BhuDrishti enforces an absolute boundary between V1 and V2:
- **Zero V1 Regressions**: `/api/v1/*` routes, schemas, and models (`users`, `parcels`) are **100% frozen** and active.
- **Dedicated V2 Namespaces**: All V2 enhancements are segregated under `app/api/v2/`, `app/services/v2/`, `app/models/v2/`, and `app/schemas/v2/`.
- **Storage Separation**: Large raster assets (ORI, DSM, DTM, COGs) reside strictly in object/file storage (`data/v2/rasters/`), never as database BLOBs.
- **Metric Math Standard**: All areas, perimeters, buffers, and snapping operations in V2 are computed in projected metric coordinate systems (UTM EPSG:32643 or local UTM), eliminating spherical degree distortion.

---

## 11. Verification & Test Metrics

BhuDrishti V2 includes an automated test suite verifying all core mathematical and operational modules:

```text
======================================================================
Ran 66 tests in the latest repository verification
Result: ALL 66 TESTS PASSING (0 Failures, 0 Errors)
======================================================================
```

- **Foundation & Hardening (`tests/test_v2_foundation.py`)**: Domain exceptions, `/health` and `/ready` probes.
- **Dataset Registry (`tests/test_v2_dataset_registry.py`)**: Hierarchical survey models, GSD/bounds calculation, SHA-256 checksumming.
- **Raster & Terrain Engine (`tests/test_v2_raster_terrain.py`)**: Trio co-registration, $nDSM$ height extraction, slope and aspect.
- **Durable Job System (`tests/test_v2_job_executor.py`)**: Asynchronous state machine and execution.
- **AI Feature Extraction (`tests/test_v2_ai_extractors.py`)**: SAM parcel, optical+nDSM building, road, corridor, and land-use extractors.
- **Cadastral Vectorization (`tests/test_v2_vectorization.py`)**: Mask-to-polygon, metric UTM, orthogonal 90° regularization, and geometry normalization.
- **Cadastral Topology & Cross-Layer (`tests/test_v2_topology_engine.py`)**: Planar overlap, duplicate, sliver detection, and building crossing parcel boundary constraints.
- **Cadastral Reconciliation (`tests/test_v2_reconciliation.py`)**: Spatial $IoU$ comparison against legacy revenue cadastres.
- **Cadastral Export & Package Tests (`tests/test_v2_exports_package.py`)**: Pre-flight validation gating, standard GeoJSON/CSV export, and SHA-256 provenance manifest generation.

---

## 12. Simple Next Steps

The immediate engineering direction is the V2 workflow defined in
[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md):
reference-data import, ORI/DSM/DTM validation, AI extraction, metric
vectorization, topology checks, reconciliation, measurable accuracy
evaluation, human WebGIS review, ground-truth updates, and
local GIS export. This is the product currently being built and tested; the
V1 implementation remains a preserved compatibility baseline.

After the core prototype is stable, useful next steps are:

1. Finish geometry editing and save corrected polygons.
2. Run a small real Telangana comparison and record accuracy results.
3. Add manual GeoJSON/GeoPackage reference import.
4. Improve raster performance for larger surveys.
5. Add migrations, deployment files, and stronger user permissions only if the prototype is later prepared for real deployment.

---

## 13. Conclusion

BhuDrishti AI is an AI-assisted cadastral preprocessing and WebGIS
decision-support prototype. Its V2 workspace combines raster datasets, AI
feature extraction, metric geometry processing, topology checks, reference
comparison, accuracy calculations, and human map review. It can help test a
GIS workflow and produce structured local outputs, but its results still need
real-data validation and independent survey or government review before any
official use.
