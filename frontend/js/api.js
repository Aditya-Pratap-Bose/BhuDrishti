// =================================================================
// js/api.js — Shared fetch helper + session storage + toasts.
// Dono pages (login.html, dashboard.html) ye file load karti hain —
// isliye API/token logic sirf EK jagah maintain hoti hai.
// =================================================================

let API_BASE_URL = localStorage.getItem('bhudrishti_api_base') || `${window.location.origin}/api/v1`;

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
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = getAuthToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

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

// saved kind: 'error' | 'info' | 'success'
function showToast(message, kind = 'error') {
  const box = document.getElementById('toastBox');
  if (!box) return; // login.html me toast box nahi hai — chup-chaap skip
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