// =================================================================
// js/auth.js — sirf login.html ke liye. Login/Register/API-settings.
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
    saveSession(data);
    window.location.href = '/dashboard'; // MPA hone ki wajah se ab yahan poora navigate karte hain
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
    saveSession(data);
    window.location.href = '/dashboard';
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Create account';
  }
}

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
    hideAuthError();
    document.getElementById('apiSettingsBox').classList.add('hidden');
  }
}

// PAGE LOAD: agar valid token pehle se hai, login form dikhane ki
// zaroorat nahi — seedha dashboard bhej do.
(async function initLoginPage() {
  if (!getAuthToken()) return;
  try {
    const user = await apiFetch('/auth/me');
    localStorage.setItem('bhudrishti_user', JSON.stringify(user));
    window.location.href = '/dashboard';
  } catch (_) {
    clearSession(); // token expire ho chuka — login form yahin rehne do
  }
})();