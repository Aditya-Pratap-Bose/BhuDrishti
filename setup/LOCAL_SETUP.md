# Local production setup

This setup runs the FastAPI application, frontend, PostgreSQL/PostGIS, and SAM locally. Docker is not required. Colab remains available by changing only `PROCESSING_MODE` and `COLAB_AI_ENDPOINT` in `.env`.

## 1. Create the Python environment

> **Production recommendation:** use **Python 3.11** on a machine with a CUDA-capable GPU if local SAM inference is required. The app will prefer `cuda` automatically when available; otherwise it falls back to `cpu`.
>
> *Note:* The project intentionally uses `rasterio` + `Pillow` for tile stitching to avoid the common Windows-native GDAL failure mode. `gdal` is not required for the normal production workflow.

### Standard Setup (Python 3.11 Virtual Environment)

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks script execution for the current user, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### GPU-enabled machine

If the host has NVIDIA CUDA support, install the matching PyTorch build before the project requirements:

```powershell
python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch
python -m pip install -r requirements.txt
```

If vector export fails with `GDAL DLL could not be found`, install the GDAL/pyogrio stack from conda-forge or install `pyogrio` and the matching GDAL runtime:

```powershell
conda install -c conda-forge gdal pyogrio -y
```

Then keep `.env` as:

```env
LOCAL_SAM_DEVICE=auto
LOCAL_SAM_USE_CUDA_IF_AVAILABLE=true
```

---

### Alternative: Using Miniconda / Conda

If you prefer managing dependencies with Conda:

```powershell
conda create -n bhu -c conda-forge python=3.11 -y
conda activate bhu
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For a GPU machine, install the CUDA-enabled PyTorch build in that environment instead of the default CPU build.

## 2. Prepare PostgreSQL and PostGIS

Create a PostgreSQL database and enable PostGIS using `psql` as a PostgreSQL administrator:

```sql
CREATE USER bhudrishti WITH PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE bhudrishti OWNER bhudrishti;
\connect bhudrishti
CREATE EXTENSION IF NOT EXISTS postgis;
```

The application creates its tables at startup. For a real production deployment, replace that startup table creation with versioned Alembic migrations before changing the schema.

## 3. Generate a secret key

Generate a new secret on each deployment machine. Do not commit it:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the printed value into `.env` as `SECRET_KEY`. Do not use the example value.

## 4. Create `.env`

Copy `.env.example` to `.env` and replace the placeholders:

```powershell
Copy-Item .env.example .env
```

For local SAM on a GPU-capable machine:

```env
SECRET_KEY=paste-the-generated-value-here
DATABASE_URL=postgresql://bhudrishti:replace-with-a-strong-password@localhost:5432/bhudrishti
PROCESSING_MODE=local
LOCAL_SAM_CHECKPOINT=models/sam_vit_b.pth
LOCAL_SAM_DEVICE=auto
LOCAL_SAM_USE_CUDA_IF_AVAILABLE=true
STAC_API_URL=https://planetarycomputer.microsoft.com/api/stac/v1
STAC_COLLECTION=sentinel-2-l2a
STAC_DATE_RANGE=2023-01-01/2026-08-26
STAC_MAX_CLOUD_COVER=10
LOCAL_UTM_EPSG=32643
CORS_ORIGINS=[]
```

For Colab instead:

```env
PROCESSING_MODE=colab
COLAB_AI_ENDPOINT=https://the-current-colab-tunnel.trycloudflare.com
```

Keep `DATABASE_URL` in both modes because users and saved parcels always live in PostgreSQL.

## 5. Download the local SAM checkpoint

Create the ignored model directory and download the ViT-B checkpoint:

```powershell
New-Item -ItemType Directory -Force models | Out-Null
Invoke-WebRequest `
  -Uri 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth' `
  -OutFile 'models/sam_vit_b.pth'
```

The file is large and is intentionally ignored by Git. Every laptop that runs `PROCESSING_MODE=local` needs its own copy.

## 6. Start the application
 
Use one terminal from the repository root. For a stable demo, start without
`--reload`; the API intentionally stops if PostgreSQL/PostGIS is unavailable,
which otherwise can appear as a repeated Codespace refresh when a supervisor
restarts it:
 
**With Conda (Environment `bhu`):**
```powershell
conda activate bhu
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
 
