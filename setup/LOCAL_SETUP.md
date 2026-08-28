# Local production setup

This setup runs the FastAPI application, frontend, PostgreSQL/PostGIS, and SAM locally. Docker is not required. Colab remains available by changing only `PROCESSING_MODE` and `COLAB_AI_ENDPOINT` in `.env`.

## 1. Create the Python environment

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation for the current user, run PowerShell once as your normal user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

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

For local SAM:

```env
SECRET_KEY=paste-the-generated-value-here
DATABASE_URL=postgresql://bhudrishti:replace-with-a-strong-password@localhost:5432/bhudrishti
PROCESSING_MODE=local
LOCAL_SAM_CHECKPOINT=models/sam_vit_b.pth
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

Use one terminal from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

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
