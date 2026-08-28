// =================================================================
// CONFIG & STATE
// =================================================================
let API_BASE_URL = `${window.location.origin}/api/v1`;
let authToken = localStorage.getItem('bhudrishti_token') || null;
let currentUser = JSON.parse(localStorage.getItem('bhudrishti_user') || 'null');

// SSIPMT campus, Raipur (Chhattisgarh) — matches the pipeline's test bbox
const CAMPUS_CENTER = [21.1345, 81.6685];
const CAMPUS_BBOX = [81.6650, 21.1310, 81.6720, 21.1380]; // [min_lon, min_lat, max_lon, max_lat]

let map, drawnItems, drawControl, selectedBbox = null, resultLayer = null;
let lastDetectedFeatures = []; // raw FeatureCollection.features from last detect call

// =================================================================
// API HELPER
// =================================================================
async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (networkErr) {
    throw new Error('Backend tak pahunch nahi paaye. Kya uvicorn chal raha hai, aur API endpoint sahi set hai?');
  }

  let data = null;
  try { data = await res.json(); } catch (_) { /* no body */ }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (HTTP ${res.status})`;
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

// =================================================================
// TOASTS
// =================================================================
function showToast(message, kind = 'error') {
  const box = document.getElementById('toastBox');
  const colors = {
    error: 'border-red-900/50 bg-red-950/80 text-red-200',
    info: 'border-scan/40 bg-surface/95 text-scan',
    success: 'border-amber/40 bg-surface/95 text-amber',
  };
  const el = document.createElement('div');
  el.className = `fade-in mb-2 text-sm rounded-lg border ${colors[kind] || colors.error} px-4 py-3 shadow-lg`;
  el.textContent = message;
  box.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

// =================================================================
// AUTH SCREEN LOGIC
// =================================================================
function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('loginForm').classList.toggle('hidden', !isLogin);
  document.getElementById('registerForm').classList.toggle('hidden', isLogin);
  document.getElementById('tabLogin').className = `flex-1 py-1.5 rounded-md text-sm font-medium transition ${isLogin ? 'bg-amber text-base' : 'text-faint'}`;
  document.getElementById('tabRegister').className = `flex-1 py-1.5 rounded-md text-sm font-medium transition ${!isLogin ? 'bg-amber text-base' : 'text-faint'}`;
  hideAuthError();
}
function showAuthError(msg) {
  const box = document.getElementById('authError');
  box.textContent = msg;
  box.classList.remove('hidden');
}
function hideAuthError() { document.getElementById('authError').classList.add('hidden'); }

async function handleLogin(e) {
  e.preventDefault();
  hideAuthError();
  const btn = document.getElementById('loginSubmitBtn');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('loginEmail').value,
        password: document.getElementById('loginPassword').value,
      }),
    });
    completeLogin(data);
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Sign in';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  hideAuthError();
  const btn = document.getElementById('registerSubmitBtn');
  btn.disabled = true; btn.textContent = 'Creating account…';
  try {
    const data = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        full_name: document.getElementById('regName').value,
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPassword').value,
        role: document.getElementById('regRole').value,
      }),
    });
    completeLogin(data);
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Create account';
  }
}

function completeLogin(tokenResponse) {
  authToken = tokenResponse.access_token;
  currentUser = tokenResponse.user;
  localStorage.setItem('bhudrishti_token', authToken);
  localStorage.setItem('bhudrishti_user', JSON.stringify(currentUser));
  enterDashboard();
}

function handleLogout() {
  authToken = null; currentUser = null;
  localStorage.removeItem('bhudrishti_token');
  localStorage.removeItem('bhudrishti_user');
  document.getElementById('dashboard').classList.add('hidden');
  document.getElementById('authScreen').classList.remove('hidden');
}

// API base URL settings popover
function toggleApiSettings() {
  const box = document.getElementById('apiSettingsBox');
  document.getElementById('apiBaseUrlInput').value = API_BASE_URL;
  box.classList.toggle('hidden');
}
function saveApiBaseUrl() {
  const val = document.getElementById('apiBaseUrlInput').value.trim();
  if (val) {
    API_BASE_URL = val.replace(/\/$/, '');
    localStorage.setItem('bhudrishti_api_base', API_BASE_URL);
    showAuthError('');
    hideAuthError();
    document.getElementById('apiSettingsBox').classList.add('hidden');
  }
}

// =================================================================
// DASHBOARD BOOT
// =================================================================
function enterDashboard() {
  document.getElementById('authScreen').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');

  document.getElementById('userLabel').textContent = currentUser ? `${currentUser.full_name} · ${currentUser.role}` : '';
  const badge = document.getElementById('modeBadge');
  badge.textContent = 'Live';
  badge.className = 'ml-2 text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border border-amber/40 text-amber';

  if (!map) initMap();
  setTimeout(() => map.invalidateSize(), 50);
  loadSavedParcels();
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

// =================================================================
// MAP + DRAW
// =================================================================
function initMap() {
  map = L.map('map', { zoomControl: true, minZoom: 3 }).setView(CAMPUS_CENTER, 17);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  // Faint marker on the SSIPMT test bbox so it's always easy to find
  L.rectangle([[CAMPUS_BBOX[1], CAMPUS_BBOX[0]], [CAMPUS_BBOX[3], CAMPUS_BBOX[2]]], {
    color: '#8695B5', weight: 1, dashArray: '4 4', fill: false, interactive: false,
  }).addTo(map).bindTooltip('SSIPMT test area', { permanent: false, direction: 'top' });

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
      polygon: false, polyline: false, circle: false, circlemarker: false, marker: false,
      rectangle: {
        shapeOptions: { color: '#F0A93B', weight: 2, fillOpacity: 0.08 },
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
      min_lon: b.getWest(), min_lat: b.getSouth(),
      max_lon: b.getEast(), max_lat: b.getNorth(),
    };
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
      selectedBbox = {
        min_lon: b.getWest(), min_lat: b.getSouth(),
        max_lon: b.getEast(), max_lat: b.getNorth(),
      };
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

// =================================================================
// DETECT
// =================================================================
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
    // Backend already differentiates: 503 tunnel down, 504 timeout,
    // 422 no imagery for this bbox, 500 unexpected — err.message carries
    // the exact Hinglish detail from satellite.py's exception handlers.
    showToast(err.message, 'error');
  } finally {
    document.getElementById('loadingOverlay').classList.add('hidden');
    setDetectEnabled(true);
  }
}

// =================================================================
// RESULTS LIST + MAP RENDERING
// =================================================================
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
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(feature.properties.ulpin, { sticky: true });
    },
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

// =================================================================
// SAVE TO REGISTRY
// =================================================================
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
    // In demo mode without Postgres configured, this will fail — surface
    // that clearly instead of a silent no-op, so it's obvious DB setup
    // is the next step rather than a bug.
    showToast(`Save failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Save to registry';
  }
}

// =================================================================
// INIT
// =================================================================
(async function init() {
  if (!authToken) return;
  try {
    currentUser = await apiFetch('/auth/me');
    localStorage.setItem('bhudrishti_user', JSON.stringify(currentUser));
    enterDashboard();
  } catch (_) {
    handleLogout();
  }
})();