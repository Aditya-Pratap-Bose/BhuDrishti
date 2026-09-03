// =================================================================
// js/map.js — BhuDrishti WebGIS Cadastral Console Controller
// Multi-Source AI Detection (Esri High-Res, OSM, Sentinel, Drone),
// Client-Side Geotiff Parser, Real-time Telemetry, Local Workspace Cache,
// Interactive Parcel Deletion, PostGIS Persistence & Attribute Inspector.
// =================================================================

// GUARD: Token verification
if (typeof getAuthToken === 'function' && !getAuthToken()) {
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

const RAIPUR_SSIPMT_CENTER = [21.1345, 81.6685];
const RAIPUR_SSIPMT_BBOX = [81.6650, 21.1310, 81.6720, 21.1380];

let map;
let basemapLayers = {};
let currentBasemap = 'satellite';

let drawnItems;
let rectangleDrawer = null;
let editHandler = null;

let selectedBbox = null;
let currentSourceType = 'esri'; // Default to Sub-meter High-Res Esri Satellite
let selectedDroneFile = null;
let v2OriAsset = null;
let v2DtmAsset = null;
let v2OriTileLayer = null;

let resultLayer = null;        // Vectorized AI parcel polygons
let savedParcelsLayer = null;  // PostgreSQL/PostGIS registered parcels
let rawImageryOverlay = null;  // Satellite/Drone raw preview ImageOverlay
let activeHighlightLayer = null;

let currentFeatureSet = [];    // Active features in local workspace (cached)
let currentDrawerFeature = null;

let activeTool = 'pointer'; // 'pointer' | 'draw' | 'edit'
let isDrawing = false;
let isEditing = false;
let drawAnchorLatLng = null;
let isProcessing = false;

const PUBLIC_IMAGERY_SOURCES = new Set(['esri', 'sentinel', 'openaerialmap', 'osm']);
const SUPPORTED_SOURCE_TYPES = new Set([...PUBLIC_IMAGERY_SOURCES, 'drone']);

function getSelectedApiVersion() {
  return typeof getApiVersion === 'function' ? getApiVersion() : 'v1';
}

function updateApiCapabilityStatus(message) {
  const status = document.getElementById('apiCapabilityStatus');
  if (!status) return;
  const version = getSelectedApiVersion();
  status.textContent = message || (version === 'v2'
    ? 'V2 Preview ready · public imagery bbox processing (no drone file required)'
    : 'V1 Stable · existing imagery and drone workflow');
  status.className = `text-[10px] leading-relaxed ${
    version === 'v2' ? 'text-cyan-800' : 'text-faint'
  }`;
}

function setProcessingApiVersion(version) {
  try {
    setApiVersion(version);
    updateApiCapabilityStatus();
    setSourceType(currentSourceType);
    showToast(`${version.toUpperCase()} processing selected. Saved parcels still use the stable v1 database API.`, 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function handleLogout() {
  if (typeof clearSession === 'function') clearSession();
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

// -----------------------------------------------------------------
// 1. INITIALIZATION & BASEMAPS
// -----------------------------------------------------------------

async function initDashboard() {
  parseWorkspaceUrlParams();
  const versionSelect = document.getElementById('apiVersionSelect');
  if (versionSelect) versionSelect.value = getApiVersion();
  updateApiCapabilityStatus();
  initMap();
  setupDropzone();
  await loadUserProfile();
  await loadSavedParcels();
}

function parseWorkspaceUrlParams() {
  try {
    const params = new URLSearchParams(window.location.search);
    const sessionName = params.get('session');
    const sourceParam = params.get('source');
    const aoiParam = params.get('aoi');
    
    if (sessionName || aoiParam === 'raipur_ssipmt') {
      const titleEl = document.getElementById('sessionTitle');
      if (titleEl) titleEl.textContent = sessionName || 'Raipur SSIPMT Urban Cadastre';
    }
    
    if (sourceParam && SUPPORTED_SOURCE_TYPES.has(sourceParam)) {
      currentSourceType = sourceParam;
      const radio = Array.from(document.querySelectorAll('input[name="sourceType"]'))
        .find((input) => input.value === sourceParam);
      if (radio) {
        radio.checked = true;
        setSourceType(sourceParam);
      }
    }
  } catch (_) {}
}

function initMap() {
  map = L.map('map', {
    zoomControl: false,
    minZoom: 3,
    maxZoom: 21,
  }).setView(RAIPUR_SSIPMT_CENTER, 17);

  // Basemap Providers
  basemapLayers['satellite'] = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Maxar, Earthstar Geographics',
    maxZoom: 20,
  });

  basemapLayers['osm'] = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  });

  // Blank Canvas layer for pure drone imagery
  basemapLayers['blank'] = L.layerGroup();

  basemapLayers['satellite'].addTo(map);

  // Zoom control positioned on bottom-left cleanly
  L.control.zoom({ position: 'bottomleft' }).addTo(map);

  // Raipur SSIPMT Reference Boundary
  L.rectangle([[RAIPUR_SSIPMT_BBOX[1], RAIPUR_SSIPMT_BBOX[0]], [RAIPUR_SSIPMT_BBOX[3], RAIPUR_SSIPMT_BBOX[2]]], {
    color: '#10B981', weight: 1.5, dashArray: '4 4', fill: false, interactive: false,
  }).addTo(map).bindTooltip('Raipur SSIPMT Benchmark Zone', { permanent: false, direction: 'top' });

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  // Initialize Leaflet Draw Rectangle Drawer
  rectangleDrawer = new L.Draw.Rectangle(map, {
    shapeOptions: {
      color: '#10B981',
      weight: 2,
      fillOpacity: 0.15,
      dashArray: '3 3',
    },
  });

  // ---------------------------------------------------------------
  // DRAW EVENT HOOKS & LIVE MEASUREMENT
  // ---------------------------------------------------------------

  map.on(L.Draw.Event.DRAWSTART, () => {
    isDrawing = true;
    drawAnchorLatLng = null;
    updateToolUI('draw');
  });

  map.on(L.Draw.Event.DRAWSTOP, () => {
    isDrawing = false;
    drawAnchorLatLng = null;
    if (activeTool === 'draw') {
      activatePointerTool();
    }
  });

  map.on('mousedown', (e) => {
    if (isDrawing && !drawAnchorLatLng) {
      drawAnchorLatLng = e.latlng;
    }
  });

  map.on('mousemove', (e) => {
    if (isDrawing && drawAnchorLatLng) {
      const min_lon = Math.min(drawAnchorLatLng.lng, e.latlng.lng);
      const max_lon = Math.max(drawAnchorLatLng.lng, e.latlng.lng);
      const min_lat = Math.min(drawAnchorLatLng.lat, e.latlng.lat);
      const max_lat = Math.max(drawAnchorLatLng.lat, e.latlng.lat);
      updateTelemetryHUD(min_lon, min_lat, max_lon, max_lat);
    } else if (isEditing && drawnItems.getLayers().length > 0) {
      updateFromDrawnLayer();
    }
  });

  map.on(L.Draw.Event.CREATED, (e) => {
    drawnItems.clearLayers();
    const layer = e.layer;
    drawnItems.addLayer(layer);
    layer.on('edit', updateFromDrawnLayer);

    updateFromDrawnLayer();
    setDetectEnabled(true);
    isDrawing = false;
    drawAnchorLatLng = null;
    activatePointerTool();
  });

  map.on('draw:editvertex', updateFromDrawnLayer);
  map.on('draw:editmove', updateFromDrawnLayer);
  map.on('draw:editresize', updateFromDrawnLayer);

  setTimeout(() => { map.invalidateSize(); }, 300);
}

function switchBasemap(type) {
  if (basemapLayers[currentBasemap]) {
    map.removeLayer(basemapLayers[currentBasemap]);
  }
  if (type === 'blank') {
    currentBasemap = 'blank';
    return;
  }
  if (basemapLayers[type]) {
    basemapLayers[type].addTo(map);
    currentBasemap = type;
  }
}

// -----------------------------------------------------------------
// 2. CADASTRE TOOLBAR: POINTER, DRAW, EDIT, CLEAR
// -----------------------------------------------------------------

function updateToolUI(tool) {
  activeTool = tool;
  const pointerBtn = document.getElementById('toolPointerBtn');
  const drawBtn = document.getElementById('toolDrawBtn');
  const editBtn = document.getElementById('toolEditBtn');
  const badge = document.getElementById('activeToolBadge');

  // Reset tool button styling
  [pointerBtn, drawBtn, editBtn].forEach(btn => {
    if (btn) {
      btn.className = 'flex items-center justify-center gap-1.5 py-2 px-2.5 bg-surface2 hover:bg-line2 border border-line rounded-xl text-ink transition group';
    }
  });

  if (tool === 'pointer' && pointerBtn) {
    pointerBtn.className = 'flex items-center justify-center gap-1.5 py-2 px-2.5 bg-scan/20 text-scan border border-scan/40 rounded-xl transition group font-medium';
    if (badge) { badge.textContent = 'POINTER'; badge.className = 'text-[9px] text-scan font-mono'; }
    document.getElementById('map').style.cursor = 'grab';
  } else if (tool === 'draw' && drawBtn) {
    drawBtn.className = 'flex items-center justify-center gap-1.5 py-2 px-2.5 bg-scan/20 text-scan border border-scan/40 rounded-xl transition group font-medium';
    if (badge) { badge.textContent = 'DRAWING'; badge.className = 'text-[9px] text-scan font-mono'; }
    document.getElementById('map').style.cursor = 'crosshair';
  } else if (tool === 'edit' && editBtn) {
    editBtn.className = 'flex items-center justify-center gap-1.5 py-2 px-2.5 bg-amber/20 text-amber border border-amber/40 rounded-xl transition group font-medium';
    if (badge) { badge.textContent = 'EDITING'; badge.className = 'text-[9px] text-amber font-mono'; }
  }
}

function activatePointerTool() {
  if (isDrawing && rectangleDrawer) {
    rectangleDrawer.disable();
    isDrawing = false;
  }
  if (isEditing && editHandler) {
    editHandler.save();
    editHandler.disable();
    isEditing = false;
  }
  updateToolUI('pointer');
}

function triggerDrawRectangle() {
  if (isEditing && editHandler) {
    editHandler.save();
    editHandler.disable();
    isEditing = false;
  }
  if (isDrawing) {
    activatePointerTool();
    return;
  }
  updateToolUI('draw');
  rectangleDrawer.enable();
}

function triggerEditRectangle() {
  const layers = drawnItems.getLayers();
  if (layers.length === 0) {
    showToast('Pehle map par rectangle draw karein.', 'info');
    return;
  }

  if (!isEditing) {
    if (isDrawing && rectangleDrawer) {
      rectangleDrawer.disable();
      isDrawing = false;
    }
    if (!editHandler) {
      editHandler = new L.EditToolbar.Edit(map, {
        featureGroup: drawnItems,
        selectedPathOptions: { color: '#F59E0B', weight: 2.5 },
      });
    }
    editHandler.enable();
    isEditing = true;
    updateToolUI('edit');
    showToast('Edit Mode Active: Handles ko drag karke resize karein.', 'info');
  } else {
    if (editHandler) {
      editHandler.save();
      editHandler.disable();
    }
    isEditing = false;
    activatePointerTool();
    updateFromDrawnLayer();
  }
}

function clearCurrentSelection() {
  if (isEditing && editHandler) {
    editHandler.disable();
    isEditing = false;
  }
  if (isDrawing && rectangleDrawer) {
    rectangleDrawer.disable();
    isDrawing = false;
  }
  drawnItems.clearLayers();
  selectedBbox = null;
  resetTelemetryHUD();
  setDetectEnabled(false);
  activatePointerTool();
}

function resetToTestArea() {
  map.flyTo(RAIPUR_SSIPMT_CENTER, 17, { duration: 1.2 });
}

function updateFromDrawnLayer() {
  const layers = drawnItems.getLayers();
  if (layers.length === 0) return;
  const layer = layers[0];
  if (layer && typeof layer.getBounds === 'function') {
    const b = layer.getBounds();
    selectedBbox = {
      min_lon: b.getWest(),
      min_lat: b.getSouth(),
      max_lon: b.getEast(),
      max_lat: b.getNorth(),
    };
    updateTelemetryHUD(selectedBbox.min_lon, selectedBbox.min_lat, selectedBbox.max_lon, selectedBbox.max_lat);
    setDetectEnabled(true);
  }
}

// -----------------------------------------------------------------
// 3. TELEMETRY STATUS BAR
// -----------------------------------------------------------------

function updateTelemetryHUD(min_lon, min_lat, max_lon, max_lat) {
  const bar = document.getElementById('telemetryBar');
  const coordsEl = document.getElementById('hudCoords');
  const dimsEl = document.getElementById('hudDims');
  const areaEl = document.getElementById('hudArea');

  if (bar) bar.classList.remove('hidden');

  if (coordsEl) {
    coordsEl.innerHTML = `W ${min_lon.toFixed(5)} S ${min_lat.toFixed(5)} &bull; E ${max_lon.toFixed(5)} N ${max_lat.toFixed(5)}`;
  }

  const latDiff = Math.abs(max_lat - min_lat);
  const lonDiff = Math.abs(max_lon - min_lon);
  const avgLatRad = ((min_lat + max_lat) / 2) * (Math.PI / 180);
  const heightM = latDiff * 111320;
  const widthM = lonDiff * 111320 * Math.cos(avgLatRad);
  const areaSqm = widthM * heightM;
  const areaHa = areaSqm / 10000;

  if (dimsEl) {
    dimsEl.innerHTML = `${widthM.toFixed(1)}m &times; ${heightM.toFixed(1)}m`;
  }
  if (areaEl) {
    areaEl.innerHTML = `${areaHa.toFixed(2)} Ha <span class="text-faint font-normal">(${areaSqm.toFixed(0)} m²)</span>`;
  }
}

function resetTelemetryHUD() {
  const bar = document.getElementById('telemetryBar');
  if (bar) bar.classList.add('hidden');
  const coordsEl = document.getElementById('hudCoords');
  const dimsEl = document.getElementById('hudDims');
  const areaEl = document.getElementById('hudArea');
  if (coordsEl) coordsEl.textContent = 'Draw a rectangle on the map';
  if (dimsEl) dimsEl.textContent = '0m \u00D7 0m';
  if (areaEl) areaEl.textContent = '0.00 Ha';
}

// -----------------------------------------------------------------
// 4. CLIENT-SIDE GEOTIFF PARSER (geotiff.js + proj4)
// -----------------------------------------------------------------

function setupDropzone() {
  const dropzone = document.getElementById('geotiffDropzone');
  if (!dropzone) return;

  dropzone.addEventListener('click', () => {
    document.getElementById('droneFileInput').click();
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-active');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) {
      processGeoTiffClientSide(files[0]);
    }
  });
}

