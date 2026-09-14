# BhuDrishti V2 Project Status and Implementation Plan

**Last updated:** September 14, 2026
**Status:** V2 backend foundation is operational; WebGIS product workflow is in progress.
**Live status tracker:** This file records current phase status, completed work, next execution slices, and acceptance evidence.
**Detailed final plan:** [`docs/IMPLEMENTATION_FINAL_PLAN.md`](IMPLEMENTATION_FINAL_PLAN.md) contains the complete implementation, validation, benchmark, and production requirements.

## Product Boundary

BhuDrishti V2 is a production-oriented geospatial cadastral processing workspace. It combines ORI, DSM, DTM, reference cadastral data, AI-derived features, reconciliation, quality evaluation, human review, and structured export.

V1 remains frozen and is not replaced by V2:

- V1 APIs remain under `/api/v1/*`.
- V2 APIs remain under `/api/v2/*`.
- V1 tables and frontend flows remain compatibility surfaces.
- V2 raster files use `data/v2/rasters/`; V2 exports use `data/v2/exports/`.

Production rules:

- No hardcoded state, district, coordinate, parcel, count, accuracy, or progress value in the production UI.
- Accuracy is calculated only from actual AI and reference geometries. Without reference geometry, the UI must say `Not evaluated`.
- Metric geometry calculations use a projected CRS, configured by `LOCAL_UTM_EPSG`.
- Remote reference sources are allowlisted and bounded to the selected state, district, AOI, or test fixture.
- Direct HTTP/API access is preferred for public sources. Browser automation is a last resort and must remain isolated, rate-limited, cached, and limited to selected areas.

## Phase Sequence and Status

Status values: **DONE**, **IN PROGRESS**, **NEXT**, **PLANNED**, **BLOCKED**.

| Phase | Product outcome | Status | Current evidence / scope |
|---|---|---|---|
| 0 | Safety baseline and V1 freeze | DONE | V1/V2 boundary is preserved in `docs/architecture/v1_v2_boundary.md`; regression suite remains green. |
| 1 | V2 foundation, configuration, errors, health, and database boot | DONE | `app/main.py`, `app/core/config.py`, `app/core/exceptions.py`, readiness/liveness routes. |
| 2 | Project, survey-unit, and dataset hierarchy | DONE | V2 models, schemas, project APIs, dataset registry, metadata and checksum validation. |
| 3 | ORI/DSM/DTM ingestion, co-registration, nDSM, and raster tiles | DONE | Raster validation and terrain services are covered by V2 tests; tile API is available. |
| 4 | Durable processing jobs | DONE | Queued/running/succeeded/failed/cancelled lifecycle, polling, cancellation, and recovery. |
| 5 | AI feature extraction and provenance | DONE | Parcel/building/road extraction interfaces and model provenance contracts exist. |
| 6 | Raster-to-vector conversion and geometry cleanup | DONE | Polygonization, metric measurements, simplification, sliver and self-intersection cleanup. |
| 7 | Topology and cross-layer validation | DONE | Persistent validation issues, overlap/sliver checks, and building/parcel checks. |
| 8 | Reference-vs-AI reconciliation | DONE | IoU-based candidate matching and MATCH/MINOR_CHANGE/MAJOR_CHANGE/NEW/MISSING/CONFLICT statuses. |
| 9 | Accuracy and quality evaluation | DONE | Quality API and scoring engine exist; values are computed from supplied geometry and metadata. |
| 10 | Real WebGIS workspace and surveyor review | IN PROGRESS | India-centered Leaflet map, Street/Satellite basemaps, cached India state/district search, searchable project inputs, map fitting, rectangle/polygon AOI persistence, real AI GeoJSON overlay, bearer-authenticated COG tile overlays, reference parcel overlay, color-coded difference map, metric-aware parcel inspector, topology issue overlay, and durable issue resolution delivered. Geometry editing and final review workflow remain. |
| 11 | NAKSHA-compatible export and audit package | DONE | GeoJSON/CSV export, validation gate, schema mapping, and SHA-256 provenance manifest. |
| 12 | Telangana reference-data validation pilot | IN PROGRESS | Allowlisted TGRAC ArcGIS REST provider, bounded query API, normalized reference features, mocked tests, and AOI-gated frontend reference layer delivered. Optional live integration test, persistence, and reconciliation workflow remain. |
| 13 | India-wide administration and provider expansion | PLANNED | State/district lazy search first; then provider adapters for other supported sources and manual GeoJSON/GeoPackage. |
| 14 | Distributed workers | PLANNED | Celery/Redis with separate GPU inference and CPU GIS workers. |
| 15 | Government RBAC and OIDC | PLANNED | Keycloak/OIDC integration and role scopes for ULB admin, GIS supervisor, and field surveyor. |
| 16 | Production packaging and deployment | PLANNED | Containerized API, PostGIS, object storage, workers, monitoring, and migration workflow. |
| 17 | High-resolution performance and field pilot | PLANNED | Multi-gigabyte raster benchmarks, Telangana comparison run, stakeholder handover package. |

## Current Phase 10 Worklist

### Delivered

