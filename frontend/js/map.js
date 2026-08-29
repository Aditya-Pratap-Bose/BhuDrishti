// =================================================================
// js/map.js — BhuDrishti GIS Console Controller
// Map interaction, drawing tools, SAM AI detection, Inspector Drawer,
// drone uploads, and PostGIS layer management.
// =================================================================

// GUARD: Token check
if (typeof getAuthToken === 'function' && !getAuthToken()) {
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

const CAMPUS_CENTER = [21.1345, 81.6685];
const CAMPUS_BBOX = [81.6650, 21.1310, 81.6720, 21.1380];

let map;
let drawnItems;
let drawControl;
let selectedBbox = null;
let currentSourceType = 'sentinel';

let resultLayer = null;        // AI Detected parcels GeoJSON layer
let savedParcelsLayer = null;  // Database saved parcels GeoJSON layer
let rawImageryOverlay = null;  // Satellite/Drone raw raster preview ImageOverlay
let activeHighlightLayer = null;

let currentFeatureSet = [];    // Currently active features (displayed on map & right panel)
let currentDrawerFeature = null;

function handleLogout() {
  if (typeof clearSession === 'function') clearSession();
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

// -----------------------------------------------------------------
// INITIALIZATION
// -----------------------------------------------------------------

async function initDashboard() {
  initMap();
  await loadUserProfile();
  await loadSavedParcels();
}

function initMap() {
  map = L.map('map', { zoomControl: true, minZoom: 3 }).setView(CAMPUS_CENTER, 17);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  // Test reference box
  L.rectangle([[CAMPUS_BBOX[1], CAMPUS_BBOX[0]], [CAMPUS_BBOX[3], CAMPUS_BBOX[2]]], {
    color: '#10B981', weight: 1.5, dashArray: '4 4', fill: false, interactive: false,
  }).addTo(map).bindTooltip('SSIPMT test area', { permanent: false, direction: 'top' });

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
      polygon: false, polyline: false, circle: false, circlemarker: false, marker: false,
      rectangle: {
        shapeOptions: {
          color: '#10B981',
          weight: 2,
          fillOpacity: 0.12,
          dashArray: '3 3'
        }
      },
    },
    edit: { featureGroup: drawnItems, remove: true },
  });
  map.addControl(drawControl);

  map.on(L.Draw.Event.CREATED, (e) => {
    drawnItems.clearLayers();
    drawnItems.addLayer(e.layer);
    const b = e.layer.getBounds();
    selectedBbox = {
      min_lon: b.getWest(),
      min_lat: b.getSouth(),
      max_lon: b.getEast(),
      max_lat: b.getNorth(),
    };
    updateBboxCard();
    updateLiveMeasure(b);
    setDetectEnabled(true);
  });

  map.on(L.Draw.Event.DELETED, () => {
    selectedBbox = null;
    document.getElementById('bboxCard').classList.add('hidden');
    document.getElementById('liveMeasureBox').classList.add('hidden');
    setDetectEnabled(false);
  });

  map.on(L.Draw.Event.EDITED, (e) => {
    e.layers.eachLayer((layer) => {
      const b = layer.getBounds();
      selectedBbox = {
        min_lon: b.getWest(),
        min_lat: b.getSouth(),
        max_lon: b.getEast(),
        max_lat: b.getNorth(),
      };
      updateBboxCard();
      updateLiveMeasure(b);
    });
  });

  setTimeout(() => { map.invalidateSize(); }, 300);
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
// UI & SOURCE TYPE HANDLING
// -----------------------------------------------------------------

function setSourceType(source) {
  currentSourceType = source;
  const droneBox = document.getElementById('droneUploadBox');
  if (source === 'drone') {
    droneBox.classList.remove('hidden');
    setDetectEnabled(false);
  } else {
    droneBox.classList.add('hidden');
    setDetectEnabled(Boolean(selectedBbox));
  }
}

