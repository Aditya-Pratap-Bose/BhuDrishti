# BhuDrishti V2 --- Detailed Implementation and Testing Plan

## Full GIS/WebGIS Workspace, Cadastral Comparison, and Accuracy Testing

> **Document role:** This is the detailed final plan for the student prototype. The live
> phase status, completed work, next execution slice, and acceptance checklist
> are maintained alongside it in `docs/PROJECT_STATUS.md`. The detailed plan
> remains detailed so the workflow, tests, benchmark, and future work are not
> lost. It describes a prototype and does not claim official government integration.

------------------------------------------------------------------------

## 1. Purpose

BhuDrishti V2 extends the existing V1 prototype into a full GIS/WebGIS
workspace for AI-assisted cadastral preprocessing, comparison, and review.

The target workflow is:

``` text
Existing Reference GIS Data
                +
Drone / Aerial ORI
                +
DSM
                +
DTM
                ↓
      Dataset Validation
                ↓
      Terrain / nDSM Generation
                ↓
       AI Feature Extraction
                ↓
       Raster → Vector Conversion
                ↓
       Geometry Validation
                ↓
 Existing Record Reconciliation
                ↓
       Accuracy Evaluation
                ↓
       Quality Score
                ↓
      WebGIS Human Review
                ↓
       Ground Truth Update
                ↓
        Local GIS Export
```

The core principle is:

> BhuDrishti should not only generate polygons. It should generate GIS
> features that can be compared against existing reference data,
> quantitatively evaluated, visually reviewed, corrected and exported.

------------------------------------------------------------------------

# 2. V1 Freeze

V1/c1 is the stable baseline and must remain operational.

Do not destructively modify:

``` text
/api/v1/*
users
parcels
existing V1 database flow
V1 authentication
V1 frontend
existing V1 processing workflow
```

V2 should remain isolated through:

``` text
/api/v2/*
app/models/v2/*
app/schemas/v2/*
app/services/v2/*
app/api/v2/*
frontend/v2/*
```

V2 database changes should be additive and isolated.

Recommended conceptual database separation:

``` text
PostgreSQL + PostGIS
│
├── V1
│   ├── users
│   └── parcels
│
└── V2
    ├── projects
    ├── surveys
    ├── survey_units
    ├── datasets
    ├── processing_jobs
    ├── v2_parcels
    ├── v2_buildings
    ├── v2_roads
    ├── reference_parcels
    ├── validation_issues
    ├── reconciliation_results
    └── quality_reports
```

------------------------------------------------------------------------

# 3. Existing Technical Architecture

The existing project architecture is based around:

``` text
Frontend
    ↓
FastAPI
    ↓
PostgreSQL + PostGIS
```

Geospatial processing:

``` text
Rasterio
GDAL
Shapely
PyProj
GeoAlchemy2
```

AI:

``` text
PyTorch
SAM / segmentation models
```

WebGIS:

``` text
Leaflet
GeoJSON
Raster tiles / COG
```

The V2 architecture should remain modular and model-agnostic.

------------------------------------------------------------------------

# 4. Input Data

BhuDrishti V2 should work with five major data categories:

1.  ORI
2.  DSM
3.  DTM
4.  Existing cadastral/reference data
5.  RoR/property/parcel attributes where available

------------------------------------------------------------------------

# 5. ORI --- Orthorectified Imagery

ORI is the main visual input.

Typical formats:

``` text
GeoTIFF
Cloud Optimized GeoTIFF
```

Example:

``` text
survey_001_ortho.tif
```

Required metadata:

``` text
CRS
width
height
pixel size
affine transform
bounds
band count
GSD
```

ORI is used for:

``` text
parcel extraction
building extraction
road extraction
visual interpretation
WebGIS background
AI inference
```

------------------------------------------------------------------------

# 6. DSM --- Digital Surface Model

DSM represents the elevation of the visible surface.

It may include:

``` text
ground
buildings
trees
other elevated objects
```

Example:

``` text
survey_001_dsm.tif
```

DSM is especially useful for identifying elevated structures such as
buildings.

------------------------------------------------------------------------

# 7. DTM --- Digital Terrain Model

DTM represents the bare-earth terrain.

Example:

``` text
survey_001_dtm.tif
```

It provides the terrain elevation required for normalized surface-height
calculations.

------------------------------------------------------------------------

# 8. nDSM

The normalized Digital Surface Model is:

``` text
nDSM = DSM - DTM
```

Implementation:

``` python
ndsm = np.maximum(DSM - DTM, 0)
```

Interpretation:

``` text
nDSM ≈ 0 m
→ terrain / ground

higher nDSM
→ elevated object candidate
```

A configurable threshold can be used for building candidates:

``` text
NDSM_BUILDING_HEIGHT_THRESHOLD=2.0
```

The threshold is a configurable engineering parameter, not a universal
cadastral rule.

------------------------------------------------------------------------

# 9. ORI + DSM + DTM

