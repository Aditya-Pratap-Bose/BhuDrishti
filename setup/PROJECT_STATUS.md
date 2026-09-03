# BhuDrishti Project Status

## Current status (2026-09-03)

This repository is a functional MVP for AI-assisted cadastral parcel extraction and review. It demonstrates the core workflow for:

- satellite / drone imagery ingestion
- raster processing
- SAM-based segmentation
- polygon vector generation
- basic cadastral parcel output
- web-based GIS review
- saving parcels in a database

The v2 upgrade has started as an additive layer. The existing v1 flow remains
the stable fallback, including its routes and authentication dependency.

This is a good starting point, but it is not yet a complete production-grade urban cadastral system matching the full SIH brief.

## What is complete

- backend API stack with FastAPI
- parcel storage and retrieval flow
- satellite AOI processing flow
- drone GeoTIFF upload flow
- local SAM-based parcel extraction
- map visualization and frontend review
- ULPIN generation logic
- basic parcel cleanup and simplification

## V2 implementation started

- v2-only raster service for CRS/bounds inspection, ORI/DTM co-registration
  checks, and COG-compatible conversion
- v2 DTM gradient-based structural prompt extraction
- v2 cadastral topology repair and quality reporting
- authenticated `POST /api/v2/quality/validate` endpoint that returns
  non-persistent cleaned geometries, overlap area, near-duplicate detection,
  sliver flags, and area/perimeter metrics
- authenticated `/api/v2/tiles/{asset_id}/{z}/{x}/{y}.png` endpoint for
  backend-rendered COG tiles with bounded asset and coordinate access
- authenticated `POST /api/v2/raster/upload` endpoint for bounded ORI/DTM
  uploads, CRS/overlap validation, atomic COG publication, and metadata
- durable SQLAlchemy-backed v2 `processing_jobs` table registered during
  startup, with authenticated create/get/list/cancel endpoints and
  database-locked, terminal-safe status transitions
- bounded in-process v2 worker with queued-job recovery after a clean process
  restart; this is a staging worker, not a horizontally scalable queue
- focused `unittest` smoke checks for job persistence, ownership, and lifecycle
  transitions
- frontend workspace selector with v1 stable default and opt-in v2 preview
  routing for compatible satellite bbox extraction
- authenticated v2 capability manifest documenting parcel, building, road,
  access-corridor, and land-use layer readiness
- authenticated `POST /api/v2/features/extract` endpoint producing bounded,
  reviewable preliminary building, road, access-corridor, and land-use
  GeoJSON layers from validated raster assets; the model/version and confidence
  are included in every feature
- opt-in V2 workspace panel for paired ORI/DTM upload and authenticated ORI
  COG tile preview; V1 remains the default
- configurable `V2_RASTER_DIR` and maximum tile zoom settings
- `rio-tiler` and `titiler.core` added to the reproducible requirements

## V2 production readiness boundary

The implemented v2 slice is suitable for local/staging demonstration of
validated raster ingestion, COG tile delivery, DTM prompts, non-persistent
geometry quality checks, and durable job state. It is not yet a complete
production deployment: a distributed queue, frontend v2 layer wiring,
versioned PostGIS migrations, persisted review state, and
container/observability setup remain before a production claim is appropriate.

## What remains to be completed

- production DSM / DTM integration with registered survey CRS metadata
- trained building footprint extraction
- trained road and access corridor detection
- trained land-use classification
- cadastral topology validation with persisted review decisions
- ground truth review workflow
- surveyor approval workflow
- production-grade QA and data validation
- stronger project documentation and milestone plan

## Honest project assessment

The current implementation is best described as an AI-backed cadastral prototype and proof-of-concept, not a full final urban land records system.

It is strong enough to demonstrate feasibility and technical capability, but additional GIS and AI modules are required before it can be presented as a complete solution to the full brief.

## Priority for final improvement

The next priorities are:

1. wire the v2 workspace to authenticated raster tiles and feature layers
2. replace threshold baselines with evaluated building/road/access models
3. add persisted quality review and surveyor approval without touching v1
4. add versioned PostGIS migrations and audit/retention fields
5. add a distributed worker adapter and operational observability

## Scope note

Given the project is being developed by a single student without a large team, the realistic target is a focused SIH-ready prototype covering the core cadastral pipeline rather than a fully deployed nationwide land governance platform.

This repo still has a strong foundation and is a valid direction for further work.
