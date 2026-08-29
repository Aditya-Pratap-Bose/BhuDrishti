// =================================================================
// js/map.js — sirf dashboard.html ke liye. Map, detect, save, guard.
// =================================================================

// GUARD: token nahi hai toh yahan tak pahunchna hi nahi chahiye tha.
if (!getAuthToken()) {
  window.location.href = '/';
}

const CAMPUS_CENTER = [21.1345, 81.6685];
const CAMPUS_BBOX = [81.6650, 21.1310, 81.6720, 21.1380];

let map, drawnItems, drawControl, selectedBbox = null, resultLayer = null;
let lastDetectedFeatures = [];

function handleLogout() {
  clearSession();
  window.location.href = '/';
}

function initMap() {
  map = L.map('map', { zoomControl: true, minZoom: 3 }).setView(CAMPUS_CENTER, 17);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  L.rectangle([[CAMPUS_BBOX[1], CAMPUS_BBOX[0]], [CAMPUS_BBOX[3], CAMPUS_BBOX[2]]], {
    color: '#8695B5', weight: 1, dashArray: '4 4', fill: false, interactive: false,
  }).addTo(map).bindTooltip('SSIPMT test area', { permanent: false, direction: 'top' });

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
      polygon: false, polyline: false, circle: false, circlemarker: false, marker: false,
      rectangle: { shapeOptions: { color: '#F0A93B', weight: 2, fillOpacity: 0.08 } },
    },
    edit: { featureGroup: drawnItems, remove: true },
  });
  map.addControl(drawControl);

  map.on(L.Draw.Event.CREATED, (e) => {
    drawnItems.clearLayers();
    drawnItems.addLayer(e.layer);
    const b = e.layer.getBounds();
    selectedBbox = { min_lon: b.getWest(), min_lat: b.getSouth(), max_lon: b.getEast(), max_lat: b.getNorth() };
    updateBboxCard();
    setDetectEnabled(true);
  });

  map.on(L.Draw.Event.DELETED, () => {
    selectedBbox = null;
    document.getElementById('bboxCard').classList.add('hidden');
    setDetectEnabled(false);
  });

  map.on(L.Draw.Event.EDITED, (e) => {
    e.layers.eachLayer((layer) => {
      const b = layer.getBounds();
      selectedBbox = { min_lon: b.getWest(), min_lat: b.getSouth(), max_lon: b.getEast(), max_lat: b.getNorth() };
      updateBboxCard();
    });
  });
}

function updateBboxCard() {
  const card = document.getElementById('bboxCard');
  const text = document.getElementById('bboxText');
  if (!selectedBbox) { card.classList.add('hidden'); return; }
  text.innerHTML = `W ${selectedBbox.min_lon.toFixed(5)}  S ${selectedBbox.min_lat.toFixed(5)}<br/>E ${selectedBbox.max_lon.toFixed(5)}  N ${selectedBbox.max_lat.toFixed(5)}`;
  card.classList.remove('hidden');
}

function setDetectEnabled(on) {
  const btn = document.getElementById('detectBtn');
  btn.disabled = !on;
  document.getElementById('detectBtnLabel').textContent = on ? 'Detect parcels' : 'Draw a rectangle first';
}

async function detectParcels() {
  if (!selectedBbox) return;
  document.getElementById('loadingOverlay').classList.remove('hidden');
  setDetectEnabled(false);
  try {
    const data = await apiFetch('/satellite/process-bbox', {
      method: 'POST',
      body: JSON.stringify(selectedBbox),
    });
    lastDetectedFeatures = data.features || [];
    renderResults(lastDetectedFeatures, { saved: false });
    showToast(`${lastDetectedFeatures.length} parcels detect hue.`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    document.getElementById('loadingOverlay').classList.add('hidden');
    setDetectEnabled(true);
  }
}

function renderResults(features, { saved }) {
  const list = document.getElementById('resultsList');
  const header = document.getElementById('resultsHeader');
  const empty = document.getElementById('emptyState');

  if (resultLayer) { map.removeLayer(resultLayer); resultLayer = null; }
  list.innerHTML = '';

  if (!features.length) {
    header.classList.add('hidden');
    empty.classList.remove('hidden');
    return;
  }

  empty.classList.add('hidden');
  header.classList.remove('hidden');
  document.getElementById('resultCount').textContent = features.length;
  document.getElementById('saveAllBtn').classList.toggle('hidden', saved);

  resultLayer = L.geoJSON({ type: 'FeatureCollection', features }, {
    style: { color: '#38D9C9', weight: 2, fillOpacity: 0.12, className: 'parcel-glow' },
    onEachFeature: (feature, layer) => { layer.bindTooltip(feature.properties.ulpin, { sticky: true }); },
  }).addTo(map);

  try { map.fitBounds(resultLayer.getBounds(), { padding: [40, 40] }); } catch (_) {}

  features.forEach((f, idx) => {
    const p = f.properties;
    const card = document.createElement('div');
    card.className = 'fade-in border border-line rounded-lg p-3 bg-base/60 hover:border-scan/40 transition cursor-pointer';
    card.innerHTML = `
      <div class="flex items-center justify-between mb-1.5">
        <span class="font-mono text-[11px] text-scan truncate">${p.ulpin}</span>
        ${saved ? '<span class="text-[10px] text-amber border border-amber/30 rounded px-1.5 py-0.5">Saved</span>' : ''}
      </div>
      <div class="flex items-center justify-between text-xs text-faint">
        <span>${p.area_sqm.toFixed(1)} m² · ${p.perimeter_m.toFixed(1)} m perimeter</span>
      </div>
      <div class="mt-1.5 text-[11px] text-faint">${p.land_use || 'Unclassified'}</div>
    `;
    card.addEventListener('click', () => {
      const layer = resultLayer.getLayers()[idx];
      if (layer) map.fitBounds(layer.getBounds(), { padding: [60, 60] });
    });
    list.appendChild(card);
  });
}

async function saveAllParcels() {
  if (!lastDetectedFeatures.length) return;
  const btn = document.getElementById('saveAllBtn');
  btn.disabled = true; btn.textContent = 'Saving…';
  try {
    const result = await apiFetch('/parcels/save', {
      method: 'POST',
      body: JSON.stringify({ type: 'FeatureCollection', features: lastDetectedFeatures }),
    });
    showToast(`${result.saved_count} saved, ${result.duplicate_count} already in registry.`, 'success');
    renderResults(result.saved_parcels.features, { saved: true });
  } catch (err) {
    showToast(`Save failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Save to registry';
  }
}

async function loadSavedParcels() {
  try {
    const data = await apiFetch('/parcels');
    renderResults(data.features || [], { saved: true });
  } catch (err) {
    if (err.status === 401) handleLogout();
    else showToast(`Registry load failed: ${err.message}`, 'error');
  }
}

// INIT
(async function initDashboard() {
  const user = getCurrentUser();
  document.getElementById('userLabel').textContent = user ? `${user.full_name} · ${user.role}` : '';
  const badge = document.getElementById('modeBadge');
  badge.textContent = 'Live';
  badge.className = 'ml-2 text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border border-amber/40 text-amber';

  initMap();
  setTimeout(() => map.invalidateSize(), 50);
  loadSavedParcels();
})();