function handleGeoTiffFileSelected(event) {
  const file = event.target.files[0];
  if (file) {
    processGeoTiffClientSide(file);
  }
}

async function processGeoTiffClientSide(file) {
  selectedDroneFile = file;
  const metaCard = document.getElementById('geotiffMetaCard');
  const sizeEl = document.getElementById('geoMetaSize');
  const dimsEl = document.getElementById('geoMetaDims');
  const crsEl = document.getElementById('geoMetaCrs');
  const areaEl = document.getElementById('geoMetaArea');

  const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
  if (sizeEl) sizeEl.textContent = `${fileSizeMB} MB`;
  if (metaCard) metaCard.classList.remove('hidden');

  try {
    showToast('geotiff.js: Reading raster metadata in browser...', 'info');
    
    const tiff = await GeoTIFF.fromBlob(file);
    const image = await tiff.getImage();
    
    const width = image.getWidth();
    const height = image.getHeight();
    const samples = image.getSamplesPerPixel();
    if (dimsEl) dimsEl.textContent = `${width} \u00D7 ${height} px (${samples} bands)`;

    const bbox = image.getBoundingBox();
    const geoKeys = image.getGeoKeys() || {};
    let epsgCode = geoKeys.ProjectedCSTypeGeoKey || geoKeys.GeographicTypeGeoKey || 32643;
    if (crsEl) crsEl.textContent = `EPSG:${epsgCode}`;

    let minLon, minLat, maxLon, maxLat;

    if (epsgCode !== 4326 && typeof proj4 !== 'undefined') {
      try {
        proj4.defs('EPSG:32643', '+proj=utm +zone=43 +datum=WGS84 +units=m +no_defs');
        proj4.defs('EPSG:32644', '+proj=utm +zone=44 +datum=WGS84 +units=m +no_defs');

        const [minX, minY, maxX, maxY] = bbox;
        const sw = proj4(`EPSG:${epsgCode}`, 'EPSG:4326', [minX, minY]);
        const ne = proj4(`EPSG:${epsgCode}`, 'EPSG:4326', [maxX, maxY]);

        minLon = Math.min(sw[0], ne[0]);
        maxLon = Math.max(sw[0], ne[0]);
        minLat = Math.min(sw[1], ne[1]);
        maxLat = Math.max(sw[1], ne[1]);
      } catch (projErr) {
        minLon = bbox[0]; minLat = bbox[1]; maxLon = bbox[2]; maxLat = bbox[3];
      }
    } else {
      minLon = bbox[0]; minLat = bbox[1]; maxLon = bbox[2]; maxLat = bbox[3];
    }

    const latDiff = Math.abs(maxLat - minLat);
    const lonDiff = Math.abs(maxLon - minLon);
    const avgLatRad = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const groundAreaSqm = (latDiff * 111320) * (lonDiff * 111320 * Math.cos(avgLatRad));
    const groundAreaHa = (groundAreaSqm / 10000).toFixed(2);
    if (areaEl) areaEl.textContent = `${groundAreaHa} Ha (${(groundAreaSqm / 1000).toFixed(1)}k m\u00B2)`;

    drawnItems.clearLayers();
    const geoTiffBounds = [[minLat, minLon], [maxLat, maxLon]];
    const rectLayer = L.rectangle(geoTiffBounds, {
      color: '#06B6D4',
      weight: 2,
      dashArray: '4 4',
      fillOpacity: 0.15,
    });
    drawnItems.addLayer(rectLayer);
    map.flyToBounds(geoTiffBounds, { padding: [50, 50], duration: 1.5 });

    selectedBbox = { min_lon: minLon, min_lat: minLat, max_lon: maxLon, max_lat: maxLat };
    updateTelemetryHUD(minLon, minLat, maxLon, maxLat);

    showToast(`GeoTIFF parsed (${width}x${height}px). Ready for SAM AI extraction!`, 'success');
  } catch (err) {
    console.warn('geotiff.js note:', err);
    if (dimsEl) dimsEl.textContent = 'Standard GeoTIFF';
    showToast('GeoTIFF file selected. Click "Run SAM on Drone Ortho".', 'info');
  }
}