The three inputs provide complementary information:

``` text
ORI
→ appearance

DSM
→ visible surface elevation

DTM
→ terrain elevation

DSM - DTM
→ object height above terrain
```

This provides stronger information than RGB imagery alone for building
and terrain-aware extraction.

------------------------------------------------------------------------

# 10. Co-Registration

ORI, DSM and DTM must describe the same geographic area and align
spatially.

Validate:

``` text
CRS
bounds
resolution
pixel dimensions
affine transform
coordinate alignment
NoData
overlap
```

If datasets are incompatible, processing must stop with a clear
validation error.

Do not silently process misaligned rasters.

------------------------------------------------------------------------

# 11. Recommended Data Structure

Large rasters should not be stored directly inside PostgreSQL.

Recommended:

``` text
data/
└── v2/
    └── projects/
        └── project_001/
            └── survey_001/
                └── unit_001/
                    ├── imagery/
                    │   └── ortho.tif
                    ├── terrain/
                    │   ├── dsm.tif
                    │   └── dtm.tif
                    ├── reference/
                    │   ├── cadastral.geojson
                    │   └── ror.csv
                    ├── derived/
                    │   ├── ndsm.tif
                    │   └── slope.tif
                    ├── outputs/
                    │   ├── parcels.geojson
                    │   ├── buildings.geojson
                    │   └── roads.geojson
                    └── reports/
                        ├── accuracy.json
                        ├── reconciliation.json
                        └── quality.json
```

------------------------------------------------------------------------

# 12. Existing Land Records --- Main Requirement

The accuracy evaluation requires a reference dataset.

The preferred reference is an official cadastral spatial dataset.

Possible sources:

``` text
State BhuNaksha
State cadastral GIS
Mahabhunakasha
Official property-card GIS
Official digitized cadastral map
```

For attributes:

``` text
Record of Rights
7/12
8A
Property Card
Khasra records
Survey records
```

Use the official state/UT land-record ecosystem relevant to the selected
benchmark location.

DILRMP can be used as a starting point to identify official state/UT
land-record portals.

------------------------------------------------------------------------

# 13. Priority of Reference Sources

## Priority 1 --- Official Cadastral Geometry

Best for boundary comparison:

``` text
official parcel polygon
survey number
plot number
khasra / CTS number
official area
```

## Priority 2 --- RoR / Property Records

Best for attributes:

``` text
owner/reference information
survey number
land use
recorded area
tenure/classification
```

RoR alone is not sufficient for boundary IoU calculation if it does not
contain spatial geometry.

## Priority 3 --- Field / GNSS Verification

Best available validation:

``` text
official cadastral geometry
        +
GNSS/CORS field points
        ↓
verified reference
```

------------------------------------------------------------------------

# 14. Practical Benchmark Strategy

Do not attempt to collect an entire city.

Create a manageable benchmark:

``` text
1 ULB / city
    ↓
1 ward / locality
    ↓
1 small survey unit
    ↓
20–50 parcels initially
```

A stronger benchmark can contain:

``` text
50–100 parcels
```

Include different conditions:

``` text
regular plots
irregular plots
small plots
large plots
dense construction
open plots
road-adjacent parcels
landlocked parcels
```

Avoid using only easy examples.

------------------------------------------------------------------------

# 15. Reference Data Acquisition Workflow

The practical workflow is:

``` text
Identify benchmark AOI
        ↓
Find official state cadastral portal
        ↓
Locate target locality / survey area
        ↓
Obtain cadastral geometry where possible
        ↓
Record parcel identifiers
        ↓
Obtain corresponding RoR/property attributes
        ↓
Convert to common CRS
        ↓
Normalize into reference schema
        ↓
Store source metadata
        ↓
Use as evaluation reference
```

Never overwrite the original source.

Maintain:

``` text
raw reference
normalized reference
```

separately.

------------------------------------------------------------------------

# 16. If Official Geometry Cannot Be Downloaded

Use a controlled fallback:

``` text
Official cadastral map
        ↓
Select benchmark parcels
        ↓
Digitize selected boundaries
        ↓
Record source and digitization method
        ↓
Validate where possible
        ↓
Use as benchmark reference
```

Label this as:

``` text
manually digitized reference
```

Do not call it official ground truth unless formally verified.

A screenshot can be used for visual demonstration, but it is not
sufficient for quantitative polygon comparison.

------------------------------------------------------------------------

# 17. Reference Parcel Schema

Recommended:

``` text
reference_parcels

id
survey_unit_id
official_parcel_number
survey_number
khasra_number
cts_number
official_area_sqm
geom
source_authority
source_dataset
source_date
verification_status
```

Keep the reference geometry immutable.

------------------------------------------------------------------------

# 18. RoR / Attribute Schema

Where available:

``` text
parcel_number
survey_number
khasra_number
cts_number
recorded_area
land_use
tenure
source
source_date
```

The geometry and record attributes should be linked through parcel
identifiers wherever possible.