function updateBboxCard() {
  const card = document.getElementById('bboxCard');
  const text = document.getElementById('bboxText');
  if (!selectedBbox) { card.classList.add('hidden'); return; }
  text.innerHTML = `W ${selectedBbox.min_lon.toFixed(5)}  S ${selectedBbox.min_lat.toFixed(5)}<br/>E ${selectedBbox.max_lon.toFixed(5)}  N ${selectedBbox.max_lat.toFixed(5)}`;
  card.classList.remove('hidden');
}

function updateLiveMeasure(bounds) {
  const box = document.getElementById('liveMeasureBox');
  const text = document.getElementById('liveMeasureText');
  if (!box || !text) return;

  const latDiff = Math.abs(bounds.getNorth() - bounds.getSouth());
  const lonDiff = Math.abs(bounds.getEast() - bounds.getWest());
  const avgLatRad = ((bounds.getNorth() + bounds.getSouth()) / 2) * (Math.PI / 180);
  const heightM = latDiff * 111320;
  const widthM = lonDiff * 111320 * Math.cos(avgLatRad);
  const areaSqm = widthM * heightM;

  text.innerHTML = `Width: ${widthM.toFixed(1)}m | Height: ${heightM.toFixed(1)}m<br/>Est. Area: ${(areaSqm / 10000).toFixed(2)} Ha (${areaSqm.toFixed(0)} m²)`;
  box.classList.remove('hidden');
}

