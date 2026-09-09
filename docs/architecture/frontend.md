# Frontend Architecture

BhuDrishti uses a framework-free HTML, CSS and ES6 frontend split into a shared layer and two isolated product surfaces.

## Layers

- `frontend/common/` contains design tokens, reusable components, the authenticated API client, session helpers and minimal navigation utilities.
- `frontend/auth/` contains sign-in and registration. A successful login always goes to `portal/index.html`.
- `frontend/portal/` is the authenticated version selector. It links to V1 or V2 and owns no survey-specific behavior.
- `frontend/v1/` preserves the existing dashboard and Leaflet WebGIS. Its dashboard and map scripts remain separate from V2.
- `frontend/v2/` is the survey-processing workspace. Its modules cover projects, datasets, jobs, feature extraction, quality, reconciliation, review presentation and exports.

## Authentication and navigation

`frontend/common/js/api.js` stores the access token and calls `/api/v1` or `/api/v2` through the same `apiFetch()` function. `auth.js` handles login, registration and session storage. Protected pages use `router.js` to redirect missing sessions to `../auth/login.html`.

The browser flow is:

`/index.html` -> `/auth/login.html` -> `/portal/index.html` -> `/v1/` or `/v2/`

The server exposes the same HTML pages through FastAPI routes and mounts their directory trees for relative CSS, JavaScript and asset paths.

## V2 backend connections

The V2 workspace uses only routes currently implemented by the backend:

- Projects: `GET/POST /api/v2/projects`
- Datasets: `GET/POST /api/v2/datasets`, `POST /api/v2/datasets/{id}/validate`
- Jobs: `GET/POST /api/v2/jobs`, `GET /api/v2/jobs/{id}`
- Features: `GET /api/v2/features/manifest`, `POST /api/v2/features/extract`
- Quality: `POST /api/v2/quality/report`
- Reconciliation: `POST /api/v2/reconciliation/compare`
- Exports: `POST /api/v2/exports/geojson`, `POST /api/v2/exports/csv`

Job creation represents the backend's HTTP 202 response and polls the returned job ID. The UI does not invent persisted feature review or field-action endpoints. Review state is clearly labeled session-local until the backend exposes a persistence contract. NAKSHA is presented as backend package preparation only; no live NAKSHA integration is fabricated.

## Path conventions

Pages use paths relative to their owning directory. Shared files are referenced with `../common/...`; V1 files use `./css`, `./js` and `../common`; V2 files use `./css`, `./js` and `../common`. New V2 behavior must stay inside `frontend/v2/` and shared code must remain genuinely version-neutral.