------------------------------------------------------------------------

# 19. CRS

Every dataset must have an explicit CRS.

Do not calculate distance or area directly in latitude/longitude
degrees.

Workflow:

``` text
Original CRS
    ↓
Validate
    ↓
Common projected CRS
    ↓
Metric calculations
```

Use the correct local projected CRS/UTM zone for the AOI.

The project may use EPSG:32643 for a suitable benchmark region, but CRS
must not be hardcoded globally for all locations.

------------------------------------------------------------------------

# 20. Dataset Registry

Every input must be registered.

Example:

``` json
{
  "dataset_id": "ds_001",
  "type": "ORI",
  "filename": "ortho.tif",
  "crs": "EPSG:32643",
  "gsd_m": 0.05,
  "width": 12000,
  "height": 10000,
  "bounds": [],
  "sha256": "..."
}
```

Register:

``` text
ORI
DSM
DTM
reference cadastral
RoR
AI outputs
```

------------------------------------------------------------------------

# 21. Provenance

Every output must identify:

``` text
dataset_id
model_version
processing_job_id
timestamp
CRS
input checksum
```

Reference data must identify:

``` text
source authority
source dataset
source date
reference identifier
verification status
```

------------------------------------------------------------------------

# 22. Complete V2 Processing Pipeline

``` text
Dataset Registration
        ↓
CRS Validation
        ↓
Raster Inspection
        ↓
ORI/DSM/DTM Co-Registration
        ↓
DSM/DTM Processing
        ↓
nDSM Generation
        ↓
Image Tiling
        ↓
AI Inference
        ↓
Mask Generation
        ↓
Raster → Vector
        ↓
Geometry Cleanup
        ↓
Topology Validation
        ↓
Reference Reconciliation
        ↓
Accuracy Calculation
        ↓
Quality Scoring
        ↓
WebGIS Review
        ↓
Verified Geometry
        ↓
Export
```

------------------------------------------------------------------------

# 23. AI Architecture

Keep feature extractors independent:

``` text
ParcelExtractor
BuildingExtractor
RoadExtractor
```

Use a common interface:

``` python
class BaseExtractor:
    def extract(...)
```

Each extractor should return:

``` text
geometry
confidence
model_version
processing_metadata
```

This keeps SAM/model implementations replaceable.

------------------------------------------------------------------------

# 24. Parcel Extraction

Initial pipeline:

``` text
ORI
 ↓
SAM / segmentation model
 ↓
raw masks
 ↓
mask filtering
 ↓
polygonization
 ↓
geometry cleanup
 ↓
parcel candidates
```

The system must distinguish:

``` text
AI candidate
```

from:

``` text
verified parcel
```

AI output is not automatically legal truth.

------------------------------------------------------------------------

# 25. Building Extraction

Use:

``` text
ORI + nDSM
```

Workflow:

``` text
ORI
 +
nDSM
 ↓
building candidate detection
 ↓
segmentation
 ↓
polygonization
 ↓
geometry cleanup
```

Suggested attributes:

``` text
building_id
area_sqm
height_estimate
confidence
geom
```

------------------------------------------------------------------------

# 26. Road Extraction

Road output can contain:

``` text
road_id
road_class
width_estimate
confidence
geom
```

Where appropriate, convert road polygons into centerlines for network
analysis.

------------------------------------------------------------------------

# 27. Raster-to-Vector

AI masks must become GIS geometries.

``` text
Mask
 ↓
Raster Polygonization
 ↓
Affine transform
 ↓
CRS transformation
 ↓
Shapely geometry
```

Libraries:

``` text
Rasterio
Shapely
PyProj
GeoAlchemy2
```

------------------------------------------------------------------------

# 28. Geometry Cleanup

Perform:

``` text
invalid geometry repair
duplicate removal
small polygon filtering
hole filtering
sliver removal
ring normalization
controlled simplification
```

Preserve raw geometry.

Recommended model:

``` text
raw_geom
processed_geom
```

Do not allow cleanup to silently destroy meaningful cadastral
boundaries.

------------------------------------------------------------------------

# 29. Topology

Check:

``` text
overlaps
gaps
duplicates
self-intersections
invalid polygons
tiny slivers
unexpected holes
```

Cross-layer checks can include:

``` text
building should normally be within parcel
road/right-of-way should intersect parcels logically
```

Topology errors and AI detection errors should remain separate metrics.

------------------------------------------------------------------------

# 30. Existing Record Reconciliation

This is the key validation stage.

``` text
REFERENCE
existing cadastral geometry

        versus

AI OUTPUT
BhuDrishti extracted geometry
```

Both are first transformed into the same CRS.

Then:

``` text
AI parcel
   ↓
spatial candidate matching
   ↓
reference parcel
   ↓
IoU
area difference
boundary distance
centroid distance
topology
   ↓
reconciliation status
```

------------------------------------------------------------------------

# 31. Parcel Matching

