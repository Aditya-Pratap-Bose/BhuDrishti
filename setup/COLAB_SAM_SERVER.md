# BhuDrishti Colab SAM server

Run these cells in order in one Google Colab notebook. The laptop backend calls the public URL printed by the final cell.

## 1. Install and mount Drive

```python
from google.colab import drive
drive.mount('/content/drive')

!pip install -q segment-geospatial pystac-client planetary-computer rioxarray geopandas fastapi uvicorn nest-asyncio requests
```

## 2. Load the model before constructing SamGeo

```python
import hashlib
import json
import os
import shutil

import geopandas as gpd
import planetary_computer
import pystac_client
import rioxarray
from samgeo import SamGeo

MODEL_DIR = '/content/drive/MyDrive/BhuDrishti_models'
os.makedirs(MODEL_DIR, exist_ok=True)
CHECKPOINT_PATH = os.path.join(MODEL_DIR, 'sam_vit_b.pth')
# CACHE_CHECKPOINT_PATH is where SamGeo usually downloads checkpoints
CACHE_CHECKPOINT_PATH = '/root/.cache/torch/hub/checkpoints/sam_vit_b_01ec64.pth'

# Initialize sam variable
sam = None

# If the checkpoint is not in the desired MODEL_DIR
if not os.path.exists(CHECKPOINT_PATH):
    print("Model checkpoint not found in MODEL_DIR. Attempting to download via SamGeo...")
    # Initialize SamGeo without a specific checkpoint path to trigger download
    # It will download the model to CACHE_CHECKPOINT_PATH if not already present
    temp_sam = SamGeo(model_type='vit_b', sam_kwargs=None)

    # Now, check if the model has been downloaded to the cache
    if os.path.exists(CACHE_CHECKPOINT_PATH):
        print(f"Model downloaded to cache. Copying from {CACHE_CHECKPOINT_PATH} to {CHECKPOINT_PATH}")
        shutil.copy2(CACHE_CHECKPOINT_PATH, CHECKPOINT_PATH)
        # Re-initialize SamGeo with the checkpoint from MODEL_DIR for consistent use
        sam = SamGeo(model_type='vit_b', checkpoint=CHECKPOINT_PATH, sam_kwargs=None)
    else:
        # This case should ideally not happen if SamGeo successfully downloads
        raise RuntimeError(f"SamGeo failed to download the model to {CACHE_CHECKPOINT_PATH}. Please check network connectivity or SamGeo setup.")
else:
    print(f"Using model checkpoint from {CHECKPOINT_PATH}")
    # If checkpoint is already in MODEL_DIR, just initialize SamGeo with it
    sam = SamGeo(model_type='vit_b', checkpoint=CHECKPOINT_PATH, sam_kwargs=None)


print('Setup done. Model ready:', os.path.exists(CHECKPOINT_PATH))

catalog = pystac_client.Client.open(
    'https://planetarycomputer.microsoft.com/api/stac/v1',
    modifier=planetary_computer.sign_inplace,
)
```

## 3. Processing and response contract

