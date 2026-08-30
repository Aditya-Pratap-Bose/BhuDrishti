# BhuDrishti Colab SAM server

Run these cells in order in one Google Colab notebook. The laptop backend calls the public URL printed by the final cell.

## 1. Install and mount Drive

```python
from google.colab import drive
drive.mount('/content/drive')

!pip install -q segment-geospatial pystac-client planetary-computer rioxarray geopandas leafmap fastapi uvicorn nest-asyncio requests pillow numpy
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
import base64
from io import BytesIO
import numpy as np
from PIL import Image

def generate_ulpin(centroid_lat, centroid_lon):
    coord_string = f'{centroid_lat:.6f}_{centroid_lon:.6f}'
    digest = hashlib.sha256(coord_string.encode()).hexdigest()[:20].upper()
    return f'COLAB-{digest}'

def generate_preview_png(image, max_dim=512):
    try:
        arr = image.values
        bands = arr[:3] if arr.shape[0] >= 3 else arr
        rgb = np.transpose(bands, (1, 2, 0))

        if rgb.dtype != np.uint8:
            rgb = rgb.astype("float32")
            rgb = rgb - rgb.min()
            max_val = rgb.max()
            if max_val > 0:
                rgb = (rgb / max_val) * 255
            rgb = rgb.astype("uint8")

        pil_img = Image.fromarray(rgb)
        pil_img.thumbnail((max_dim, max_dim))

        buffer = BytesIO()
        pil_img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print("Preview image generate nahi ho payi:", e)
        return None

def _calculate_zoom_for_bbox(bbox):
    import math
    min_lon, min_lat, max_lon, max_lat = bbox
    avg_lat = (min_lat + max_lat) / 2
    width_m = abs(max_lon - min_lon) * 111320 * math.cos(math.radians(avg_lat))
    height_m = abs(max_lat - min_lat) * 111320
    max_dim = max(width_m, height_m)
    
    if max_dim < 350:
        return 19  # ~0.3m/px
    elif max_dim < 900:
        return 18  # ~0.6m/px
    elif max_dim < 2500:
        return 17  # ~1.2m/px
    else:
        return 16  # ~2.4m/px

def _load_tile_image(bbox, source_type='esri'):
    try:
        from samgeo.common import tms_to_geotiff
    except ImportError:
        from samgeo import tms_to_geotiff
        
    zoom = _calculate_zoom_for_bbox(bbox)
    if source_type == 'esri':
        tile_source = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    elif source_type == 'osm':
        tile_source = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    else:
        tile_source = 'SATELLITE'
        
    out_tif = os.path.join(MODEL_DIR, f'temp_tile_{source_type}.tif')
    try:
        tms_to_geotiff(output=out_tif, bbox=bbox, zoom=zoom, source=tile_source, overwrite=True)
    except Exception as e:
        print(f"tms_to_geotiff with {tile_source} failed: {e}, falling back to SATELLITE")
        tms_to_geotiff(output=out_tif, bbox=bbox, zoom=zoom, source='SATELLITE', overwrite=True)
        
    image = rioxarray.open_rasterio(out_tif)
    if image.rio.crs is None:
        image = image.rio.write_crs('EPSG:4326')
    if image.rio.crs.to_epsg() != 4326:
        image = image.rio.reproject('EPSG:4326')
    return image

def _load_sentinel_image(bbox):
    search = catalog.search(
        collections=['sentinel-2-l2a'],
        bbox=bbox,
        datetime='2023-01-01/2026-08-26',
        query={'eo:cloud_cover': {'lt': 10}},
    )
    items = list(search.items())
    print(len(items), 'Sentinel images mile')
    if not items:
        raise ValueError('Is area/date range me koi Sentinel-2 image nahi mili')

    selected_item = min(items, key=lambda item: item.properties.get('eo:cloud_cover', 100))
    print('Cloud cover:', selected_item.properties.get('eo:cloud_cover'), '%')

    image = rioxarray.open_rasterio(selected_item.assets['visual'].href)
    cropped = image.rio.clip_box(minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs='EPSG:4326')
    return cropped.rio.reproject('EPSG:4326')


def _load_oam_image(bbox):
    import leafmap
    gdf = leafmap.oam_search(bbox=bbox, return_gdf=True)
    print(0 if gdf is None else len(gdf), 'OpenAerialMap images mile')
    if gdf is None or gdf.empty:
        raise ValueError(
            'Is bbox ke liye OpenAerialMap par koi imagery nahi hai '
            '(OAM crowd-sourced hai, coverage mostly disaster-response zones tak hai). '
            'Sentinel-2 ya Esri High-Res source try karein.'
        )
    if 'file_size' in gdf.columns:
        gdf = gdf.sort_values('file_size')
    asset_url = gdf.iloc[0]['uuid']
    print('OAM image select hui:', gdf.iloc[0].get('title', asset_url))

    image = rioxarray.open_rasterio(asset_url)
    cropped = image.rio.clip_box(minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3], crs='EPSG:4326')
    if cropped.rio.crs.to_epsg() != 4326:
        cropped = cropped.rio.reproject('EPSG:4326')
    return cropped


def process_area(bbox, source_type='esri', utm_epsg=32643):
    if source_type in ('esri', 'osm'):
        image_4326 = _load_tile_image(bbox, source_type=source_type)
    elif source_type == 'openaerialmap':
        image_4326 = _load_oam_image(bbox)
    else:
        image_4326 = _load_sentinel_image(bbox)

    preview_b64 = generate_preview_png(image_4326)
    preview_bounds = list(image_4326.rio.bounds())

    tif_path = os.path.join(MODEL_DIR, 'input_tile.tif')
    mask_path = os.path.join(MODEL_DIR, 'mask.tif')
    geojson_path = os.path.join(MODEL_DIR, 'output.geojson')

    image_4326.rio.to_raster(tif_path)
    sam.generate(tif_path, output=mask_path)
    sam.tiff_to_vector(mask_path, geojson_path)

    gdf = gpd.read_file(geojson_path).to_crs(epsg=utm_epsg)
    if gdf.empty:
        return {'type': 'FeatureCollection', 'features': [], 'preview_image_base64': preview_b64, 'preview_bounds': preview_bounds}

    gdf['area_sqm'] = gdf.geometry.area
    gdf = gdf[gdf['area_sqm'] > gdf['area_sqm'].quantile(0.25)].copy()
    gdf['geometry'] = gdf.geometry.simplify(tolerance=0.2, preserve_topology=True)
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

    return {
        'type': 'FeatureCollection',
        'features': features,
        'preview_image_base64': preview_b64,
        'preview_bounds': preview_bounds,
    }
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
    source_type: str = 'esri'  # 'esri' (High-Res), 'sentinel', 'openaerialmap', 'osm'


@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.post('/process')
def process_endpoint(req: BBoxRequest):
    if req.min_lon >= req.max_lon or req.min_lat >= req.max_lat:
        return {'error': 'Invalid bbox ordering'}
    try:
        return process_area(
            [req.min_lon, req.min_lat, req.max_lon, req.max_lat],
            source_type=req.source_type,
        )
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