Use spatial indexing.

For each AI parcel:

``` text
candidate reference parcels
        ↓
bounding-box filtering
        ↓
intersection calculation
        ↓
highest valid overlap
```

Possible statuses:

``` text
MATCH
MINOR_CHANGE
MAJOR_CHANGE
NEW
MISSING
CONFLICT
```

------------------------------------------------------------------------

# 32. Intersection over Union

For AI polygon A and reference polygon B:

``` text
IoU = Area(A ∩ B) / Area(A ∪ B)
```

Example:

``` text
Intersection = 900 m²
Union = 1050 m²

IoU = 900 / 1050
    = 0.8571
    = 85.71%
```

IoU is one geometric metric, not the complete accuracy score.

------------------------------------------------------------------------

# 33. Area Error

For matched parcels:

``` text
Area Error (%) =
|AI Area - Reference Area|
-------------------------- × 100
     Reference Area
```

Example:

``` text
Reference = 1000 m²
AI = 950 m²

Area Error = 5%
```

Area consistency can additionally be reported as:

``` text
100 - Area Error
```

but the raw error percentage should always be preserved.

------------------------------------------------------------------------

# 34. Boundary Distance

Measure the distance between:

``` text
AI boundary
Reference boundary
```

Report:

``` text
mean boundary distance
median boundary distance
95th percentile boundary distance
maximum boundary distance
```

Example:

``` text
Mean = 0.42 m
Median = 0.31 m
P95 = 0.94 m
```

Boundary distance is especially important for cadastral applications
because IoU alone can hide localized boundary shifts.

------------------------------------------------------------------------

# 35. Centroid Error

Calculate:

``` text
distance(AI centroid, reference centroid)
```

in meters.

Use this as a diagnostic metric rather than a replacement for boundary
distance.

------------------------------------------------------------------------

# 36. Precision

For parcel detection:

``` text
Precision = TP / (TP + FP)
```

where:

``` text
TP = correctly detected reference parcels
FP = AI parcels without valid reference matches
```

------------------------------------------------------------------------

# 37. Recall

``` text
Recall = TP / (TP + FN)
```

where:

``` text
FN = reference parcels missed by AI
```

------------------------------------------------------------------------

# 38. F1

``` text
F1 = 2 × Precision × Recall
     ------------------------
       Precision + Recall
```

F1 provides a combined detection metric.

------------------------------------------------------------------------

# 39. IoU Matching Threshold

Use configurable thresholds.

Example initial configuration:

``` text
IoU >= 0.85
→ MATCH

0.65 <= IoU < 0.85
→ MINOR_CHANGE

0.40 <= IoU < 0.65
→ MAJOR_CHANGE

IoU < 0.40
→ CONFLICT / NEW
```

These are project evaluation thresholds, not universal government
standards.

Keep them configurable.

------------------------------------------------------------------------

# 40. Topology Quality

Report:

``` text
invalid geometry count
overlap count
gap count
duplicate count
sliver count
self-intersection count
```

Example:

``` text
50 parcels
1 invalid geometry
2 overlaps
1 sliver
```

------------------------------------------------------------------------

# 41. Do Not Report a Fake Single Accuracy Number

Never hardcode:

``` text
Accuracy = 95%
```

unless it was actually measured.

The correct process is:

``` text
Defined benchmark
+
defined reference
+
defined matching threshold
+
measured metrics
=
reported result
```

If the benchmark has not been executed, say:

> Final quantitative accuracy is pending validation against the selected
> reference dataset.

------------------------------------------------------------------------

# 42. Quality Score

A separate internal quality score can combine multiple dimensions.

Initial weighting:

``` text
Raster Quality              20%
Geometric Quality           25%
AI Detection/Confidence     20%
Topology Quality             20%
Reference Reconciliation    15%
```

Formula:

``` text
Quality Score =
0.20 × Raster
+ 0.25 × Geometry
+ 0.20 × AI
+ 0.20 × Topology
+ 0.15 × Reconciliation
```

This is a product-level quality score.

It must not be presented as an official government accuracy standard.

------------------------------------------------------------------------

# 43. Quality Grade

Example internal grade:

``` text
90–100 → A
80–89  → B
70–79  → C
60–69  → D
<60    → F
```

Keep this separate from measured accuracy metrics.

------------------------------------------------------------------------

# 44. WebGIS V2

The WebGIS should be the main operational interface.

Required components:

``` text
Map
Layer panel
Dataset information
Processing status
Parcel inspector
Reference comparison
Reconciliation panel
Topology panel
Quality panel
Editing tools
Review workflow
Export controls
```

------------------------------------------------------------------------

# 45. WebGIS Layers

``` text
Base Map
ORI
DSM visualization
DTM visualization
nDSM

Reference Parcels
AI Parcels
Verified Parcels
Buildings
Roads
Validation Issues
```

------------------------------------------------------------------------

# 46. Reference vs AI Comparison

Provide:

