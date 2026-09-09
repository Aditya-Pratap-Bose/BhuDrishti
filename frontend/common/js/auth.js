// =================================================================
// Shared authentication helpers used by login, portal, V1 and V2.
// =================================================================

function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('loginForm').classList.toggle('hidden', !isLogin);
  document.getElementById('registerForm').classList.toggle('hidden', isLogin);
  document.getElementById('tabLogin').className = `flex-1 py-1.5 rounded-lg text-sm font-medium transition ${isLogin ? 'bg-line text-ink shadow-sm' : 'text-faint hover:text-ink'}`;
  document.getElementById('tabRegister').className = `flex-1 py-1.5 rounded-lg text-sm font-medium transition ${!isLogin ? 'bg-line text-ink shadow-sm' : 'text-faint hover:text-ink'}`;
  hideAuthError();
}
function showAuthError(msg) {
  const box = document.getElementById('authError');
  box.textContent = msg;
  box.classList.remove('hidden');
}
function hideAuthError() { document.getElementById('authError').classList.add('hidden'); }

function getPortalUrl() {
  return window.location.pathname.includes('/auth/') ? '../portal/index.html' : '/portal/';
}

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
    window.location.href = getPortalUrl();
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
    window.location.href = getPortalUrl();
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Create account';
  }
}

// PAGE LOAD: an existing valid session belongs at the version selector.
(async function initLoginPage() {
  if (!document.getElementById('loginForm')) return;
  if (!getAuthToken()) return;
  try {
    const user = await apiFetch('/auth/me');
    localStorage.setItem('bhudrishti_user', JSON.stringify(user));
    window.location.href = getPortalUrl();
  } catch (_) {
    clearSession();
  }
})();