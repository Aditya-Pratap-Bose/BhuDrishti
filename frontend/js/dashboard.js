// =================================================================
// js/dashboard.js — BhuDrishti Management Hub Controller
// Dynamic AOIs (Create/Delete), PostGIS Registry, Role Management.
// =================================================================

// GUARD: Token verification
if (typeof getAuthToken === 'function' && !getAuthToken()) {
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

let allRegistryParcels = [];

const DEFAULT_AOIS = [
  {
    id: 'raipur_ssipmt',
    name: 'Raipur SSIPMT Urban Zone',
    region: 'Raipur, CG',
    tag: 'Urban Cadastre',
    tagColor: 'scan',
    desc: 'High-res urban layout benchmark with roads and institutional cadastral plots.',
    feed: 'esri',
    feedLabel: 'Esri High-Res',
    isDefault: true,
  },
  {
    id: 'drone_ingest',
    name: 'Drone GeoTIFF Ingestion',
    region: 'Custom Ortho',
    tag: 'Drone Mission',
    tagColor: 'amber',
    desc: 'Direct client-side geotiff.js processing for sub-5cm centimeter accuracy flights.',
    feed: 'drone',
    feedLabel: 'Upload TIFF',
    isDefault: true,
  }
];

function handleLogout() {
  if (typeof clearSession === 'function') clearSession();
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

async function initDashboardHub() {
  await loadUserProfile();
  renderAOICards();
  await loadRegistryData();
}

function getStoredAOIs() {
  try {
    const raw = localStorage.getItem('bhudrishti_custom_aois');
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

function saveStoredAOIs(aois) {
  try {
    localStorage.setItem('bhudrishti_custom_aois', JSON.stringify(aois));
  } catch (_) {}
}

function getAllAOIs() {
  const custom = getStoredAOIs();
  return [...DEFAULT_AOIS, ...custom];
}

function renderAOICards() {
  const grid = document.getElementById('sessionsGrid');
  const countBadge = document.getElementById('aoiCountBadge');
  const activeSessionsEl = document.getElementById('statActiveSessions');
  if (!grid) return;

  const aois = getAllAOIs();

  if (countBadge) countBadge.textContent = `${aois.length} AOIs Ready`;
  if (activeSessionsEl) activeSessionsEl.textContent = aois.length;

  grid.innerHTML = aois.map((aoi, idx) => {
    const tagBg = aoi.tagColor === 'amber' 
      ? 'bg-amber-50 text-amber-800 border-amber-300'
      : aoi.tagColor === 'cyan'
      ? 'bg-cyan-50 text-cyan-800 border-cyan-300'
      : 'bg-emerald-50 text-emerald-800 border-emerald-300';

    const launchUrl = aoi.feed === 'drone' 
      ? 'workspace.html?source=drone' 
      : aoi.id === 'raipur_ssipmt'
      ? 'workspace.html?aoi=raipur_ssipmt'
      : `workspace.html?session=${encodeURIComponent(aoi.name)}&region=${encodeURIComponent(aoi.region)}&source=${aoi.feed}`;

    return `
      <div class="glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between group relative">
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-[9px] font-mono uppercase border px-2 py-0.5 rounded-full font-bold ${tagBg}">
              ${aoi.tag || 'Field Mission'}
            </span>
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-mono text-faint font-semibold">${aoi.region}</span>
              ${!aoi.isDefault ? `
                <button onclick="deleteCustomAOI('${aoi.id}', event)" title="Delete AOI" class="text-faint hover:text-red-600 p-1 rounded-lg hover:bg-red-50 transition">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              ` : ''}
            </div>
          </div>
          <h3 class="font-bold text-sm text-ink group-hover:text-emerald-700 transition">${aoi.name}</h3>
          <p class="text-xs text-faint line-clamp-2 leading-relaxed">${aoi.desc || 'Active survey zone.'}</p>
        </div>

        <div class="pt-3 border-t border-line flex items-center justify-between">
          <span class="text-[10px] font-mono text-faint font-medium">Feed: <b class="text-ink font-semibold">${aoi.feedLabel || aoi.feed}</b></span>
          <a href="${launchUrl}" class="text-xs font-bold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 transition">
            <span>Open Workspace</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        </div>
      </div>
    `;
  }).join('');
}

function deleteCustomAOI(id, event) {
  if (event) event.stopPropagation();
  if (!confirm('Are you sure you want to delete this Survey AOI?')) return;

  let custom = getStoredAOIs();
  custom = custom.filter(a => a.id !== id);
  saveStoredAOIs(custom);
  renderAOICards();
  showToast('Survey AOI removed.', 'info');
}

async function loadUserProfile() {
  const user = getCurrentUser();
  const labelEl = document.getElementById('userLabel');
  const roleEl = document.getElementById('statUserRole');
  const roleDescEl = document.getElementById('statRoleDesc');

  function applyUserData(u) {
    const roleStr = (u.role || 'Surveyor').toUpperCase();
    if (labelEl) {
      labelEl.textContent = `${u.full_name || u.email} (${roleStr})`;
    }
    if (roleEl) {
      roleEl.textContent = roleStr;
      roleEl.className = (u.role === 'admin' || u.role === 'tehsildar') ? 'text-2xl font-bold font-mono text-emerald-400' : 'text-2xl font-bold font-mono text-amber';
    }
    if (roleDescEl) {
      roleDescEl.textContent = (u.role === 'admin' || u.role === 'tehsildar')
        ? 'Full DB commit & deletion privileges'
        : 'Field workspace curation & export';
    }
  }

  if (user) {
    applyUserData(user);
  }

  try {
    const liveUser = await apiFetch('/auth/me');
    if (liveUser) {
      localStorage.setItem('bhudrishti_user', JSON.stringify(liveUser));
      applyUserData(liveUser);
    }
  } catch (_) {}
}

async function loadRegistryData() {
  const tbody = document.getElementById('registryTableBody');
  const countEl = document.getElementById('statDbParcels');

  try {
    const data = await apiFetch('/parcels?limit=500');
    allRegistryParcels = data.features || [];

    if (countEl) {
      countEl.textContent = allRegistryParcels.length;
    }

    renderRegistryTable(allRegistryParcels);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-red-400 font-body text-xs">Failed to load database records: ${err.message}</td></tr>`;
    }
  }
}

function formatUlpinDisplay(rawUlpin) {
  if (!rawUlpin) return '22-10-001-0000000';
  const clean = String(rawUlpin).replace(/[^A-Z0-9]/gi, '').toUpperCase();
  if (clean.length === 14) {
    return `${clean.substring(0, 2)}-${clean.substring(2, 4)}-${clean.substring(4, 7)}-${clean.substring(7, 14)}`;
  }
  if (rawUlpin.includes('-')) return rawUlpin.toUpperCase();
  return clean.substring(0, 14).toUpperCase();
}

function renderRegistryTable(parcels) {
  const tbody = document.getElementById('registryTableBody');
  if (!tbody) return;

  if (!parcels || !parcels.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-faint font-body text-xs">No registered land parcels found in PostGIS database. Use the Working Area to extract and commit parcels.</td></tr>`;
    return;
  }

  const currentUser = getCurrentUser() || {};
  const canDelete = currentUser.role === 'admin' || currentUser.role === 'tehsildar';

  tbody.innerHTML = parcels.map((p, idx) => {
    const props = p.properties || {};
    const area = props.area_sqm ? Number(props.area_sqm) : 0;
    const areaHa = (area / 10000).toFixed(3);
    const dateStr = props.created_at ? new Date(props.created_at).toLocaleDateString() : 'N/A';
    const displayUlpin = formatUlpinDisplay(props.ulpin);

    return `
      <tr class="hover:bg-slate-50 transition group">
        <td class="py-3 px-3.5">
          <span class="text-emerald-700 font-bold hover:underline cursor-pointer tracking-wider" title="${props.ulpin}">${displayUlpin}</span>
        </td>
        <td class="py-3 px-3.5 font-body">
          <span class="px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-[10px] text-slate-700 font-medium">${props.land_use || 'Unclassified'}</span>
        </td>
        <td class="py-3 px-3.5">
          <span class="text-ink font-semibold">${area.toFixed(1)} m²</span>
          <span class="text-faint text-[10px]">(${areaHa} Ha)</span>
        </td>
        <td class="py-3 px-3.5 text-faint font-medium">${props.perimeter_m ? Number(props.perimeter_m).toFixed(1) : 0} m</td>
        <td class="py-3 px-3.5 font-body text-ink font-medium">${props.owner_name || '<span class="text-faint italic font-normal">Unregistered</span>'}</td>
        <td class="py-3 px-3.5 text-faint font-body text-[10px]">${dateStr}</td>
        <td class="py-3 px-3.5 text-right">
          <div class="flex items-center justify-end gap-1.5 font-body">
            <button onclick="handleExportCert(${idx})" title="Export PDF Certificate" class="bg-surface hover:bg-surface2 border border-line px-2.5 py-1 rounded-lg text-ink font-semibold text-[10px] transition shadow-sm">
              PDF
            </button>
            ${canDelete ? `
              <button onclick="handleDeleteRegistryParcel('${props.id}')" title="Delete from Database" class="bg-red-50 hover:bg-red-100 border border-red-200 px-2.5 py-1 rounded-lg text-red-600 font-semibold text-[10px] transition shadow-sm">
                Delete
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function filterRegistryTable() {
  const query = (document.getElementById('registrySearch').value || '').toLowerCase().trim();
  if (!query) {
    renderRegistryTable(allRegistryParcels);
    return;
  }

  const filtered = allRegistryParcels.filter(f => {
    const p = f.properties || {};
    return (p.ulpin && p.ulpin.toLowerCase().includes(query)) ||
           (p.owner_name && p.owner_name.toLowerCase().includes(query)) ||
           (p.land_use && p.land_use.toLowerCase().includes(query));
  });

  renderRegistryTable(filtered);
}

function handleExportCert(idx) {
  const feature = allRegistryParcels[idx];
  if (feature && typeof exportParcelPDF === 'function') {
    exportParcelPDF(feature);
  }
}

async function handleDeleteRegistryParcel(parcelId) {
  if (!confirm('Are you sure you want to delete this parcel from the PostGIS database?')) return;

  try {
    await apiFetch(`/parcels/${parcelId}`, { method: 'DELETE' });
    showToast('Parcel deleted from database.', 'success');
    await loadRegistryData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Modal logic & Survey creation
function openNewSessionModal() {
  document.getElementById('newSessionModal').classList.remove('hidden');
}

function closeNewSessionModal() {
  document.getElementById('newSessionModal').classList.add('hidden');
}

function handleCreateSession(e) {
  e.preventDefault();
  const name = document.getElementById('newSessionName').value.trim();
  const region = document.getElementById('newSessionRegion').value.trim();
  const feed = document.getElementById('newSessionFeed').value;
  const desc = document.getElementById('newSessionDesc') ? document.getElementById('newSessionDesc').value.trim() : '';

  if (name) {
    const feedLabels = {
      'esri': 'Esri High-Res',
      'drone': 'Upload TIFF',
      'sentinel': 'Sentinel-2 STAC',
    };

    const newAOI = {
      id: 'aoi_' + Date.now(),
      name: name,
      region: region || 'Field Survey',
      tag: feed === 'drone' ? 'Drone Mission' : 'Custom AOI',
      tagColor: feed === 'drone' ? 'amber' : 'cyan',
      desc: desc || `Field survey zone in ${region}.`,
      feed: feed,
      feedLabel: feedLabels[feed] || feed,
      isDefault: false,
    };

    const currentCustom = getStoredAOIs();
    currentCustom.unshift(newAOI);
    saveStoredAOIs(currentCustom);

    const params = new URLSearchParams({ session: name, region, source: feed });
    window.location.href = `workspace.html?${params.toString()}`;
  }
}

window.addEventListener('load', () => {
  initDashboardHub();
});