- Removed the hardcoded SSIPMT-area map center and demo marker.
- Opened V2 over India with a real Leaflet map.
- Added Street map and Satellite imagery switching with attribution.
- Kept the existing Leaflet integration so raster tiles and GeoJSON layers can be added incrementally.
- Made the map responsive and large enough to serve as the primary workspace surface.
- Added authenticated, data-driven state search and state-scoped district search APIs.
- Added a locally cached GADM India level-2 catalog for administrative names and district extents; this is navigation metadata, not authoritative cadastral data.
- Wired project creation State and District inputs to the backend catalog instead of frontend arrays.
- Added validated map fitting to the selected project's district bbox, falling back to the state bbox when a district extent is unavailable.
- Added a real current-map-bounds AOI action that persists on the selected survey unit through the V2 API.
- Added two-click rectangle AOI drawing backed by the same persisted survey AOI contract.
- Added multi-click Polygon AOI drawing with explicit finish action and GeoJSON geometry persistence.
- Added a toggleable AI features overlay that renders only returned GeoJSON features and fits the map through the existing map lifecycle.
- Added bearer-authenticated raster tile overlays for valid registered GeoTIFF/COG datasets through the existing V2 tile API.
- Added an AOI-gated Telangana reference action that fetches bounded ArcGIS GeoJSON and renders a separate `Reference parcels` layer.
- Added actual reconciliation difference geometries: red AI-only, blue reference-only, and green intersection areas.
- Added click inspectors for AI and reference features; unavailable parcel metrics show `N/A` instead of fabricated values.
- Added an AI topology validation action that renders actual backend issue geometries with severity-colored markers and descriptions.
- Added durable topology issue persistence, project issue listing, and reviewer resolution notes with authenticated API actions.

### Next implementation order

1. Add backend administrative data contracts: states, state districts, and bounded search.
2. Add frontend State and District autocomplete with keyboard navigation, loading, empty, and clear states.
3. Add click AOI drawing; rectangle, polygon, and current-bounds AOI persistence are delivered.
4. Add buildings, roads, and richer legends; AI, registered raster, Telangana reference, difference, and topology issue layers are delivered.
5. Add richer Reference/AI/Difference modes backed only by actual API results; parcel inspector and base difference map are delivered.
6. Add geometry editing, reviewer decision states, and connect the final export workflow.

## Phase 12 Telangana Pilot

Telangana is the first public reference-data pilot, not the global backend assumption.

- Provider configuration must hold the TGRAC ArcGIS REST service URL and layer IDs in one place.
- The provider must use bounded ArcGIS REST queries and normalize results into the internal reference parcel contract.
- Tests must mock the remote service for deterministic unit coverage.
- A separate optional live test may query a tiny AOI and must never download a state or district wholesale.
- If the service does not expose usable geometry for a selected AOI, the product must offer manual GeoJSON/GeoPackage import rather than reconstructing parcels from screenshots.
- Added `GET /api/v2/reference/telangana/search` with a bounded WGS84 bbox contract and no user-supplied URL support.
- Added normalization for reference ID, parcel number, survey number, state, source, and source URL while preserving provider properties.
- Added deterministic mocked provider tests; a live public request remains optional and AOI-limited.

## Acceptance Checklist

### Foundation and data

- [x] V2 opens through the existing authenticated frontend route.
- [x] V2 project and dataset APIs exist.
- [x] ORI/DSM/DTM metadata and co-registration validation exist.
- [x] nDSM and raster tile backend services exist.

### WebGIS workflow

- [x] Real interactive map is visible.
- [x] Street/Satellite basemap switch works in the Leaflet implementation.
- [x] State search is data-driven.
- [x] District search is scoped to the selected state.
- [x] Selected state/district fits the map to real administrative bboxes.
- [x] Rectangle AOI can be drawn and persisted.
- [x] Polygon AOI can be drawn, validated, and persisted as GeoJSON.
- [x] Returned AI GeoJSON features render as a toggleable map layer.
- [x] Valid registered raster datasets render through authenticated V2 tile overlays.
- [x] AOI-bounded Telangana reference parcels render as a separate map layer.
- [x] Reconciliation returns and renders actual AI-only, reference-only, and intersection geometries.
- [x] AI/reference feature click opens an inspector with actual metrics or `N/A`.
- [x] Backend topology issues render as a real severity-colored map layer.
- [x] Topology issues can be persisted and resolved with an authenticated reviewer note.
- [x] Current map bounds can be persisted as the survey AOI.
- [ ] Reference, AI, raster, and issue layers render from actual data.
- [x] Parcel inspector shows `N/A` when a metric is unavailable.

### Processing and comparison

- [x] Processing job lifecycle API exists.
- [x] AI extraction and vectorization services exist.
- [x] Reconciliation and quality engines exist.
- [x] Telangana ArcGIS reference provider is implemented and covered by mocked tests.
- [x] Reference-vs-AI difference geometry is visible in the map.
- [ ] Accuracy dashboard is wired to real reconciliation results.
- [x] GeoJSON/CSV export validation and provenance exist.

## Verification Baseline

Run from the repository root:

```bash
pytest -q
node --check frontend/v2/js/map.js
git diff --check
```

Latest recorded result: **66 tests passed**. The test count must be refreshed here whenever tests are added or removed.

## Documentation Policy

- This file is the live implementation-plan status tracker; the detailed final plan is preserved in `docs/IMPLEMENTATION_FINAL_PLAN.md`.
- Architecture documents under `docs/architecture/` remain technical references, not competing roadmaps.
- Setup instructions live only under `setup/` and must match the current API/configuration.
- Do not commit temporary PDFs, notebooks, model weights, raster uploads, tunnel binaries, logs, or local caches.