// -----------------------------------------------------------------
// 5. DATA SOURCE SELECTION
// -----------------------------------------------------------------

function setSourceType(source) {
  if (!SUPPORTED_SOURCE_TYPES.has(source)) {
    showToast('Unsupported imagery source selected.', 'error');
    return;
  }
  currentSourceType = source;
  const droneBox = document.getElementById('droneUploadBox');
  const detectBtn = document.getElementById('detectBtn');
  const v2Box = document.getElementById('v2RasterUploadBox');

  if (source === 'drone') {
    if (droneBox) droneBox.classList.remove('hidden');
    if (v2Box) v2Box.classList.toggle('hidden', getSelectedApiVersion() !== 'v2');
    if (detectBtn) detectBtn.classList.add('hidden');
    updateApiCapabilityStatus(getSelectedApiVersion() === 'v2'
      ? 'V2 raster preparation is optional; public bbox processing does not require drone files'
      : 'V1 Stable · upload a GeoTIFF to run the drone workflow');
  } else {
    if (droneBox) droneBox.classList.add('hidden');
    if (v2Box) v2Box.classList.add('hidden');
    if (detectBtn) detectBtn.classList.remove('hidden');
    setDetectEnabled(Boolean(selectedBbox));
    updateApiCapabilityStatus();
  }

}