``` text
Reference only
AI only
Reference + AI
Difference
```

Recommended comparison controls:

``` text
opacity
layer toggle
swipe comparison
```

Difference visualization:

``` text
Reference ∩ AI
Reference - AI
AI - Reference
```

This makes the numerical reconciliation visually understandable.

------------------------------------------------------------------------

# 47. Parcel Inspector

When a parcel is selected:

``` text
Parcel ID
Reference ID
Survey Number
Reference Area
AI Area
Area Difference
IoU
Boundary Error
AI Confidence
Topology Status
Reconciliation Status
Review Status
```

Example:

``` text
Reference Area: 1020 m²
AI Area:        1002 m²

Area Error:     1.76%
IoU:            91.4%

Boundary P95:   0.42 m
AI Confidence:  0.91

Topology:       VALID
Reconciliation: MATCH
```

------------------------------------------------------------------------

# 48. Human Review

Workflow:

``` text
AI Generated
      ↓
Review Required
      ↓
Surveyor edits
      ↓
Validation
      ↓
Verified
```

Editing operations:

``` text
move vertex
add vertex
delete vertex
split parcel
merge parcel
reshape boundary
```

Store the fact that the geometry was manually corrected.

------------------------------------------------------------------------

# 49. Ground Truthing

The reviewer should be able to mark:

``` text
Agree with Shape
Needs Correction
Field Verified
Conflict
Missing
New Parcel
```

This creates a human-in-the-loop cadastral workflow.

------------------------------------------------------------------------

# 50. Accuracy Dashboard

Show:

``` text
Total reference parcels
AI detected parcels

TP
FP
FN

Precision
Recall
F1

Mean IoU
Median IoU

Mean Area Error
Median Area Error

Mean Boundary Distance
P95 Boundary Distance

Topology Errors

Overall Quality Score
Quality Grade
```

------------------------------------------------------------------------

# 51. Dataset-Level Statistics

Do not report only the mean.

For IoU and geometric errors report:

``` text
mean
median
P10
P90 / P95
```

This shows whether performance is consistently good or driven by a few
easy parcels.

------------------------------------------------------------------------

# 52. Accuracy Report

Generate:

``` text
accuracy.json
accuracy.csv
accuracy_report.pdf
```

Example:

``` json
{
  "dataset": "unit_001",
  "reference_source": "official_cadastral_map",
  "parcel_count": 50,
  "true_positive": 46,
  "false_positive": 3,
  "false_negative": 4,
  "precision": 0.9388,
  "recall": 0.92,
  "f1": 0.9293,
  "mean_iou": 0.874,
  "mean_area_error_percent": 4.8,
  "mean_boundary_distance_m": 0.47,
  "p95_boundary_distance_m": 1.12
}
```

The values are example values only and must be replaced with measured
results.

------------------------------------------------------------------------

# 53. Reference vs Ground Truth

Existing cadastral records are authoritative references, but they may
contain:

``` text
old survey information
digitization errors
map displacement
land-use changes
mutation timing differences
construction changes
```

Therefore maintain three concepts:

``` text
REFERENCE
FIELD_VERIFIED_REFERENCE
AI_OUTPUT
```

Do not claim field-level accuracy without field verification.

------------------------------------------------------------------------

# 54. If RoR Area and Map Area Differ

Keep both values:

``` text
recorded_area
cadastral_geometry_area
```

Calculate their discrepancy separately.

For boundary evaluation:

``` text
cadastral geometry → boundary reference
```

For attribute validation:

``` text
RoR/property record → attribute reference
```

Do not force the two sources to match.

------------------------------------------------------------------------

# 55. ULPIN

The system must distinguish between:

``` text
official government-issued ULPIN
```

and:

``` text
BhuDrishti-generated provisional identifier
```

A locally generated deterministic ID must never be presented as an
officially issued ULPIN.

------------------------------------------------------------------------

# 56. V2 API Structure

Recommended:

``` text
/api/v2/projects
/api/v2/surveys
/api/v2/survey-units

/api/v2/datasets
/api/v2/datasets/{id}

/api/v2/jobs
/api/v2/jobs/{id}

/api/v2/raster
/api/v2/tiles/{asset_id}/{z}/{x}/{y}.png

/api/v2/extraction/parcels
/api/v2/extraction/buildings
/api/v2/extraction/roads

/api/v2/topology
/api/v2/topology/issues

/api/v2/reference
/api/v2/reference/import

/api/v2/reconciliation
/api/v2/reconciliation/{id}

/api/v2/accuracy
/api/v2/accuracy/report

/api/v2/quality/report

/api/v2/export
```

------------------------------------------------------------------------

# 57. Database Entities

Minimum:

``` text
Project
Survey
SurveyUnit
Dataset
ProcessingJob

ReferenceParcel
Parcel
Building
Road

ValidationIssue
ReconciliationResult
AccuracyResult
QualityReport

ModelRun
ExportManifest
```

