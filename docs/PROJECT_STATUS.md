# BhuDrishti V2 Project Status and Implementation Plan

**Last updated:** September 14, 2026
**Status:** Full GIS/WebGIS prototype is working in small tested slices; real-data validation and editing are still in progress.
**Live status tracker:** This file records current phase status, completed work, next execution slices, and acceptance evidence.
**Detailed final plan:** [`docs/IMPLEMENTATION_FINAL_PLAN.md`](IMPLEMENTATION_FINAL_PLAN.md) contains the complete implementation, validation, benchmark, and production requirements.

## Product Boundary

BhuDrishti V2 is a student-built full GIS/WebGIS prototype. It combines ORI, DSM, DTM, reference data, AI-derived features, reconciliation, quality checks, map review, and local GIS export. It is not an official government land-record system.

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
- A passing unit test means the code path works for the test input; it does not mean the system is validated on real survey data.

## Phase Sequence and Status

Status values: **DONE**, **IN PROGRESS**, **NEXT**, **PLANNED**, **BLOCKED**.

| Phase | Product outcome | Status | Current evidence / scope |
|---|---|---|---|
| 0 | V1 safety and V2 separation | [x] COMPLETE | V1/V2 boundary documented; regression suite remains green. |
| 1 | Basic backend setup and error handling | [x] COMPLETE | FastAPI app, config, health/readiness, database boot, and structured errors. |
| 2 | Projects, surveys, and datasets | [x] COMPLETE | Project APIs, survey units, dataset registry, metadata and checksum checks. |
| 3 | ORI/DSM/DTM checks and raster tiles | [x] COMPLETE (code/tests) | Raster metadata, co-registration, nDSM services, COG/tile API. Real large survey testing is pending. |
| 4 | Processing jobs | [x] COMPLETE (code/tests) | Queued/running/succeeded/failed/cancelled lifecycle and recovery tests. |
| 5 | AI feature extraction | [x] COMPLETE (code/tests) | Parcel/building/road interfaces and provenance fields. Real model quality is not yet benchmarked. |
| 6 | Raster-to-vector and geometry cleanup | [x] COMPLETE (code/tests) | Polygonization, metric measurements, simplification, and cleanup tests. |
| 7 | Topology checks and issue review | [x] COMPLETE (code/tests) | Overlap/sliver/cross-layer checks, persisted issues, and resolution notes. |
| 8 | Reference vs AI comparison | [x] COMPLETE (code/tests) | IoU comparison, status categories, and difference geometries. Real reference benchmark pending. |
| 9 | Accuracy and quality calculations | [x] COMPLETE (code/tests) | Quality API and calculation code exist; real-data accuracy report pending. |
| 10 | Full GIS/WebGIS workspace and review | [~] IN PROGRESS | Map, basemaps, admin search, map fitting, AOI, AI/raster/reference layers, difference map, parcel inspector, topology issue layer, and issue resolution are working. Geometry editing and final review workflow remain. |
| 11 | Local GIS export and file manifest | [x] COMPLETE (code/tests) | GeoJSON/CSV export, local validation gate, and SHA-256 manifest. Not an official NAKSHA submission. |
| 12 | Telangana reference-data test | [~] IN PROGRESS | Bounded TGRAC provider, normalized features, mocked tests, and AOI-gated map layer are working. Live request, saved reference records, and real accuracy benchmark remain. |
| 13 | India-wide admin and provider expansion | [ ] NOT STARTED | More providers, manual GeoJSON/GeoPackage import, and deeper hierarchy. |
| 14 | Optional worker scaling | [ ] NOT STARTED | Celery/Redis only if larger processing workloads require it. |
| 15 | Optional user roles/login improvements | [ ] NOT STARTED | Stronger roles and identity integration for a future deployment. |
| 16 | Optional deployment packaging | [ ] NOT STARTED | Docker, migrations, storage, backups, and monitoring. |
| 17 | Real-data benchmark and field test | [ ] NOT STARTED | Telangana comparison, large raster test, and student project evidence. |

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

1. Add click AOI drawing; rectangle, polygon, and current-bounds AOI persistence are delivered.
2. Add buildings, roads, and richer legends; AI, registered raster, Telangana reference, difference, and topology issue layers are delivered.
3. Add richer Reference/AI/Difference modes backed only by actual API results; parcel inspector and base difference map are delivered.
4. Add geometry editing, reviewer decision states, and connect the final export workflow.

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
- [x] Reference, AI, raster, and issue layers have real-data API/map paths; broad real-survey validation is still pending.
- [x] Parcel inspector shows `N/A` when a metric is unavailable.

### Processing and comparison

- [x] Processing job lifecycle API exists.
- [x] AI extraction and vectorization services exist.
- [x] Reconciliation and quality engines exist.
- [x] Telangana ArcGIS reference provider is implemented and covered by mocked tests.
- [x] Reference-vs-AI difference geometry is visible in the map.
- [ ] Accuracy dashboard is wired to a real Telangana benchmark result.
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