function setDetectEnabled(on) {
  const btn = document.getElementById('detectBtn');
  if (!btn) return;
  btn.disabled = !on;
  const label = document.getElementById('detectBtnLabel');
  if (label) {
    label.textContent = on ? 'Detect Parcels' : (currentSourceType === 'drone' ? 'Select GeoTIFF file' : 'Draw a rectangle first');
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
// AI INFERENCE PIPELINE
// -----------------------------------------------------------------

async function detectParcels() {
  if (!selectedBbox) {
    showToast('Pehle map par rectangle draw karein.', 'error');
    return;
  }
  const overlay = document.getElementById('loadingOverlay');
  overlay.classList.remove('hidden');
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
  if (!fileInput || !fileInput.files.length) {
    showToast('Pehle koi .tif ya .tiff GeoTIFF file select karein.', 'error');
    return;
  }
  const file = fileInput.files[0];
  const overlay = document.getElementById('loadingOverlay');
  overlay.classList.remove('hidden');

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

  // Handle raw satellite/drone preview raster image
  if (data.preview_image_base64 && data.preview_bounds) {
    const [minx, miny, maxx, maxy] = data.preview_bounds;
    const imageBounds = [[miny, minx], [maxy, maxx]];
    if (rawImageryOverlay) {
      map.removeLayer(rawImageryOverlay);
    }
    rawImageryOverlay = L.imageOverlay(`data:image/png;base64,${data.preview_image_base64}`, imageBounds, {
      opacity: 0.85,
    });
    const layerRawCheck = document.getElementById('layerRaw');
    if (!layerRawCheck || layerRawCheck.checked) {
      rawImageryOverlay.addTo(map);
    }
  }

  renderResults(features, { saved: false });
  showToast(`${features.length} parcels detected by AI.`, 'success');
}

// -----------------------------------------------------------------
// RENDERING RESULTS & PARCEL CARDS
// -----------------------------------------------------------------

function renderResults(features, { saved }) {
  currentFeatureSet = features;
  const list = document.getElementById('resultsList');
  const header = document.getElementById('resultsHeader');
  const empty = document.getElementById('emptyState');
  const countEl = document.getElementById('resultCount');
  const saveAllBtn = document.getElementById('saveAllBtn');

  if (resultLayer) {
    map.removeLayer(resultLayer);
    resultLayer = null;
  }
  list.innerHTML = '';

  if (!features || !features.length) {
    if (header) header.classList.add('hidden');
    if (empty) empty.classList.remove('hidden');
    if (countEl) countEl.textContent = '0';
    return;
  }

  if (empty) empty.classList.add('hidden');
  if (header) header.classList.remove('hidden');
  if (countEl) countEl.textContent = features.length;
  if (saveAllBtn) saveAllBtn.classList.toggle('hidden', saved);

  resultLayer = L.geoJSON({ type: 'FeatureCollection', features }, {
    style: (feature) => ({
      color: saved ? '#3B82F6' : '#10B981',
      weight: 2,
      fillOpacity: 0.2,
      className: 'parcel-glow',
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(`<b>${p.ulpin}</b><br/>${p.land_use || 'Unclassified'}<br/>${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0} m²`, {
        sticky: true,
      });

      layer.on('click', () => {
        openDrawer(feature, layer);
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

  features.forEach((feature, idx) => {
    const p = feature.properties || {};
    const card = document.createElement('div');
    card.className = 'fade-in border border-line rounded-xl p-3.5 bg-surface2 hover:border-scan/50 transition cursor-pointer hover:bg-line/40';
    card.innerHTML = `
      <div class="flex items-center justify-between mb-1.5">
        <span class="font-mono text-xs text-scan font-medium">${p.ulpin}</span>
        <span class="text-[10px] px-2 py-0.5 rounded-full bg-surface border border-line text-faint">${p.land_use || 'Unclassified'}</span>
      </div>
      <div class="flex items-center justify-between text-[11px] text-faint">
        <span>Area: <b class="text-ink font-mono">${p.area_sqm ? Number(p.area_sqm).toFixed(1) : 0}</b> m²</span>
        <span>Perimeter: <b class="text-ink font-mono">${p.perimeter_m ? Number(p.perimeter_m).toFixed(1) : 0}</b> m</span>
      </div>
      ${p.owner_name ? `<div class="text-[10px] text-emerald-400/80 mt-1 truncate">Owner: ${p.owner_name}</div>` : ''}
    `;

    card.addEventListener('click', () => {
      openDrawer(feature);
      // Zoom to polygon
      try {
        const tempLayer = L.geoJSON(feature);
        map.fitBounds(tempLayer.getBounds(), { padding: [60, 60] });
      } catch (_) {}
    });

    list.appendChild(card);
  });
}

// -----------------------------------------------------------------
// PERSISTENCE (POSTGIS CRUD)
// -----------------------------------------------------------------

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

    showToast(`Saved ${res.saved_count} parcels to PostGIS (${res.duplicate_count} skipped duplicates).`, 'success');
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
    const data = await apiFetch('/parcels?limit=200');
    if (data && data.features && data.features.length) {
      renderResults(data.features, { saved: true });
    }
  } catch (_) {
    // Database empty or initial load
  }
}

// -----------------------------------------------------------------
// PARCEL INSPECTOR DRAWER
// -----------------------------------------------------------------

function openDrawer(feature, layer) {
  currentDrawerFeature = feature;
  const p = feature.properties || {};

  document.getElementById('drawerUlpin').textContent = p.ulpin || 'N/A';
  document.getElementById('drawerArea').textContent = `${p.area_sqm ? Number(p.area_sqm).toFixed(2) : 0} m²`;
  document.getElementById('drawerPerimeter').textContent = `${p.perimeter_m ? Number(p.perimeter_m).toFixed(2) : 0} m`;
  document.getElementById('drawerLandUse').value = p.land_use || 'Unclassified';
  document.getElementById('drawerOwner').value = p.owner_name || '';

  if (activeHighlightLayer) {
    map.removeLayer(activeHighlightLayer);
  }
  activeHighlightLayer = L.geoJSON(feature, {
    style: {
      color: '#F59E0B',
      weight: 3,
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

  // If parcel is already saved in DB (has ID), update on server
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
      showToast('Parcel attributes updated successfully.', 'success');
      renderResults(currentFeatureSet, { saved: true });
      closeDrawer();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save Changes'; }
    }
  } else {
    // Unsaved local AI detection
    p.land_use = newLandUse;
    p.owner_name = newOwner;
    showToast('Local parcel attributes updated. Click "Save All" to commit to database.', 'info');
    renderResults(currentFeatureSet, { saved: false });
    closeDrawer();
  }
}

// -----------------------------------------------------------------
// EVENT LISTENERS
// -----------------------------------------------------------------

window.addEventListener('load', () => {
  initDashboard();
});