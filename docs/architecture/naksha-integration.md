# BhuDrishti V2 — NAKSHA Integration Specification

---

## 1. Context & Executive Directive

### 1.1 The Nature of NAKSHA
**NAKSHA** (National Geospatial Knowledge-based Land Survey of Habitations in Urban Areas) is the Government of India's national initiative under the **Department of Land Resources (DoLR)**, Ministry of Rural Development, aligned with the **Digital India Land Records Modernization Programme (DILRMP)**.

A critical engineering clarification must be maintained:
> **NAKSHA is NOT an external public AI API** accepting programmatic `POST /upload` requests.  
> It is an enterprise government cadastral survey ecosystem consisting of administrative hierarchies (State $\to$ District $\to$ ULB), Survey Unit management, aerial survey imagery ingestion (TPK raster packages), feature-extracted vector layers (Esri File Geodatabase / GDB / Shapefiles), CORS GeoJSON/CSV ground-truth positioning, WebGIS editing (split, merge, reshape), Record of Rights (RoR) linkage, statutory public notification, and dispute/claims redressal workflows.

### 1.2 BhuDrishti's Upstream Role
BhuDrishti functions as the **AI/GIS Cadastral Processing & Decision-Support Engine** positioned immediately upstream of NAKSHA:

```
[ Aerial / Drone / Satellite Survey ]
                │
                ▼
╔══════════════════════════════════════════════════════════════════════╗
║                       BHUDRISHTI V2 ENGINE                           ║
║                                                                      ║
║  1. Ingestion: ORI + DSM + DTM Multi-Raster Co-Registration          ║
║  2. Multimodal AI Extraction: SAM + nDSM Elevation Fusion            ║
║  3. Metric Cadastral Vectorization: UTM EPSG:32643 Transformation    ║
║  4. Cadastral Topology: Planar Enforcement & Cross-Layer Validation  ║
║  5. Existing Cadastral Reconciliation: AI vs Legacy Revenue Records  ║
║  6. 5-Pillar Quality Scoring & Automated Grade Assessment            ║
║  7. Surveyor WebGIS Remediation: Split, Merge, Snap, Sign-Off        ║
╚══════════════════════════════════════════════════════════════════════╝
                │
                ▼
   [ NAKSHA Integration Adapter ]
        ├── Strict Validation Gate (Zero Unreviewed Errors)
        ├── Standardized Schema Mapping (Bhu-Aadhaar / ULPIN)
        └── Signed Cryptographic Provenance Manifest (SHA-256)
                │
                ▼
[ NAKSHA Government Ecosystem (DoLR / DILRMP) ]
        ├── Survey Unit Ingestion & WebGIS Overlay
        ├── RoR (Record of Rights) Property Register Linking
        ├── 30-Day Public Notice & Claims Redressal
        └── Official Final Cadastral Map Publication
```

---

## 2. NAKSHA Validation Gate

Before any dataset can be packaged for NAKSHA, it must pass through BhuDrishti's **Strict Validation Gate** (`app/services/v2/exports/naksha_adapter.py`).

An export request is **rejected** with `NAKSHAValidationError` if:
1. **Unresolved Topology Errors**: Any active `ValidationIssue` with severity `ERROR` (such as intersecting parcel boundaries, or building footprints crossing parcel limits) has not been explicitly reviewed and marked `RESOLVED` or `ACCEPTED_EXCEPTION` by an authorized surveyor.
2. **Quality Threshold Failure**: The Survey Unit's 5-Pillar Quality Score is below $70.0$ (Grade D or F).
3. **Missing Mandatory CRS**: Geometries lack a defined projected coordinate system or valid EPSG code.
4. **Non-Metric Extents**: Coordinates are unprojected degrees without valid UTM transform metadata.

---

## 3. Standard Cadastral Schema Mapping

BhuDrishti converts internal feature attributes to the official NAKSHA Cadastral Schema:

| BhuDrishti Property | NAKSHA Attribute Name | Data Type | Description |
|---|---|---|---|
| `ulpin` / generated | `naksha_bhu_aadhaar_ulpin` | `String(14)` | Unique Land Parcel Identification Number (Bhu-Aadhaar) computed from parcel centroid |
| `survey_unit_id` | `survey_unit_code` | `String(32)` | Government administrative survey unit code (e.g., `SU-DURG-042`) |
| `id` | `cadastral_parcel_id` | `String(64)` | Internal survey feature identifier |
| `area_sqm` | `gis_area_sqm` | `Float(10,2)` | Projected planar surface area in square meters (metric UTM) |
| `perimeter_m` | `gis_perimeter_m` | `Float(10,2)` | Boundary perimeter length in meters |
| `land_use_type` | `naksha_land_use_code` | `String(16)` | Controlled revenue classification code (see taxonomy below) |
| `verification_status` | `verification_state` | `String(24)` | Ground truth verification status (`UNVERIFIED`, `FIELD_VERIFIED`, `RECONCILED`) |
| `confidence` | `ai_confidence_score` | `Float(4,3)` | Multi-stream AI model extraction confidence ($0.000 - 1.000$) |
| `reconciliation_status` | `reconciliation_class` | `String(24)` | Comparison class against legacy records (`MATCH`, `MINOR_CHANGE`, `MAJOR_CHANGE`, `NEW`, `CONFLICT`) |