async function uploadV2RasterPair() {
  const ori = document.getElementById('v2OriFileInput')?.files[0];
  const dtm = document.getElementById('v2DtmFileInput')?.files[0];
  const status = document.getElementById('v2RasterStatus');
  if (!ori || !dtm) {
    showToast('V2 ke liye ORI aur DTM dono GeoTIFF select karein.', 'error');
    return;
  }
  const button = document.getElementById('v2UploadBtn');
  const form = new FormData();
  form.append('ori_file', ori);
  form.append('dtm_file', dtm);
  if (button) { button.disabled = true; button.textContent = 'Validating and preparing COGs...'; }
  try {
    const result = await apiFetch('/raster/upload', { method: 'POST', body: form }, 'v2');
    v2OriAsset = result.ori;
    v2DtmAsset = result.dtm;
    if (status) {
      status.textContent = `Ready: ${result.co_registration.crs} • ORI/DTM overlap verified`;
      status.classList.remove('hidden');
    }
    addV2OriTiles(v2OriAsset.asset_id);
    showToast('V2 COG layers ready. ORI tiles added to the map.', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (button) { button.disabled = false; button.textContent = 'Prepare V2 COG Layers'; }
  }
}

function addV2OriTiles(assetId) {
  if (v2OriTileLayer) map.removeLayer(v2OriTileLayer);
  const token = getAuthToken();
  v2OriTileLayer = L.tileLayer('', { attribution: 'BhuDrishti V2 COG', maxZoom: 22 });
  v2OriTileLayer.createTile = function(coords, done) {
    const tile = document.createElement('img');
    tile.alt = '';
    tile.setAttribute('role', 'presentation');
    const url = `${window.location.origin}/api/v2/tiles/${encodeURIComponent(assetId)}/${coords.z}/${coords.x}/${coords.y}.png`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((response) => {
        if (!response.ok) throw new Error(`V2 tile request failed (${response.status})`);
        return response.blob();
      })
      .then((blob) => {
        tile.src = URL.createObjectURL(blob);
        tile.onload = () => { URL.revokeObjectURL(tile.src); done(null, tile); };
      })
      .catch((error) => done(error, tile));
    return tile;
  };
  v2OriTileLayer.addTo(map);
}

function setDetectEnabled(on) {
  const btn = document.getElementById('detectBtn');
  if (!btn) return;
  btn.disabled = !on;
  const label = document.getElementById('detectBtnLabel');
  if (label) {
    label.textContent = on ? 'Extract Parcels (SAM AI)' : 'Draw a boundary box first';
  }
}

function toggleLayer(layerName, isChecked) {
  if (layerName === 'raw') {
    if (rawImageryOverlay) {
      if (isChecked) map.addLayer(rawImageryOverlay);
      else map.removeLayer(rawImageryOverlay);
    }
  } else if (layerName === 'parcels') {
    if (resultLayer) {
      if (isChecked) map.addLayer(resultLayer);
      else map.removeLayer(resultLayer);
    }
    if (savedParcelsLayer) {
      if (isChecked) map.addLayer(savedParcelsLayer);
      else map.removeLayer(savedParcelsLayer);
    }
  }
}

// -----------------------------------------------------------------
// 6. AI SEGMENTATION PIPELINE (SAM AI)
// -----------------------------------------------------------------

async function detectParcels() {
  if (!selectedBbox) {
    showToast('Pehle map par rectangle boundary draw karein.', 'error');
    return;
  }
  const overlay = document.getElementById('loadingOverlay');
  const statusText = document.getElementById('loadingStatusText');
  if (overlay) overlay.classList.remove('hidden');
  if (statusText) statusText.textContent = `Running SAM AI on ${currentSourceType.toUpperCase()} imagery...`;
  setDetectEnabled(false);

  try {
    const payload = {
      min_lon: selectedBbox.min_lon,
      min_lat: selectedBbox.min_lat,
      max_lon: selectedBbox.max_lon,
      max_lat: selectedBbox.max_lat,
      source_type: currentSourceType,
    };

    const apiVersion = getApiVersion();
    const data = await apiFetch('/satellite/process-bbox', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, apiVersion);

    handleInferenceResponse(data);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (overlay) overlay.classList.add('hidden');
    setDetectEnabled(true);
  }
}

async function detectFromDrone() {
  const fileInput = document.getElementById('droneFileInput');
  const file = selectedDroneFile || (fileInput && fileInput.files[0]);
  if (!file) {
    showToast('Pehle koi .tif GeoTIFF file drop ya select karein.', 'error');
    return;
  }

  const overlay = document.getElementById('loadingOverlay');
  const statusText = document.getElementById('loadingStatusText');
  if (overlay) overlay.classList.remove('hidden');
  if (statusText) statusText.textContent = `Running SAM AI on high-res Drone GeoTIFF (${getApiVersion().toUpperCase()})...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const data = await apiFetch('/satellite/process-drone', {
      method: 'POST',
      body: formData,
    });
    handleInferenceResponse(data);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (overlay) overlay.classList.add('hidden');
  }
}

function handleInferenceResponse(data) {
  const features = data.features || [];
  currentFeatureSet = features;

  if (data.preview_image_base64 && data.preview_bounds) {
    const [minx, miny, maxx, maxy] = data.preview_bounds;
    const imageBounds = [[miny, minx], [maxy, maxx]];
    if (rawImageryOverlay) {
      map.removeLayer(rawImageryOverlay);
    }
    rawImageryOverlay = L.imageOverlay(`data:image/png;base64,${data.preview_image_base64}`, imageBounds, {
      opacity: 0.9,
    });
    const layerRawCheck = document.getElementById('layerRaw');
    if (!layerRawCheck || layerRawCheck.checked) {
      rawImageryOverlay.addTo(map);
    }
  }

  renderResults(features, { saved: false });
  showToast(`Success: Extracted ${features.length} parcels into workspace.`, 'success');
}

// -----------------------------------------------------------------
// 7. RESULTS RENDERING, STATS & INDIVIDUAL PARCEL REMOVAL
// -----------------------------------------------------------------

function formatDisplayUlpin(rawUlpin) {
  if (!rawUlpin) return '22-10-001-0000000';
  const clean = String(rawUlpin).replace(/[^A-Z0-9]/gi, '').toUpperCase();
  if (clean.length === 14) {
    return `${clean.substring(0, 2)}-${clean.substring(2, 4)}-${clean.substring(4, 7)}-${clean.substring(7, 14)}`;
  }
  if (rawUlpin.includes('-')) return rawUlpin.toUpperCase();
  return clean.substring(0, 14).toUpperCase();
}

function removeParcel(index, event) {
  if (event) {
    event.stopPropagation();
  }
  if (index < 0 || index >= currentFeatureSet.length) return;

  const removed = currentFeatureSet.splice(index, 1)[0];
  if (currentDrawerFeature && currentDrawerFeature === removed) {
    closeDrawer();
  }

  renderResults(currentFeatureSet, { saved: false });
  showToast('Parcel removed from workspace.', 'info');
}

function renderResults(features, { saved }) {
  currentFeatureSet = features || [];
  const list = document.getElementById('resultsList');
  const header = document.getElementById('resultsHeader');
  const empty = document.getElementById('emptyState');
  const countEl = document.getElementById('resultCount');
  const saveAllBtn = document.getElementById('saveAllBtn');

  const statTotalArea = document.getElementById('statTotalArea');
  const statAvgArea = document.getElementById('statAvgArea');
  const statSavedCount = document.getElementById('statSavedCount');
  const headerCount = document.getElementById('headerParcelCount');

  if (resultLayer) {
    map.removeLayer(resultLayer);
    resultLayer = null;
  }
  if (list) list.innerHTML = '';

  if (!currentFeatureSet || !currentFeatureSet.length) {
    if (header) header.classList.add('hidden');
    if (empty) empty.classList.remove('hidden');
    if (countEl) countEl.textContent = '0';
    if (headerCount) headerCount.textContent = '0';
    return;
  }

  if (empty) empty.classList.add('hidden');
  if (header) header.classList.remove('hidden');
  if (countEl) countEl.textContent = currentFeatureSet.length;
  if (headerCount) headerCount.textContent = currentFeatureSet.length;
  if (saveAllBtn) saveAllBtn.classList.toggle('hidden', saved);

  // Calculate Aggregated Metrics
  let totalAreaSqm = 0;
  let savedCount = 0;
  currentFeatureSet.forEach(f => {
    const a = f.properties && f.properties.area_sqm ? Number(f.properties.area_sqm) : 0;
    totalAreaSqm += a;
    if (f.properties && f.properties.id) savedCount++;
  });
  const totalAreaHa = (totalAreaSqm / 10000).toFixed(2);
  const avgAreaSqm = (totalAreaSqm / currentFeatureSet.length).toFixed(0);

  if (statTotalArea) statTotalArea.textContent = `${totalAreaHa} Ha`;
  if (statAvgArea) statAvgArea.textContent = `${avgAreaSqm} m²`;
  if (statSavedCount) statSavedCount.textContent = saved ? `${savedCount} in DB` : 'Cached';

  // Interactive GeoJSON Layer on Map
  resultLayer = L.geoJSON({ type: 'FeatureCollection', features: currentFeatureSet }, {
    style: (feature) => ({
      color: saved ? '#3B82F6' : '#10B981',
      weight: 2,
      fillOpacity: 0.22,
      className: 'parcel-glow',
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const displayId = formatDisplayUlpin(p.ulpin);
      layer.bindTooltip(`<b>${displayId}</b><br/>${p.land_use || 'Unclassified'}<br/>${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0} m²`, {
        sticky: true,
      });

      layer.on('click', () => {
        openDrawer(feature);
      });
    },
  });

  const layerParcelsCheck = document.getElementById('layerParcels');
  if (!layerParcelsCheck || layerParcelsCheck.checked) {
    resultLayer.addTo(map);
  }

  try {
    map.fitBounds(resultLayer.getBounds(), { padding: [40, 40] });
  } catch (_) {}

  // Populate Interactive Parcel Cards List
  currentFeatureSet.forEach((feature, idx) => {
    const p = feature.properties || {};
    const displayUlpin = formatDisplayUlpin(p.ulpin);
    const card = document.createElement('div');
    card.className = 'fade-in border border-line rounded-xl p-3 bg-surface2/70 hover:bg-surface3 hover:border-scan/50 transition cursor-pointer group shadow-sm relative';
    card.innerHTML = `
      <div class="flex items-center justify-between mb-1.5">
        <div class="flex items-center gap-1.5">
          <span class="font-mono text-xs text-scan font-semibold group-hover:text-emerald-300 transition truncate max-w-[150px]" title="${p.ulpin}">${displayUlpin}</span>
          <span class="text-[9px] font-mono px-2 py-0.5 rounded-full bg-surface border border-line text-faint">${p.land_use || 'Unclassified'}</span>
        </div>
        <button onclick="removeParcel(${idx}, event)" title="Remove parcel from workspace" class="text-faint hover:text-red-400 p-1 rounded-lg hover:bg-red-950/30 transition">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="flex items-center justify-between text-[11px] text-faint font-mono">
        <span>Area: <b class="text-ink">${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0}</b> m²</span>
        <span>Perimeter: <b class="text-ink">${p.perimeter_m ? Number(p.perimeter_m).toFixed(1) : 0}</b> m</span>
      </div>
      ${p.owner_name ? `<div class="text-[10px] text-emerald-400 font-medium mt-1 truncate">Owner: ${p.owner_name}</div>` : ''}
    `;

    card.addEventListener('click', () => {
      openDrawer(feature);
      try {
        const tempLayer = L.geoJSON(feature);
        map.fitBounds(tempLayer.getBounds(), { padding: [80, 80] });
      } catch (_) {}
    });

    list.appendChild(card);
  });
}

// -----------------------------------------------------------------
// 8. ATTRIBUTE INSPECTOR, CLIENT-SIDE BOUNDARY RESHAPING & POSTGIS CRUD
// -----------------------------------------------------------------

let isEditingParcelBoundary = false;
let boundaryEditMarkers = [];

function calculatePolygonGeodesicMetrics(coords) {
  if (!coords || coords.length < 3) return { areaSqm: 0, perimeterM: 0 };
  
  let perimeterM = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    const p1 = coords[i];
    const p2 = coords[i+1];
    const latMid = ((p1[1] + p2[1]) / 2) * (Math.PI / 180);
    const dLat = (p2[1] - p1[1]) * 111320;
    const dLon = (p2[0] - p1[0]) * 111320 * Math.cos(latMid);
    perimeterM += Math.sqrt(dLat * dLat + dLon * dLon);
  }

  // Scaled planar area
  let area = 0;
  const n = coords.length;
  const avgLatRad = (coords.reduce((sum, c) => sum + c[1], 0) / n) * (Math.PI / 180);
  const mPerDegLat = 111320;
  const mPerDegLon = 111320 * Math.cos(avgLatRad);

  for (let i = 0; i < n - 1; i++) {
    const x1 = coords[i][0] * mPerDegLon;
    const y1 = coords[i][1] * mPerDegLat;
    const x2 = coords[i+1][0] * mPerDegLon;
    const y2 = coords[i+1][1] * mPerDegLat;
    area += (x1 * y2) - (x2 * y1);
  }
  const areaSqm = Math.abs(area) / 2;
  return { areaSqm, perimeterM };
}

function openDrawer(feature) {
  if (isEditingParcelBoundary) {
    toggleParcelBoundaryEdit();
  }

  currentDrawerFeature = feature;
  const p = feature.properties || {};

  const ulpinEl = document.getElementById('drawerUlpin');
  const areaEl = document.getElementById('drawerArea');
  const perimEl = document.getElementById('drawerPerimeter');
  const landUseEl = document.getElementById('drawerLandUse');
  const ownerEl = document.getElementById('drawerOwner');

  if (ulpinEl) {
    ulpinEl.textContent = p.ulpin || 'N/A';
    ulpinEl.title = p.ulpin || '';
  }
  if (areaEl) areaEl.textContent = `${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0} m² (${((p.area_sqm || 0) / 10000).toFixed(3)} Ha)`;
  if (perimEl) perimEl.textContent = `${p.perimeter_m ? Number(p.perimeter_m).toFixed(1) : 0} m`;
  if (landUseEl) landUseEl.value = p.land_use || 'Unclassified';
  if (ownerEl) ownerEl.value = p.owner_name || '';

  if (activeHighlightLayer) {
    map.removeLayer(activeHighlightLayer);
  }
  activeHighlightLayer = L.geoJSON(feature, {
    style: {
      color: '#F59E0B',
      weight: 3.5,
      fillOpacity: 0.35,
    }
  }).addTo(map);

  const drawer = document.getElementById('parcelDrawer');
  if (drawer) drawer.classList.remove('hidden');
}

function closeDrawer() {
  if (isEditingParcelBoundary) {
    toggleParcelBoundaryEdit();
  }
  const drawer = document.getElementById('parcelDrawer');
  if (drawer) drawer.classList.add('hidden');
  if (activeHighlightLayer) {
    map.removeLayer(activeHighlightLayer);
    activeHighlightLayer = null;
  }
  currentDrawerFeature = null;
}

function toggleParcelBoundaryEdit() {
  if (!currentDrawerFeature) return;
  isEditingParcelBoundary = !isEditingParcelBoundary;

  const btn = document.getElementById('toggleEditBoundaryBtn');
  const btnText = document.getElementById('editBoundaryBtnText');
  const badge = document.getElementById('drawerEditBadge');

  if (isEditingParcelBoundary) {
    if (btn) btn.className = 'bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/60 text-amber-300 font-bold px-3 py-2 rounded-xl transition flex items-center gap-1.5 shadow-[0_0_15px_rgba(245,158,11,0.3)]';
    if (btnText) btnText.textContent = 'Finish Reshaping';
    if (badge) badge.classList.remove('hidden');
    enableParcelVertexHandles();
    showToast('Boundary Reshaper: Drag the corner points on the map to resize/reshape.', 'info');
  } else {
    if (btn) btn.className = 'bg-surface2/80 hover:bg-surface3 border border-line hover:border-amber/50 text-amber font-medium px-3 py-2 rounded-xl transition flex items-center gap-1.5 shadow-sm';
    if (btnText) btnText.textContent = 'Reshape Boundary';
    if (badge) badge.classList.add('hidden');
    disableParcelVertexHandles();
    renderResults(currentFeatureSet, { saved: false });
    showToast('Boundary updated in workspace.', 'success');
  }
}

function enableParcelVertexHandles() {
  disableParcelVertexHandles();
  if (!currentDrawerFeature || !currentDrawerFeature.geometry) return;
  const geomType = currentDrawerFeature.geometry.type;
  let ring = geomType === 'Polygon' 
    ? currentDrawerFeature.geometry.coordinates[0] 
    : (geomType === 'MultiPolygon' ? currentDrawerFeature.geometry.coordinates[0][0] : null);
  
  if (!ring || ring.length < 3) return;

  ring.forEach((coord, idx) => {
    if (idx === ring.length - 1 && ring.length > 3 && coord[0] === ring[0][0] && coord[1] === ring[0][1]) {
      return;
    }

    const latlng = [coord[1], coord[0]];
    const marker = L.marker(latlng, {
      draggable: true,
      icon: L.divIcon({
        className: 'leaflet-editing-icon',
        iconSize: [12, 12],
      }),
      title: `Corner ${idx + 1} — Drag to reshape`,
    }).addTo(map);

    marker.on('drag', (e) => {
      const newPos = e.target.getLatLng();
      ring[idx] = [newPos.lng, newPos.lat];
      if (idx === 0) {
        ring[ring.length - 1] = [newPos.lng, newPos.lat];
      }

      if (activeHighlightLayer) {
        map.removeLayer(activeHighlightLayer);
      }
      activeHighlightLayer = L.geoJSON(currentDrawerFeature, {
        style: {
          color: '#F59E0B',
          weight: 3.5,
          fillOpacity: 0.35,
          className: 'parcel-editing-glow'
        }
      }).addTo(map);

      const metrics = calculatePolygonGeodesicMetrics(ring);
      currentDrawerFeature.properties.area_sqm = metrics.areaSqm;
      currentDrawerFeature.properties.perimeter_m = metrics.perimeterM;

      const areaEl = document.getElementById('drawerArea');
      const perimEl = document.getElementById('drawerPerimeter');
      if (areaEl) areaEl.textContent = `${metrics.areaSqm.toFixed(1)} m² (${(metrics.areaSqm / 10000).toFixed(3)} Ha)`;
      if (perimEl) perimEl.textContent = `${metrics.perimeterM.toFixed(1)} m`;
    });

    boundaryEditMarkers.push(marker);
  });
}

function disableParcelVertexHandles() {
  boundaryEditMarkers.forEach(m => map.removeLayer(m));
  boundaryEditMarkers = [];
}

function generateClientVertexHash(coords) {
  if (!coords || coords.length < 3) return "0000000";
  const BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  
  let pts = coords.map(([lon, lat]) => [Number(lon).toFixed(6), Number(lat).toFixed(6)]);
  if (pts.length > 3 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1]) {
    pts = pts.slice(0, -1);
  }
  
  let minIdx = 0;
  for (let i = 1; i < pts.length; i++) {
    if (pts[i][0] < pts[minIdx][0] || (pts[i][0] === pts[minIdx][0] && pts[i][1] < pts[minIdx][1])) {
      minIdx = i;
    }
  }
  const canonicalPts = pts.slice(minIdx).concat(pts.slice(0, minIdx));
  const rawRepr = canonicalPts.map(p => `${p[0]},${p[1]}`).join('|');
  
  let hash = 2166136261;
  for (let i = 0; i < rawRepr.length; i++) {
    hash ^= rawRepr.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  let unsigned = hash >>> 0;
  let res = '';
  while (res.length < 7) {
    res = BASE36[unsigned % 36] + res;
    unsigned = Math.floor(unsigned / 36);
    if (unsigned === 0 && res.length < 7) {
      unsigned = (Math.imul(hash, 31) + res.length * 1013904223) >>> 0;
    }
  }
  return res.slice(-7);
}

function recalculateDrawerUlpin() {
  if (!currentDrawerFeature || !currentDrawerFeature.geometry) return;
  const geomType = currentDrawerFeature.geometry.type;
  let ring = geomType === 'Polygon' 
    ? currentDrawerFeature.geometry.coordinates[0] 
    : (geomType === 'MultiPolygon' ? currentDrawerFeature.geometry.coordinates[0][0] : null);
  
  if (!ring || !ring.length) return;

  const vertexHash = generateClientVertexHash(ring);
  const newUlpin = `22-10-001-${vertexHash}`;
  currentDrawerFeature.properties.ulpin = newUlpin;

  const ulpinEl = document.getElementById('drawerUlpin');
  if (ulpinEl) {
    ulpinEl.textContent = newUlpin;
    ulpinEl.title = newUlpin;
  }

  renderResults(currentFeatureSet, { saved: false });
  showToast(`Standard 14-Digit ULPIN Re-evaluated: ${newUlpin}`, 'success');
}

function deleteCurrentDrawerParcel() {
  if (!currentDrawerFeature) return;
  const idx = currentFeatureSet.indexOf(currentDrawerFeature);
  if (idx > -1) {
    currentFeatureSet.splice(idx, 1);
  }
  closeDrawer();
  renderResults(currentFeatureSet, { saved: false });
  showToast('Parcel deleted from workspace.', 'info');
}

async function saveSingleParcelToDB() {
  if (!currentDrawerFeature) return;

  const btn = document.getElementById('saveSingleBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>Saving...</span>';
  }

  try {
    const payload = {
      type: 'FeatureCollection',
      features: [currentDrawerFeature],
    };

    const res = await apiFetch('/parcels/save', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    showToast(`Parcel saved to PostGIS database!`, 'success');
    if (res.saved_parcels && res.saved_parcels.features && res.saved_parcels.features.length) {
      const savedFeature = res.saved_parcels.features[0];
      currentDrawerFeature.properties.id = savedFeature.properties.id;
    }
    renderResults(currentFeatureSet, { saved: true });
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg><span>Save to DB</span>`;
    }
  }
}