------------------------------------------------------------------------

# 58. Parcel Table

Suggested fields:

``` text
id
project_id
survey_unit_id

parcel_number
reference_id

geom
raw_geom

area_sqm
perimeter_m

ai_confidence
status

source_dataset_id
model_run_id

created_at
updated_at
```

------------------------------------------------------------------------

# 59. Reference Parcel Table

Suggested:

``` text
id
survey_unit_id

official_parcel_number
survey_number
khasra_number
cts_number

official_area_sqm

geom

source_authority
source_dataset
source_date

verification_status
```

------------------------------------------------------------------------

# 60. Reconciliation Table

Suggested:

``` text
id

ai_parcel_id
reference_parcel_id

iou
area_error_percent

boundary_mean_m
boundary_median_m
boundary_p95_m

centroid_distance_m

status
created_at
```

------------------------------------------------------------------------

# 61. Accuracy Table

Suggested:

``` text
id
survey_unit_id

tp
fp
fn

precision
recall
f1

mean_iou
median_iou

mean_area_error
median_area_error

mean_boundary_distance
p95_boundary_distance

topology_error_count

created_at
```

------------------------------------------------------------------------

# 62. Frontend Structure

Keep common, V1 and V2 separated:

``` text
frontend/
│
├── common/
│   ├── components/
│   ├── utils/
│   ├── api/
│   ├── types/
│   └── gis/
│
├── v1/
│   ├── pages/
│   ├── components/
│   ├── templates/
│   └── api/
│
└── v2/
    ├── pages/
    ├── components/
    ├── map/
    ├── layers/
    ├── inspector/
    ├── reconciliation/
    ├── quality/
    ├── review/
    └── api/
```

V1 must not import V2 business logic.

------------------------------------------------------------------------

# 63. V2 Pages

Minimum:

``` text
V2 Dashboard
Project
Survey Unit
Dataset Manager
Processing Jobs
WebGIS Workspace
Reconciliation
Accuracy Report
Quality Report
Export
```

------------------------------------------------------------------------

# 64. Dataset Manager

The interface should allow:

``` text
Upload ORI
Upload DSM
Upload DTM
Upload Reference Cadastral
Upload RoR / CSV
```

Display:

``` text
CRS
GSD
bounds
resolution
file size
checksum
validation status
```

------------------------------------------------------------------------

# 65. Processing Job UI

Show:

``` text
Queued
Running
Succeeded
Failed
Cancelled
```

Pipeline progress:

``` text
Ingestion
Raster Validation
nDSM
AI Extraction
Vectorization
Topology
Reconciliation
Accuracy
Quality
```

------------------------------------------------------------------------

# 66. Large Raster Handling

Do not load entire large rasters into the browser.

Use:

``` text
Cloud Optimized GeoTIFF where applicable
windowed reads
tile endpoints
```

For benchmark-sized vector datasets:

``` text
GeoJSON
```

is sufficient initially.

------------------------------------------------------------------------

# 67. Standalone Cadastral Standards Alignment

BhuDrishti is designed as a standalone, modular cadastral decision-support system. It generates standard cadastral deliverables (GeoJSON, CSV registers, and validation-gated packages) aligned with national spatial standards (such as 14-digit ULPIN / Bhu-Aadhaar and metric UTM EPSG:32643 projection).

Target concept:

``` text
Aerial / Drone Imagery
      ↓
Feature Extraction
      ↓
Planar Topology & Cross-Layer Validation
      ↓
Reference Record Reconciliation
      ↓
Quality Scoring & WebGIS Review
      ↓
Validated Cadastral Export (GeoJSON / CSV / Manifest)
```

BhuDrishti operates independently: government agencies or downstream systems can ingest its standardized, cryptographically verified outputs on their own side if desired.

------------------------------------------------------------------------

# 68. Export Formats

Support:

``` text
GeoJSON
GeoPackage
CSV
Shapefile
```

Government-specific adapters can be added independently.

------------------------------------------------------------------------

# 69. Provenance Manifest

Generate:

``` text
manifest.json
```

containing:

``` text
project
survey
survey unit
input datasets
SHA-256 checksums
model versions
processing timestamp
CRS
software version
quality score
validation status
```

------------------------------------------------------------------------

# 70. Export Gate

Critical validation errors should block export.

Examples:

``` text
missing CRS
invalid geometry
critical topology issue
unresolved reference conflict
```

Example:

``` text
EXPORT BLOCKED
```

Warnings such as low AI confidence can remain reviewable.

------------------------------------------------------------------------

# 71. Testing Without Immediate Drone Data

If direct drone testing is currently difficult, V2 development should
continue in stages.

## Stage 1 --- Synthetic

Test:

``` text
polygonization
IoU
area calculation
boundary distance
topology
reconciliation
quality scoring
```

using known polygons.

## Stage 2 --- Real GeoTIFF

Test:

``` text
ingestion
CRS
tiling
WebGIS
raster processing
```