### Controlled Land-Use Revenue Taxonomy
NAKSHA mandates standardized land-use coding:
- `RESIDENTIAL` $\to$ Code `100` (Urban Residential Habitation)
- `COMMERCIAL` $\to$ Code `200` (Retail, Offices, Markets)
- `INDUSTRIAL` $\to$ Code `300` (Manufacturing, Warehousing)
- `AGRICULTURAL` $\to$ Code `400` (Cultivated Land / Orchards)
- `WATER_BODY` $\to$ Code `500` (Lakes, Tanks, Rivers, Canals)
- `ROAD_TRANSPORT` $\to$ Code `600` (Public Right-of-Way, Highways, Streets)
- `OPEN_VACANT` $\to$ Code `700` (Unbuilt Urban Land, Plots)
- `FOREST_VEGETATION` $\to$ Code `800` (Reserved Forest, Dense Canopy)

---

## 4. NAKSHA Survey Unit Package Structure

Exported deliverables are bundled into an immutable, self-contained directory or ZIP archive matching state survey submission standards:

```
SU-DURG-042_20260908T103000Z/
├── manifest.json                  # Cryptographic provenance & execution manifest
├── vectors/
│   ├── parcels.geojson            # Cadastral parcel boundaries with ULPIN attributes
│   ├── buildings.geojson          # Dual-stream extracted building footprints
│   ├── roads.geojson              # Linear road network centerlines / corridors
│   └── access_corridors.geojson   # Narrow access pathways to landlocked parcels
├── tables/
│   ├── cadastral_register.csv     # Tabular attribute register for revenue clerk entry
│   └── validation_audit.csv       # Complete record of resolved topological exceptions
└── rasters/
    ├── ori_metadata.json          # Georeferencing, GSD, and sensor metadata
    └── (ori_overview.tif)         # Optional downsampled overview for rapid GIS check
```

### Manifest Specification (`manifest.json`)
The manifest ensures end-to-end chain of custody and data integrity:

```json
{
  "manifest_version": "2.0.0",
  "survey_unit_id": "SU-DURG-042",
  "project_name": "Durg Urban Land Survey 2026",
  "generated_at": "2026-09-08T10:30:00Z",
  "generator": "BhuDrishti V2 NAKSHAAdapter",
  "validation_summary": {
    "quality_score": 92.4,
    "quality_grade": "A",
    "unreviewed_errors": 0,
    "resolved_exceptions": 3,
    "total_parcels": 148,
    "total_buildings": 210
  },
  "provenance": {
    "sam_model_version": "vit_h-cadastral-v2",
    "ndsm_elevation_used": true,
    "utm_crs": "EPSG:32643",
    "surveyor_id": "ecb1c8f3-29de-4e29-b6a7-b3cb089f3f01"
  },
  "layer_checksums_sha256": {
    "vectors/parcels.geojson": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "vectors/buildings.geojson": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
    "vectors/roads.geojson": "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d",
    "tables/cadastral_register.csv": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
  }
}
```

---

## 5. Official Ingestion & Verification Procedure

When a BhuDrishti package is handed over to the government survey authority:

1. **Authentication & Role Authorization**:
   - The ULB Administrator or GIS Supervisor logs into the official NAKSHA Portal (`naksha.dolr.gov.in`).
2. **Survey Unit Ingestion**:
   - The user selects State $\to$ District $\to$ ULB $\to$ Target Survey Unit.
   - The BhuDrishti export package is loaded. The NAKSHA ingestion engine validates SHA-256 layer hashes against `manifest.json`.
3. **WebGIS Visual Verification**:
   - The extracted vector boundaries (`parcels.geojson`, `buildings.geojson`) are rendered over the high-resolution TPK raster background.
   - Ground-truth CORS coordinate points are overlaid to confirm sub-5cm spatial registration.
4. **Revenue Property Linking (RoR)**:
   - Revenue clerks link each 14-character `naksha_bhu_aadhaar_ulpin` to landowner identity, property tax assessments, and existing Khata/Khasra numbers.
5. **Statutory Public Notice & Publication**:
   - The survey unit map is published for a 30-day claims and objections window.
   - Following dispute resolution, final publication locks the cadastral records into the state land registry.
