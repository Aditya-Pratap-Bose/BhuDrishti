// =================================================================
// js/dashboard.js — BhuDrishti Management Hub Controller
// Session Management, PostGIS Database Registry & Role Management.
// =================================================================

// GUARD: Token verification
if (typeof getAuthToken === 'function' && !getAuthToken()) {
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

let allRegistryParcels = [];

function handleLogout() {
  if (typeof clearSession === 'function') clearSession();
  window.location.href = window.location.pathname.endsWith('.html') ? 'login.html' : '/';
}

async function initDashboardHub() {
  await loadUserProfile();
  await loadRegistryData();
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
  if (!rawUlpin) return 'ULPIN-XXXX';
  const clean = rawUlpin.replace(/^(COLAB|LOCAL|SAVED)-/, '');
  const p1 = clean.substring(0, 4);
  const p2 = clean.substring(4, 8);
  return `ULPIN-${p1}-${p2}`.toUpperCase();
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
      <tr class="hover:bg-surface2/60 transition group">
        <td class="py-3 px-3">
          <span class="text-scan font-bold hover:underline cursor-pointer" title="${props.ulpin}">${displayUlpin}</span>
        </td>
        <td class="py-3 px-3 font-body">
          <span class="px-2 py-0.5 rounded-md bg-surface2 border border-line text-[10px] text-faint">${props.land_use || 'Unclassified'}</span>
        </td>
        <td class="py-3 px-3">
          <span class="text-ink font-semibold">${area.toFixed(1)} m²</span>
          <span class="text-faint text-[10px]">(${areaHa} Ha)</span>
        </td>
        <td class="py-3 px-3 text-faint">${props.perimeter_m ? Number(props.perimeter_m).toFixed(1) : 0} m</td>
        <td class="py-3 px-3 font-body text-ink">${props.owner_name || '<span class="text-faint italic">Unregistered</span>'}</td>
        <td class="py-3 px-3 text-faint font-body text-[10px]">${dateStr}</td>
        <td class="py-3 px-3 text-right">
          <div class="flex items-center justify-end gap-1.5 font-body">
            <button onclick="handleExportCert(${idx})" title="Export PDF Certificate" class="bg-surface2 hover:bg-line border border-line px-2 py-1 rounded-lg text-ink text-[10px] transition">
              PDF
            </button>
            ${canDelete ? `
              <button onclick="handleDeleteRegistryParcel('${props.id}')" title="Delete from Database" class="bg-surface2 hover:bg-red-950/40 border border-line hover:border-red-800/60 px-2 py-1 rounded-lg text-red-400 text-[10px] transition">
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

// Modal logic
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

  if (name) {
    const params = new URLSearchParams({ session: name, region, source: feed });
    window.location.href = `workspace.html?${params.toString()}`;
  }
}

window.addEventListener('load', () => {
  initDashboardHub();
});
