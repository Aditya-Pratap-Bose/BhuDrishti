# BhuDrishti — Future Implementation Plan

> **V2 upgrade baseline (2026-09):** v1 remains the stable fallback contract. New
> spatial tiling, ORI/DTM processing, topology validation, and asynchronous
> processing work is being added only under `/api/v2` and new `app/v2` service
> modules. Existing v1 routes, authentication dependencies, schemas, and
> frontend flow are not being changed unless a shared bug fix is required.

## V2 Execution Status

### Completed in the current v2 slice
- keep the existing v1 API and auth flow intact as the fallback layer
- dedicated v2 service boundary for raster ingestion and COG preparation
- DTM-derived structural prompt extraction and reusable topology cleanup
- authenticated XYZ tiles from validated COG assets
- authenticated geometry quality validation without persistence side effects,
  including overlap area, near-duplicate detection, sliver flags, and
  area/perimeter metrics
- authenticated, bounded preliminary feature extraction for building, road,
  access-corridor, and land-use GeoJSON review layers
- explicit v2 feature-layer contracts and capability manifest for SIH 26012
- reproducible v2 geospatial dependencies and configurable upload/tile limits
- bounded ORI/DTM upload validation and atomic COG publication

### Remaining production milestones
- distributed worker/queue execution on top of the durable v2 processing job
  foundation (the current bounded in-process worker is staging-only)
- frontend v2 tile/layer wiring behind an explicit v2 opt-in
- multimodal SAM/FastSAM inference using DTM prompts
- PostGIS v2 schema migrations and persisted quality/review state
- containerized deployment, observability, and operational runbooks

### Current blocker: Codespace restart/refresh loop

The API intentionally fails during startup when PostgreSQL/PostGIS is not
reachable. In a Codespace this can look like repeated refreshes when a process
manager restarts the failed Uvicorn process. This is not a fallback condition:
v1 authentication and parcel persistence must never silently switch to
in-memory or SQLite storage.

Before launching the API, copy `.env.example` to `.env`, set a reachable
`DATABASE_URL`, and verify PostgreSQL has the PostGIS extension enabled. For a
stable demo, start without `--reload`; use `--reload` only after the database
preflight succeeds.

### Version and data policies

Version selection is URL-based, not a user-facing login setting. Shared v1
authentication remains the entry point while both API prefixes are deployed.
The v1 workspace stays the default until the complete v2 frontend workflow is
verified.

Current v2 raster and quality endpoints are non-persistent for parcel records.
Before persistence, add an Alembic migration with versioned processing/job
tables, ownership, audit, and retention fields. Never implicitly mutate the
existing v1 `parcels` table.

### Next milestones
1. **Raster foundation:** validate ORI/DTM CRS, bounds, resolution, and
   co-registration; convert uploads to Cloud Optimized GeoTIFFs.
   *(Upload orchestration and atomic COG publication are now in place.)*
2. **Tile delivery:** serve bounded XYZ tiles from COGs through v2, with
   backend-side raster reads so browsers never load a full survey raster.
   *(Initial endpoint and COG renderer are now in place.)*
3. **Multimodal extraction:** make DTM prompts optional and feed them into the
   existing SAM-compatible engine, with an explicit model/version in results.
4. **Topology and quality:** repair invalid polygons, remove overlaps/slivers,
   calculate quality flags, and only then persist verified records.
5. **Async jobs:** use the durable v2 `processing_jobs` records and validated
   status transitions for large-area worker execution; keep the current
   synchronous v1 processing path untouched.
6. **Deployment hardening:** add migrations and container packaging only after
   the local v2 path is proven.

### Compatibility guardrails
- `/api/v1/*` remains the production fallback and is not routed through v2.
- v2 reuses the existing `get_current_user` dependency and parcel contracts
  where compatible; no second auth system is introduced.
- Optional dependencies must fail with clear v2 errors, never silently alter
  v1 behavior.
- Each milestone must be verified with targeted tests before frontend wiring.

## 1. Project Goal

BhuDrishti is intended as an AI-enabled cadastral mapping platform for urban parcel extraction, building footprint detection, road/access corridor identification, and land-use classification from high-resolution drone and orthorectified imagery. The current repo is a strong MVP foundation, but it still needs additional GIS, ML, and validation work to become a production-grade solution that matches the SIH urban cadastral brief.

This document is meant to be honest about what is already implemented and what remains to be built.

---

## 2. Current Status

### Completed / Working in the current repo
- FastAPI backend for parcel and satellite workflows
- Frontend dashboard and workspace UI
- Parcel GeoJSON generation flow
- Local SAM-based segmentation flow
- Drone GeoTIFF upload support
- PostGIS-ready database schema and parcel storage
- ULPIN generation logic
- Basic map-based review interface
- Basic GIS post-processing and simplification

### Still missing / not production-grade
- DSM/DTM integration
- trained building footprint extraction
- trained road / access corridor extraction
- trained land-use classification pipeline
- Topology validation for cadastral integrity
- Ground truth review workflow
- Surveyor workflow for parcel acceptance/rejection
- Data quality scoring and confidence output
- Production-grade deployment hygiene and repeatable setup

---

## 3. Short-Term Objective (Next 4–6 Weeks)

Focus on making the current project look and behave like a real SIH-ready prototype without introducing container-heavy complexity.

### A. Make the AI workflow more realistic
- Add a multi-source raster pipeline for:
  - ORI / orthophoto imagery
  - DSM
  - DTM
  - optional vector parcel overlays
