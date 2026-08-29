// =================================================================
// js/api.js — Shared fetch helper + session storage + toasts.
// Dono pages (login.html, dashboard.html) ye file load karti hain —
// isliye API/token logic sirf EK jagah maintain hoti hai.
// =================================================================

let API_BASE_URL = localStorage.getItem('bhudrishti_api_base') ||
  ((window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000'))
    ? 'http://127.0.0.1:8000/api/v1'
    : `${window.location.origin}/api/v1`);

function getAuthToken() {
  return localStorage.getItem('bhudrishti_token');
}

function getCurrentUser() {
  return JSON.parse(localStorage.getItem('bhudrishti_user') || 'null');
}

function saveSession(tokenResponse) {
  localStorage.setItem('bhudrishti_token', tokenResponse.access_token);
  localStorage.setItem('bhudrishti_user', JSON.stringify(tokenResponse.user));
}

function clearSession() {
  localStorage.removeItem('bhudrishti_token');
  localStorage.removeItem('bhudrishti_user');
}

async function apiFetch(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = { ...(options.headers || {}) };
  
  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (networkErr) {
    throw new Error('Backend tak connect nahi ho sake. Make sure FastAPI server (http://127.0.0.1:8000) chal raha hai.');
  }

  let data = null;
  try { 
    data = await res.json(); 
  } catch (_) { /* no body or non-JSON */ }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (HTTP ${res.status})`;
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

// saved kind: 'error' | 'info' | 'success'
function showToast(message, kind = 'error') {
  const box = document.getElementById('toastBox');
  if (!box) return;
  const colors = {
    error: 'border-red-900/50 bg-red-950/90 text-red-200',
    info: 'border-scan/40 bg-surface/95 text-scan',
    success: 'border-emerald-500/40 bg-surface/95 text-emerald-400',
  };
  const el = document.createElement('div');
  el.className = `fade-in mb-2 text-xs rounded-xl border ${colors[kind] || colors.error} px-4 py-3 shadow-2xl backdrop-blur-md flex items-center justify-between gap-3`;
  el.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" class="text-faint hover:text-ink text-xs font-mono">&times;</button>`;
  box.appendChild(el);
  setTimeout(() => { if (el.parentElement) el.remove(); }, 6000);
}