async function saveDrawerChanges() {
  if (!currentDrawerFeature) return;

  const newLandUse = document.getElementById('drawerLandUse').value;
  const newOwner = document.getElementById('drawerOwner').value.trim() || null;
  const p = currentDrawerFeature.properties || {};

  if (p.id) {
    const saveBtn = document.getElementById('drawerSaveBtn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }
    try {
      const updated = await apiFetch(`/parcels/${p.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          land_use_type: newLandUse,
          owner_name: newOwner,
        }),
      });

      p.land_use = updated.properties.land_use;
      p.owner_name = updated.properties.owner_name;
      showToast('Parcel attributes updated and synced to database.', 'success');
      renderResults(currentFeatureSet, { saved: true });
      closeDrawer();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Update Info'; }
    }
  } else {
    p.land_use = newLandUse;
    p.owner_name = newOwner;
    showToast('Local parcel attributes updated. Click "Save to DB" to commit.', 'info');
    renderResults(currentFeatureSet, { saved: false });
    closeDrawer();
  }
}

async function saveAllParcels() {
  if (!currentFeatureSet || !currentFeatureSet.length) {
    showToast('Save karne ke liye koi parcels nahi hain.', 'error');
    return;
  }

  const saveBtn = document.getElementById('saveAllBtn');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
  }

  try {
    const payload = {
      type: 'FeatureCollection',
      features: currentFeatureSet,
    };

    const res = await apiFetch('/parcels/save', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    showToast(`Saved ${res.saved_count} parcels to PostGIS (${res.duplicate_count} duplicates skipped).`, 'success');
    if (res.saved_parcels && res.saved_parcels.features) {
      renderResults(res.saved_parcels.features, { saved: true });
    }
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save All';
    }
  }
}

async function loadSavedParcels() {
  try {
    const data = await apiFetch('/parcels?limit=250');
    if (data && data.features && data.features.length) {
      renderResults(data.features, { saved: true });
    }
  } catch (_) {}
}

async function loadUserProfile() {
  const user = getCurrentUser();
  const labelEl = document.getElementById('userLabel');
  if (user && labelEl) {
    labelEl.textContent = `${user.full_name || user.email} (${(user.role || 'Surveyor').toUpperCase()})`;
  } else {
    try {
      const liveUser = await apiFetch('/auth/me');
      if (liveUser && labelEl) {
        localStorage.setItem('bhudrishti_user', JSON.stringify(liveUser));
        labelEl.textContent = `${liveUser.full_name || liveUser.email} (${(liveUser.role || 'Surveyor').toUpperCase()})`;
      }
    } catch (_) {}
  }
}

// -----------------------------------------------------------------
// EVENT INITIALIZER
// -----------------------------------------------------------------

window.addEventListener('load', () => {
  initDashboard();
});