- Keep the current SAM-based parcel segmentation as the base model
- Add a second stage for parcel cleanup and cadastral refinement
- Record confidence scores for each extracted parcel

### B. Add essential GIS quality checks
- Remove tiny sliver polygons
- Detect overlapping polygons
- Detect gap/missing zones
- Detect invalid geometries
- Flag parcel intersections and near-duplicates
- Validate coordinate/reference system consistency

### C. Build a review workflow
- Add a parcel review screen with accept/reject state
- Add manual editing support for obvious bad polygons
- Add a save-as-draft or approval flow
- Mark uncertain parcels for technician review

### D. Improve setup quality
- Ensure requirements are clean and reproducible
- Add a proper local environment checklist
- Document the GPU setup clearly
- Document the expected workflow for each data source

---

## 4. Medium-Term Objective (6–10 Weeks)

### A. Building footprint detection
Add a separate building extraction module that runs on high-resolution imagery and optionally DSM.

Goals:
- detect roof footprints
- separate building polygons from parcel polygons
- identify mismatches between parcel edges and footprint edges
- flag probable encroachments

Implementation approach:
- Use a segmentation model or object-detection model for building footprints
- Post-process output with polygon cleanup and topology checks
- Save output in a separate `buildings` layer

### B. Road and access corridor detection
Add a road network layer using imagery + vector cleanup.

Goals:
- detect primary and secondary roads
- detect narrow access corridors
- separate roads from parcel boundaries
- identify missing connectivity or invalid parcel access

Implementation approach:
- segmentation or line extraction pipeline
- morphological cleanup
- vector conversion to road polylines

### C. Land-use classification
Add a land-use tagging model or heuristic classification layer.

Goals:
- residential
- commercial
- industrial
- institutional
- water
- vegetation
- vacant
- mixed-use

Implementation approach:
- image-based classifier using feature embeddings or segmentation context
- fallback rule-based labels if model is not available

---

## 5. Production-Grade Components That Should Exist

Even without Docker, the repo should still be organized like a serious product.

### A. Data pipeline
- Input image ingestion
- validation of CRS and bounds
- metadata capture
- source tracking
- processing logs

### B. AI pipeline
- model version tracking
- checkpoint path management
- inference confidence logs
- fallback behavior for model failure

### C. GIS validation layer
- geometry validity
- overlap detection
- sliver removal
- topology correctness
- area/perimeter checks
- standard output format

### D. Review layer
- parcel approval/rejection states
- technician notes
- correction history
- export-ready final parcel map

### E. Project hygiene
- clean requirements file
- local env instructions
- GPU and CPU mode management
- reproducible commands
- clear README with status and roadmap

---

## 6. Recommended Development Order

### Phase 1: Must-have for demo + judges
1. Fix the local SAM initialization and GPU detection path
2. Clean and stabilize the environment setup
3. Add DSM/DTM awareness to the processing pipeline
4. Add parcel quality filters and topology checks
5. Add a review/approve layer for parcel outputs
6. Improve the frontend to show multiple layers (parcel, building, roads)

### Phase 2: Strong SIH story
1. Building footprint module
2. Road detection module
3. Land-use classification
4. Validation confidence metrics
5. Better dataset and sample outputs

### Phase 3: Hardening and polish
1. Logging and error tracking
2. Reproducible local setup
3. QA checklist
4. Sample final report for demo

---

## 7. Scope for a Single Developer

Since this is being built mostly by one person, the scope must stay realistic.

### Doable this semester
- parcel extraction with better cleanup
- building footprint extraction (basic version)
- road/access corridor detection (basic detection layer)
- land-use tagging (rule-based or basic classifier)
- topology validation module
- review workflow UI

### Avoid for now
- full end-to-end nationwide deployment
- complex multi-model server orchestration
- heavy cloud infrastructure
- excessive production deployment architecture
- Docker complexity for now

This project should be treated as a focused SIH-grade prototype, not a giant government platform rollout.

---

## 8. Suggested Module Structure for Future Work

Add these modules in the repo structure:

```text
app/
  services/
    ai/
      sam_engine.py
      building_detector.py
      road_detector.py
      landuse_classifier.py
    gis/
      topo_validator.py
      dsm_dtm_processor.py
      vector_quality_checks.py
  api/
    v1/
      review.py
      gis_layers.py
```

And add UI support for:
- parcel layer
- building layer
- road layer
- land-use labels
- review and approval panel

---

## 9. What to mention in the final project report

The repo should clearly state that:
- the current version is a strong MVP prototype for automated urban parcel extraction
- the system is designed for future extension to DSM/DTM, buildings, roads, and land-use classification
- the next step is not full deployment but functional SIH-grade cadastral intelligence with review and validation workflows

This honesty makes the project appear mature and realistic instead of over-claiming.

---

## 10. Final Recommendation

If the goal is to build a project that is credible for SIH and still realistic for one student working alone, the best strategy is:

- keep the core parcel extraction engine strong
- build a clear modular extension path
- add review, validation, and classification modules in a practical order
- avoid over-engineering infra before the core AI/GIS value is solid

This approach is feasible, presentable, and convincing for judges.

---

## 11. Suggested next file to create

Create a project status markdown file next to this one, such as:

- `setup/PROJECT_STATUS.md`

This file can say exactly:
- what is already done
- what remains
- what is in progress
- what is planned for the final SIH submission

This makes the repo look professional and transparent.
