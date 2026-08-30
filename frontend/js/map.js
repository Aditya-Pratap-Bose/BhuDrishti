// =================================================================
// js/map.js — BhuDrishti WebGIS Cadastral Console Controller
// Multi-Source AI Detection, geotiff.js Client-Side Parser,
// Real-time Telemetry HUD, PostGIS Persistence, & Attribute Inspector.
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
let currentSourceType = 'sentinel';
let selectedDroneFile = null;

let resultLayer = null;        // Vectorized AI parcel polygons
let savedParcelsLayer = null;  // PostgreSQL/PostGIS registered parcels
let rawImageryOverlay = null;  // Satellite/Drone raw preview ImageOverlay
let activeHighlightLayer = null;

let currentFeatureSet = [];    // Active features displayed on map & sidebar
let currentDrawerFeature = null;

let isDrawing = false;
let isEditing = false;
let drawAnchorLatLng = null;

function handleLogout() {
  if (typeof clearSession === 'function') clearSession();
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

// -----------------------------------------------------------------
// 1. INITIALIZATION & BASEMAPS
// -----------------------------------------------------------------

async function initDashboard() {
  initMap();
  setupDropzone();
  await loadUserProfile();
  await loadSavedParcels();
}

function initMap() {
  map = L.map('map', {
    zoomControl: false, // We place custom zoom controls or clean bottom position
    minZoom: 3,
    maxZoom: 21,
  }).setView(RAIPUR_SSIPMT_CENTER, 17);

  // Basemap Providers
  basemapLayers['satellite'] = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
    maxZoom: 20,
  });

  basemapLayers['dark'] = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    maxZoom: 20,
    subdomains: 'abcd',
  });

  basemapLayers['osm'] = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  });

  basemapLayers['satellite'].addTo(map);

  // Add zoom control at bottom-right
  L.control.zoom({ position: 'bottomleft' }).addTo(map);

  // Raipur SSIPMT Test Zone Reference Boundary
  L.rectangle([[RAIPUR_SSIPMT_BBOX[1], RAIPUR_SSIPMT_BBOX[0]], [RAIPUR_SSIPMT_BBOX[3], RAIPUR_SSIPMT_BBOX[2]]], {
    color: '#10B981', weight: 1.5, dashArray: '4 4', fill: false, interactive: false,
  }).addTo(map).bindTooltip('Raipur SSIPMT Test Cadastre', { permanent: false, direction: 'top' });

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  // Initialize Leaflet Draw Rectangle Drawer Programmatically
  rectangleDrawer = new L.Draw.Rectangle(map, {
    shapeOptions: {
      color: '#10B981',
      weight: 2,
      fillOpacity: 0.15,
      dashArray: '3 3',
    },
  });

  // ---------------------------------------------------------------
  // REAL-TIME TELEMETRY & DRAW EVENT HOOKS
  // ---------------------------------------------------------------

  map.on(L.Draw.Event.DRAWSTART, () => {
    isDrawing = true;
    drawAnchorLatLng = null;
    document.getElementById('toolDrawBtn').classList.add('bg-scan/20', 'text-scan', 'border-scan/40');
  });

  map.on(L.Draw.Event.DRAWSTOP, () => {
    isDrawing = false;
    drawAnchorLatLng = null;
    document.getElementById('toolDrawBtn').classList.remove('bg-scan/20', 'text-scan', 'border-scan/40');
  });

  map.on('mousedown', (e) => {
    if (isDrawing && !drawAnchorLatLng) {
      drawAnchorLatLng = e.latlng;
    }
  });

  map.on('mousemove', (e) => {
    // 1. Real-time telemetry while dragging to draw rectangle
    if (isDrawing && drawAnchorLatLng) {
      const min_lon = Math.min(drawAnchorLatLng.lng, e.latlng.lng);
      const max_lon = Math.max(drawAnchorLatLng.lng, e.latlng.lng);
      const min_lat = Math.min(drawAnchorLatLng.lat, e.latlng.lat);
      const max_lat = Math.max(drawAnchorLatLng.lat, e.latlng.lat);
      updateTelemetryHUD(min_lon, min_lat, max_lon, max_lat);
    }
    // 2. Real-time telemetry while dragging vertices in edit mode
    else if (isEditing && drawnItems.getLayers().length > 0) {
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
  if (basemapLayers[type]) {
    basemapLayers[type].addTo(map);
    currentBasemap = type;
  }
}

// -----------------------------------------------------------------
// 2. PROGRAMMATIC CADASTRE DRAWING TOOLS
// -----------------------------------------------------------------

function triggerDrawRectangle() {
  if (isDrawing) {
    rectangleDrawer.disable();
    isDrawing = false;
    return;
  }
  if (isEditing) {
    triggerEditRectangle(); // Turn off edit mode first
  }
  rectangleDrawer.enable();
}

function triggerEditRectangle() {
  const layers = drawnItems.getLayers();
  if (layers.length === 0) {
    showToast('Pehle map par rectangle draw karein.', 'info');
    return;
  }

  const editBtn = document.getElementById('toolEditBtn');
  if (!isEditing) {
    if (!editHandler) {
      editHandler = new L.EditToolbar.Edit(map, {
        featureGroup: drawnItems,
        selectedPathOptions: { color: '#F59E0B', weight: 2.5 },
      });
    }
    editHandler.enable();
    isEditing = true;
    editBtn.classList.add('bg-amber/20', 'text-amber', 'border-amber/40');
    showToast('Edit Mode Active: Drag handles to resize boundary.', 'info');
  } else {
    if (editHandler) {
      editHandler.save();
      editHandler.disable();
    }
    isEditing = false;
    editBtn.classList.remove('bg-amber/20', 'text-amber', 'border-amber/40');
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
// 3. REAL-TIME TELEMETRY HUD
// -----------------------------------------------------------------

function updateTelemetryHUD(min_lon, min_lat, max_lon, max_lat) {
  const coordsEl = document.getElementById('hudCoords');
  const dimsEl = document.getElementById('hudDims');
  const areaEl = document.getElementById('hudArea');

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
  const coordsEl = document.getElementById('hudCoords');
  const dimsEl = document.getElementById('hudDims');
  const areaEl = document.getElementById('hudArea');
  if (coordsEl) coordsEl.textContent = 'Draw a rectangle on the map';
  if (dimsEl) dimsEl.textContent = '0m \u00D7 0m';
  if (areaEl) areaEl.textContent = '0.00 Ha (0 m\u00B2)';
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
  metaCard.classList.remove('hidden');

  try {
    showToast('geotiff.js: Reading raster metadata in browser...', 'info');
    
    // 1. Read GeoTIFF Blob using geotiff.js
    const tiff = await GeoTIFF.fromBlob(file);
    const image = await tiff.getImage();
    
    const width = image.getWidth();
    const height = image.getHeight();
    const samples = image.getSamplesPerPixel();
    if (dimsEl) dimsEl.textContent = `${width} \u00D7 ${height} px (${samples} bands)`;

    // 2. Extract Geographic / Projected Bounding Box
    const origin = image.getOrigin();       // [originX, originY, originZ]
    const resolution = image.getResolution(); // [resX, resY, resZ]
    const bbox = image.getBoundingBox();    // [minX, minY, maxX, maxY]

    const geoKeys = image.getGeoKeys() || {};
    let epsgCode = geoKeys.ProjectedCSTypeGeoKey || geoKeys.GeographicTypeGeoKey || 32643;
    if (crsEl) crsEl.textContent = `EPSG:${epsgCode}`;

    let minLon, minLat, maxLon, maxLat;

    // 3. Convert coordinates to WGS84 (EPSG:4326) using proj4 if projected
    if (epsgCode !== 4326 && typeof proj4 !== 'undefined') {
      try {
        // Define common Indian UTM zones if not already in proj4
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
        // Fallback: if already lat/lon
        minLon = bbox[0]; minLat = bbox[1]; maxLon = bbox[2]; maxLat = bbox[3];
      }
    } else {
      minLon = bbox[0]; minLat = bbox[1]; maxLon = bbox[2]; maxLat = bbox[3];
    }

    // 4. Calculate Ground Area
    const latDiff = Math.abs(maxLat - minLat);
    const lonDiff = Math.abs(maxLon - minLon);
    const avgLatRad = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const groundAreaSqm = (latDiff * 111320) * (lonDiff * 111320 * Math.cos(avgLatRad));
    const groundAreaHa = (groundAreaSqm / 10000).toFixed(2);
    if (areaEl) areaEl.textContent = `${groundAreaHa} Ha (${(groundAreaSqm / 1000).toFixed(1)}k m\u00B2)`;

    // 5. Draw detected bounding box on map & fly to it!
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
    console.warn('geotiff.js quick metadata extraction note:', err);
    if (dimsEl) dimsEl.textContent = 'Standard GeoTIFF';
    showToast('GeoTIFF file selected. Click "Run AI Boundary Extraction" below.', 'info');
  }
}

// -----------------------------------------------------------------
// 5. DATA SOURCE SELECTION
// -----------------------------------------------------------------

function setSourceType(source) {
  currentSourceType = source;
  const droneBox = document.getElementById('droneUploadBox');
  const detectBtn = document.getElementById('detectBtn');

  if (source === 'drone') {
    droneBox.classList.remove('hidden');
    if (detectBtn) detectBtn.classList.add('hidden'); // Drone uses its own dedicated run button
  } else {
    droneBox.classList.add('hidden');
    if (detectBtn) detectBtn.classList.remove('hidden');
    setDetectEnabled(Boolean(selectedBbox));
  }
}

function setDetectEnabled(on) {
  const btn = document.getElementById('detectBtn');
  if (!btn) return;
  btn.disabled = !on;
  const label = document.getElementById('detectBtnLabel');
  if (label) {
    label.textContent = on ? 'Extract Land Parcels (SAM AI)' : 'Draw a boundary box first';
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
  overlay.classList.remove('hidden');
  if (statusText) statusText.textContent = `Processing ${currentSourceType.toUpperCase()} imagery via SAM AI...`;
  setDetectEnabled(false);

  try {
    const payload = {
      min_lon: selectedBbox.min_lon,
      min_lat: selectedBbox.min_lat,
      max_lon: selectedBbox.max_lon,
      max_lat: selectedBbox.max_lat,
      source_type: currentSourceType,
    };

    const data = await apiFetch('/satellite/process-bbox', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    handleInferenceResponse(data);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    overlay.classList.add('hidden');
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
  overlay.classList.remove('hidden');
  if (statusText) statusText.textContent = 'Running SAM AI on high-res Drone GeoTIFF...';

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
    overlay.classList.add('hidden');
  }
}

function handleInferenceResponse(data) {
  const features = data.features || [];
  currentFeatureSet = features;

  // Handle raw satellite / drone raster preview ImageOverlay
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
  showToast(`Success: Extracted ${features.length} land parcel boundaries.`, 'success');
}

// -----------------------------------------------------------------
// 7. RESULTS RENDERING & SUMMARY METRICS
// -----------------------------------------------------------------

function renderResults(features, { saved }) {
  currentFeatureSet = features;
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
  list.innerHTML = '';

  if (!features || !features.length) {
    if (header) header.classList.add('hidden');
    if (empty) empty.classList.remove('hidden');
    if (countEl) countEl.textContent = '0';
    if (headerCount) headerCount.textContent = '0';
    return;
  }

  if (empty) empty.classList.add('hidden');
  if (header) header.classList.remove('hidden');
  if (countEl) countEl.textContent = features.length;
  if (headerCount) headerCount.textContent = features.length;
  if (saveAllBtn) saveAllBtn.classList.toggle('hidden', saved);

  // Calculate Aggregated Metrics
  let totalAreaSqm = 0;
  let savedCount = 0;
  features.forEach(f => {
    const a = f.properties && f.properties.area_sqm ? Number(f.properties.area_sqm) : 0;
    totalAreaSqm += a;
    if (f.properties && f.properties.id) savedCount++;
  });
  const totalAreaHa = (totalAreaSqm / 10000).toFixed(2);
  const avgAreaSqm = (totalAreaSqm / features.length).toFixed(0);

  if (statTotalArea) statTotalArea.textContent = `${totalAreaHa} Ha`;
  if (statAvgArea) statAvgArea.textContent = `${avgAreaSqm} m²`;
  if (statSavedCount) statSavedCount.textContent = `${savedCount}/${features.length}`;

  // Interactive GeoJSON Layer
  resultLayer = L.geoJSON({ type: 'FeatureCollection', features }, {
    style: (feature) => ({
      color: saved ? '#3B82F6' : '#10B981',
      weight: 2,
      fillOpacity: 0.22,
      className: 'parcel-glow',
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(`<b>${p.ulpin}</b><br/>${p.land_use || 'Unclassified'}<br/>${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0} m²`, {
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
  features.forEach((feature, idx) => {
    const p = feature.properties || {};
    const card = document.createElement('div');
    card.className = 'fade-in border border-line rounded-xl p-3 bg-surface2/70 hover:bg-surface3 hover:border-scan/50 transition cursor-pointer group shadow-sm';
    card.innerHTML = `
      <div class="flex items-center justify-between mb-1.5">
        <span class="font-mono text-xs text-scan font-semibold group-hover:text-emerald-300 transition truncate max-w-[180px]">${p.ulpin}</span>
        <span class="text-[9px] font-mono px-2 py-0.5 rounded-full bg-surface border border-line text-faint">${p.land_use || 'Unclassified'}</span>
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
// 8. ATTRIBUTE INSPECTOR & POSTGIS CRUD
// -----------------------------------------------------------------

function openDrawer(feature) {
  currentDrawerFeature = feature;
  const p = feature.properties || {};

  const ulpinEl = document.getElementById('drawerUlpin');
  const areaEl = document.getElementById('drawerArea');
  const perimEl = document.getElementById('drawerPerimeter');
  const landUseEl = document.getElementById('drawerLandUse');
  const ownerEl = document.getElementById('drawerOwner');

  if (ulpinEl) ulpinEl.textContent = p.ulpin || 'N/A';
  if (areaEl) areaEl.textContent = `${p.area_sqm ? Number(p.area_sqm).toFixed(2) : 0} m² (${((p.area_sqm || 0) / 10000).toFixed(3)} Ha)`;
  if (perimEl) perimEl.textContent = `${p.perimeter_m ? Number(p.perimeter_m).toFixed(2) : 0} m`;
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

  document.getElementById('parcelDrawer').classList.remove('hidden');
}

function closeDrawer() {
  document.getElementById('parcelDrawer').classList.add('hidden');
  if (activeHighlightLayer) {
    map.removeLayer(activeHighlightLayer);
    activeHighlightLayer = null;
  }
  currentDrawerFeature = null;
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
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save Attributes'; }
    }
  } else {
    p.land_use = newLandUse;
    p.owner_name = newOwner;
    showToast('Local parcel attributes updated. Click "Save All" to commit.', 'info');
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