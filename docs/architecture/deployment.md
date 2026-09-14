# BhuDrishti V2 — Practical Deployment Architecture

---

## 1. System Overview

BhuDrishti V2 is designed as a clean, modular, and lightweight cadastral processing platform. It avoids unnecessary distributed cluster overhead in favor of an efficient, reproducible single-instance deployment model with an asynchronous background task queue.

```mermaid
flowchart TB
    CLIENT["Web Browser\n(Leaflet WebGIS UI)"]
    
    subgraph AppServer ["BhuDrishti Application Host"]
        API["FastAPI / Uvicorn ASGI Server\n(Endpoints: /api/v1/*, /api/v2/*)"]
        QUEUE["In-Process Task Queue\n(Thread-based background worker)"]
        AI["AI Segmentation Engine\n(PyTorch SAM ViT-B / GPU or CPU)"]
        STORAGE["Local File Storage\n(data/v2/rasters, data/v2/exports)"]
    end

    DB[(PostgreSQL + PostGIS\nSpatial Database)]

    CLIENT -->|HTTPS / REST API| API
    API -->|Read / Write Jobs & Features| DB
    API -->|Submit Processing Task| QUEUE
    QUEUE -->|Execute Inference| AI
    QUEUE -->|Read/Write Rasters & Exports| STORAGE
    QUEUE -->|Update Job Status| DB
```

---

## 2. Core Components

| Component | Technology | Responsibility |
|---|---|---|
| **Web / API Server** | FastAPI 0.110+ on Uvicorn | Serves static WebGIS frontends (`/v1`, `/v2`, `/portal`), REST APIs, and raster tiles. |
| **Spatial Database** | PostgreSQL 15+ with PostGIS 3.3+ | Persists users, parcels, projects, surveys, datasets, and validation issues with spatial geometry indexing. |
| **Job Execution** | Durable DB Queue + Thread Worker | Manages long-running AI extraction and raster processing jobs asynchronously without locking HTTP connections. |
| **AI Inference** | PyTorch + SAM ViT-B | Runs boundary segmentation locally using available CUDA GPU, falling back to CPU or Google Colab tunnel. |
| **File Storage** | Local filesystem (`data/`) | Stores GeoTIFF rasters (`data/v2/rasters/`) and generated export packages (`data/v2/exports/`). |

---

## 3. Environment & Configuration

All runtime configurations are managed through `.env`:

```ini
# Core
APP_NAME=BhuDrishti
API_PREFIX=/api
PROCESSING_MODE=local   # 'local' or 'colab'

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bhudrishti

# Security
SECRET_KEY=change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI & Computing
LOCAL_SAM_CHECKPOINT=models/sam_vit_b.pth
LOCAL_SAM_MODEL_TYPE=vit_b
LOCAL_SAM_DEVICE=auto   # 'auto' selects cuda if available, otherwise cpu

# Cadastral Defaults
LOCAL_UTM_EPSG=EPSG:32643
ULPIN_STATE_CODE=22
ULPIN_DISTRICT_CODE=10
```

---

## 4. Operational Health & Probes

* **Liveness Probe** (`GET /health`): Returns HTTP 200 indicating the ASGI server is alive and responding.
* **Readiness Probe** (`GET /ready`): Queries PostgreSQL (`SELECT 1`) to ensure the database connection is operational. Returns HTTP 503 if database connectivity is down.

---

## 5. Running in Production

### Direct Execution
```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> [!NOTE]
> For production environments, run Uvicorn behind a standard reverse proxy (such as Nginx or Caddy) for SSL termination and static asset caching.