```python
def generate_ulpin(centroid_lat, centroid_lon):
    coord_string = f'{centroid_lat:.6f}_{centroid_lon:.6f}'
    digest = hashlib.sha256(coord_string.encode()).hexdigest()[:20].upper()
    return f'COLAB-{digest}'


def process_area(bbox, utm_epsg=32643):
    search = catalog.search(
        collections=['sentinel-2-l2a'],
        bbox=bbox,
        datetime='2023-01-01/2026-08-26',
        query={'eo:cloud_cover': {'lt': 10}},
    )
    items = list(search.items())
    print(len(items), 'images mile')
    if not items:
        raise ValueError('Is area/date range me koi Sentinel-2 image nahi mili')

    selected_item = min(
        items,
        key=lambda item: item.properties.get('eo:cloud_cover', 100),
    )
    print('Cloud cover:', selected_item.properties.get('eo:cloud_cover'), '%')

    image = rioxarray.open_rasterio(selected_item.assets['visual'].href)
    image_cropped = image.rio.clip_box(
        minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs='EPSG:4326'
    )

    tif_path = os.path.join(MODEL_DIR, 'sentinel_tile.tif')
    mask_path = os.path.join(MODEL_DIR, 'mask.tif')
    geojson_path = os.path.join(MODEL_DIR, 'output.geojson')

    image_cropped.rio.to_raster(tif_path)
    sam.generate(tif_path, output=mask_path)
    sam.tiff_to_vector(mask_path, geojson_path)

    gdf = gpd.read_file(geojson_path).to_crs(epsg=utm_epsg)
    if gdf.empty:
        return {'type': 'FeatureCollection', 'features': []}

    gdf['area_sqm'] = gdf.geometry.area
    gdf = gdf[gdf['area_sqm'] > gdf['area_sqm'].quantile(0.25)].copy()
    gdf['geometry'] = gdf.geometry.simplify(tolerance=0.00002, preserve_topology=True)
    gdf['perimeter_m'] = gdf.geometry.length
    gdf['centroid'] = gdf.geometry.centroid
    gdf['ulpin'] = gdf['centroid'].apply(lambda pt: generate_ulpin(pt.y, pt.x))
    gdf = gdf.to_crs(epsg=4326)

    features = []
    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry.geom_type != 'Polygon':
            continue
        features.append({
            'type': 'Feature',
            'properties': {
                'ulpin': row['ulpin'],
                'area_sqm': float(row['area_sqm']),
                'perimeter_m': float(row['perimeter_m']),
                'land_use': 'Unclassified',
            },
            'geometry': json.loads(gpd.GeoSeries([geometry], crs='EPSG:4326').to_json())['features'][0]['geometry'],
        })

    return {'type': 'FeatureCollection', 'features': features}
```

## 4. Colab API

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title='BhuDrishti Colab SAM Engine')


class BBoxRequest(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.post('/process')
def process_endpoint(req: BBoxRequest):
    if req.min_lon >= req.max_lon or req.min_lat >= req.max_lat:
        return {'error': 'Invalid bbox ordering'}
    try:
        return process_area([
            req.min_lon, req.min_lat, req.max_lon, req.max_lat
        ])
    except Exception as exc:
        return {'error': str(exc)}
```

## 5. Start the server once

```python
import nest_asyncio
import threading
import uvicorn

nest_asyncio.apply()


def run_server():
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')

threading.Thread(target=run_server, daemon=True).start()
```

## 6. Verify Colab locally, then create the tunnel

```python
import requests
import time

# Retry mechanism for connecting to the server
retries = 5
wait_time = 2  # seconds

for i in range(retries):
    try:
        response = requests.get('http://127.0.0.1:8000/health', timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print('Server check:', response.status_code, response.json())
        break # Exit loop if successful
    except requests.exceptions.ConnectionError as e:
        if i < retries - 1:
            print(f"Connection refused. Retrying in {wait_time} seconds... (Attempt {i+1}/{retries})")
            time.sleep(wait_time)
        else:
            print(f"Failed to connect to the server after {retries} attempts.")
            raise e # Re-raise the last exception if all retries fail
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        raise e
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise e
```

```python
!wget -q -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x cloudflared
!./cloudflared --version
```

```python
import re
import subprocess
import time

try:
    tunnel.terminate()
except NameError:
    pass

tunnel = subprocess.Popen(
    ['./cloudflared', 'tunnel', '--url', 'http://127.0.0.1:8000'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

public_url = None
for _ in range(60):
    line = tunnel.stdout.readline()
    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
    if match:
        public_url = match.group(0)
        break

if public_url is None:
    raise RuntimeError('Cloudflare URL nahi mila; tunnel output check karein.')

print('COLAB_AI_ENDPOINT=', public_url)
print('Health URL:', public_url + '/health')
```

Put the printed `COLAB_AI_ENDPOINT` value into the laptop `.env`, then restart the laptop backend. The laptop backend must use the Colab public URL, never `localhost:8000`.