## Stage 3 --- Real Drone ORI

Test:

``` text
complete image extraction
```

## Stage 4 --- ORI + DSM + DTM

Test:

``` text
multimodal terrain-aware pipeline
```

## Stage 5 --- ORI + DSM + DTM + Official Reference

Run the complete benchmark.

------------------------------------------------------------------------

# 72. Synthetic Accuracy Benchmark

Create known geometries:

``` text
reference polygon
AI polygon with 0.2 m shift
AI polygon with 0.5 m shift
AI polygon with missing corner
AI polygon with extra corner
AI polygon with subdivision
```

The evaluation engine should correctly calculate the resulting
differences.

This allows development of the evaluation system before real drone data
is available.

------------------------------------------------------------------------

# 73. Evaluation Engine Independence

The accuracy engine should accept:

``` text
reference.geojson
ai_output.geojson
```

independently from the AI model.

Therefore:

``` text
AI model incomplete
```

does not block:

``` text
reconciliation
accuracy
quality
WebGIS comparison
```

This should be implemented early.

------------------------------------------------------------------------

# 74. Benchmark Execution

The complete benchmark:

``` text
Reference
    ↓
AI Output
    ↓
Spatial Matching
    ↓
IoU
    ↓
Area Error
    ↓
Boundary Distance
    ↓
Precision
    ↓
Recall
    ↓
F1
    ↓
Topology
    ↓
Quality Score
```

Then generate:

``` text
numeric report
visual comparison
review queue
```

------------------------------------------------------------------------

# 75. Accuracy Reporting

Recommended report:

``` text
BHUDRISHTI V2 ACCURACY REPORT

Dataset:
UNIT-001

Reference:
Official cadastral map

Total reference parcels:
50

AI parcels:
49

TP:
46

FP:
3

FN:
4

Precision:
93.88%

Recall:
92.00%

F1:
92.93%

Mean IoU:
87.40%

Median IoU:
90.10%

Mean Area Error:
4.80%

Mean Boundary Distance:
0.47 m

P95 Boundary Distance:
1.12 m

Topology Errors:
3

Overall Quality Score:
87.40

Grade:
B
```

These values are only an example format.

------------------------------------------------------------------------

# 76. How to Explain Accuracy to Evaluators

Do not say:

> Our system has 95% accuracy.

unless that number was actually measured.

Preferred explanation:

> BhuDrishti is evaluated against an authoritative cadastral reference
> dataset. Parcel detection is measured using Precision, Recall and F1,
> while geometric agreement is evaluated using IoU, area error and
> boundary distance. Topology errors are evaluated separately, and a
> separate composite quality score is generated for operational decision
> support.

If the benchmark has not yet been completed:

> The evaluation pipeline is implemented, while final quantitative
> accuracy is pending validation against the selected reference dataset.

------------------------------------------------------------------------

# 77. Development Order

The implementation should proceed in this order:

## Phase 0

Freeze and verify V1/c1.

## Phase 1

V2 database and data contracts.

Current implementation focus: the V2 project, survey, and dataset contracts
normalize operator-entered labels and reject malformed bounds, raster
resolution, dimensions, band counts, GSD values, and SHA-256 checksums before
storage. This phase does not require external cadastral records.

## Phase 2

Reference data import.

## Phase 3

ORI/DSM/DTM ingestion and validation.

## Phase 4

nDSM and raster processing.

## Phase 5

AI extraction.

## Phase 6

Vectorization and geometry cleanup.

## Phase 7

Topology.

## Phase 8

Reconciliation.

## Phase 9

Accuracy engine.

## Phase 10

WebGIS reference-vs-AI comparison.

## Phase 11

Human review/editing.

## Phase 12

Quality dashboard.

## Phase 13

Government-compatible export.

## Phase 14

Final benchmark and documentation.

# Future Practical Extensions
 
After the prototype workflow is thoroughly tested and benchmarked, these practical improvements may be considered:

1. **Versioned persistence**: Introduce Alembic migrations for schema upgrades.
2. **Interactive vertex editor in V2**: Implement full client-side vertex editing and snapping directly in the V2 WebGIS workspace.
3. **Large drone flight optimization**: Streamline COG generation and chunked memory processing for multi-gigabyte orthomosaics.
4. **Simple container packaging**: Provide a clean Docker setup for local and server deployment.
5. **Real survey field test**: Run field pilots comparing drone imagery extractions against ground-truth cadastral revenue records.

------------------------------------------------------------------------

# 78. Immediate Priority

Because direct V2 drone testing may not yet be possible, the immediate
priority should be:

``` text
1. Reference parcel import
2. Accuracy engine
3. Reconciliation engine
4. Synthetic benchmark
5. Reference-vs-AI WebGIS
6. Human review
7. Existing V2 raster pipeline validation
8. Real drone integration
9. Complete benchmark
```

This prevents drone-data availability from blocking the entire V2
implementation.