**With standard venv:**
```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On Linux/codespaces, use the same module form:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

After the database preflight succeeds, `--reload` may be added for source
editing during development.

Before starting, verify that `.env` exists and PostgreSQL/PostGIS is accepting
connections at the configured `DATABASE_URL`. The application creates its
tables during startup, so the server will intentionally stop rather than
serve authenticated routes against an unavailable database.

Open the frontend in a browser:

```text
http://127.0.0.1:8000/
```

The same server provides:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

Register a Surveyor account from the frontend, then sign in. Admin and Tehsildar accounts must be assigned by an administrative workflow; public registration cannot create them.

## 7. Switch engines

Restart Uvicorn after changing `.env`.

Local engine:

```env
PROCESSING_MODE=local
```

Colab engine:

```env
PROCESSING_MODE=colab
COLAB_AI_ENDPOINT=https://current-tunnel-url.trycloudflare.com
```

The laptop backend calls Colab at `COLAB_AI_ENDPOINT/process`. `localhost:8000` is the laptop API and must not be used as the Colab endpoint.

## 8. What local processing does

For each selected map rectangle, the local engine:

1. Searches Planetary Computer for a low-cloud Sentinel-2 scene.
2. Downloads the signed visual asset and crops it to the rectangle.
3. Runs the local `SamGeo` model.
4. Converts the mask to vector polygons.
5. Splits multipart output into individual polygons.
6. Calculates area and perimeter in the configured UTM CRS.
7. Returns the backend `FeatureCollection` contract.
8. Lets the backend validate and save the result in PostGIS.

The first local request can be slow and CPU inference may be impractical on a low-spec machine. In that case, use `PROCESSING_MODE=colab`; the database and frontend flow remain unchanged.

## 9. Ye batch ke naye changes

- Naya endpoint: `POST /satellite/process-drone` — drone/custom GeoTIFF
  upload karta hai. Ye HAMESHA local SAM engine use karta hai, chahe
  `.env` mein `PROCESSING_MODE=colab` ho — isliye `LOCAL_SAM_CHECKPOINT`
  set hona aur model download hona zaroori hai even agar bbox flow ke
  liye Colab use kar rahe ho.
- Naye pip deps: `Pillow`, `numpy`. Dobara chalao:
```powershell
  python -m pip install -r requirements.txt
```
- DB schema change: `parcels` table mein naya `owner_name` column aaya
  hai. Agar Supabase project bilkul naya hai, `init_db()` khud bana
  dega restart pe. Agar pehle se `parcels` table exist karta hai, Supabase
  SQL editor mein ye chalao:
```sql
  ALTER TABLE parcels ADD COLUMN IF NOT EXISTS owner_name VARCHAR(150);
```
- Route rename: `PATCH /parcels/{id}/land-use` ab `PATCH /parcels/{id}`
  hai (body mein `land_use_type` aur/ya `owner_name` dono accept karta hai).

## 10. Choosing v1 or v2

Both API versions run in the same FastAPI process:

- v1: `/api/v1/...` — stable frontend and existing parcel save flow.
- v2: `/api/v2/...` — COG tiles, ORI/DTM ingestion, and topology quality
  validation, and durable processing jobs.

Choose the version per request in the URL. Authentication is shared; login
remains at `/api/v1/auth/login`. The browser UI intentionally remains v1 by
default until v2 upload, tile, save, and review support is fully wired.

v2 raster upload and quality validation do not write to the existing v1
`parcels` table. COG files use `V2_RASTER_DIR`, and quality results are
non-persistent. Processing requests can be persisted in the v2
`processing_jobs` table without changing v1 tables:

```text
POST  /api/v2/jobs                 # create a queued job
GET   /api/v2/jobs/{job_id}        # fetch an owned job
PATCH /api/v2/jobs/{job_id}/status # worker/owner lifecycle update
```

All job endpoints require the existing bearer token. Jobs are scoped to their
creator, and transitions are locked and validated (`queued -> running ->
succeeded|failed|cancelled`; dispatch can also fail directly). Terminal jobs
cannot be reopened. `init_db()`
registers this table at startup; use a versioned migration before applying
schema changes to an existing production database.

In the workspace, **V1 Stable** is selected by default. **V2 Preview** changes
only the compatible satellite bbox extraction request; parcel loading, editing,
and saving continue through the stable v1 APIs. Drone processing remains v1
unless V2 is selected: V2 then exposes a paired ORI/DTM upload panel and adds
the prepared ORI COG as an authenticated map tile layer. Parcel extraction and
saving still remain on the stable V1 contract.

## 11. V2 job smoke check

This repository has no external test runner yet. Run the focused persistence
and transition checks after installing requirements:

```powershell
python -m unittest tests.test_v2_jobs_smoke -v
```

The check uses an isolated SQLite database only for verification. The running
API always uses the configured `DATABASE_URL`; it has no in-memory job
fallback.

## 12. Drone GeoTIFF request specification

Ask the college lab for a processed, orthorectified, georeferenced drone
orthomosaic, not raw camera photographs. Preferred deliverables:

- `.tif` or `.tiff` GeoTIFF
- RGB or RGBN orthomosaic
- embedded CRS, preferably the survey's local UTM CRS
- embedded affine geotransform and real-world bounds
- companion DTM GeoTIFF with the same CRS and overlapping footprint

A GeoTIFF is an image plus map metadata. It is not merely a renamed JPEG.
Photogrammetry software such as Pix4D, DJI Terra, WebODM, or Agisoft normally
converts the camera photos into the orthomosaic before upload.

The v2 upload flow streams files with size limits, validates GeoTIFF readability,
checks CRS and overlap, converts both files to tiled compressed COGs, publishes
them atomically, and serves map tiles without loading the full raster in the
browser. The existing v1 drone endpoint remains separate: it accepts one
GeoTIFF, runs local SAM, and does not require a DTM.