------------------------------------------------------------------------

# 79. First Benchmark Directory

Create:

``` text
data/v2/benchmark/unit_001/
```

with:

``` text
reference/
    parcels.geojson

imagery/
    ortho.tif

terrain/
    dsm.tif
    dtm.tif

outputs/
    ai_parcels.geojson

reports/
```

If DSM/DTM is temporarily unavailable, begin with:

``` text
reference + ORI
```

and add DSM/DTM later.

------------------------------------------------------------------------

# 80. Status Tracking

"Implemented" must not automatically mean "validated on real drone
imagery".

Track:

``` text
CODE_IMPLEMENTED
UNIT_TESTED
INTEGRATION_TESTED
REAL_DATA_TESTED
BENCHMARK_VALIDATED
```

Recommended status matrix:

  Module             Code                 Unit Test   Real Data   Benchmark
  ------------------ -------------------- ----------- ----------- -----------
  Dataset Registry   Implemented          Required    Pending     Pending
  ORI                Implemented          Required    Pending     Pending
  DSM                Implemented          Required    Pending     Pending
  DTM                Implemented          Required    Pending     Pending
  nDSM               Implemented          Required    Pending     Pending
  Parcel AI          Implemented/verify   Required    Pending     Pending
  Building AI        Implemented/verify   Required    Pending     Pending
  Road AI            Implemented/verify   Required    Pending     Pending
  Vectorization      Implemented          Required    Pending     Pending
  Topology           Implemented          Required    Pending     Pending
  Reference Import   Build/verify         Required    Required    Required
  Reconciliation     Build/verify         Required    Required    Required
  Accuracy Engine    Build/verify         Required    Required    Required
  WebGIS Review      Build                Required    Required    Required
  Export             Implement/verify     Required    Required    Required

------------------------------------------------------------------------

# 81. Definition of Done

V2 should be considered benchmark-ready only when:

``` text
[ ] ORI can be registered
[ ] DSM can be registered
[ ] DTM can be registered
[ ] CRS is validated
[ ] ORI/DSM/DTM alignment is validated
[ ] nDSM can be generated
[ ] AI extraction can run
[ ] AI masks become GIS polygons
[ ] polygons are geometrically valid
[ ] topology checks run
[ ] reference cadastral layer can be imported
[ ] AI/reference matching works
[ ] IoU is calculated
[ ] area error is calculated
[ ] boundary distance is calculated
[ ] Precision is calculated
[ ] Recall is calculated
[ ] F1 is calculated
[ ] topology errors are calculated
[ ] quality score is generated
[ ] WebGIS displays reference + AI
[ ] reviewer can edit
[ ] corrected geometry can be saved
[ ] provenance is stored
[ ] accuracy report is generated
[ ] export validation works
```

------------------------------------------------------------------------

# 82. Final Architecture

``` text
                    GOVERNMENT / REFERENCE DATA
                              │
               ┌──────────────┴──────────────┐
               │                             │
        Cadastral Maps                    RoR
               │                             │
               └──────────────┬──────────────┘
                              │
                         REFERENCE DB
                              │
Drone / Aerial ──→ ORI ───────┤
                              │
DSM ──────────────────────────┤
                              │
DTM ──────────────────────────┤
                              ▼
                    DATASET REGISTRY
                              │
                              ▼
                     CRS / QA CHECK
                              │
                              ▼
                     TERRAIN ENGINE
                              │
                    DSM - DTM = nDSM
                              │
                              ▼
                       AI ENGINE
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
          Parcels          Buildings          Roads
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                       VECTOR ENGINE
                              │
                              ▼
                     TOPOLOGY ENGINE
                              │
                              ▼
                    RECONCILIATION ENGINE
                              │
                ┌─────────────┼──────────────┐
                ▼             ▼              ▼
               IoU        Area Error    Boundary Error
                │             │              │
                └─────────────┼──────────────┘
                              ▼
                     ACCURACY ENGINE
                              │
                              ▼
                     QUALITY SCORER
                              │
                              ▼
                         WEBGIS V2
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         Compare          Edit/Review       Validate
              │               │                │
              └───────────────┼────────────────┘
                              ▼
                       VERIFIED PARCEL
                              │
                              ▼
                  Government-Compatible Export
```

------------------------------------------------------------------------

# 83. Final Engineering Definition

BhuDrishti V2 is:

``` text
AI
+
GIS
+
ORI
+
DSM
+
DTM
+
Cadastral Reference Data
+
Spatial Reconciliation
+
Quantitative Accuracy Evaluation
+
Human-in-the-Loop Verification
```

The key difference from a simple image-segmentation system is:

``` text
Existing Record
      +
New Aerial Evidence
      ↓
AI Extraction
      ↓
Spatial Comparison
      ↓
Quantitative Accuracy
      ↓
Human Review
      ↓
Verified Cadastral Dataset
```

This is the intended end-to-end implementation direction for BhuDrishti
V2.
