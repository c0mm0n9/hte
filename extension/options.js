const PORTAL_API_BASE = (typeof globalThis !== 'undefined' && globalThis.KIDS_SAFETY_CONFIG?.PORTAL_API_BASE) || 'http://127.0.0.1:8000';
const VALIDATE_URL = PORTAL_API_BASE.replace(/\/$/, '') + '/api/portal/validate/';
const STORAGE_KEY = 'kidsSafetyApiKey';
if (typeof console !== 'undefined' && console.log) {
  console.log('[sIsland Options] Validate URL:', VALIDATE_URL);
}
const STORAGE_MODE = 'kidsSafetyMode';

const apiKeyInput = document.getElementById('api-key');
const saveBtn = document.getElementById('save-btn');
const clearBtn = document.getElementById('clear-btn');
const statusEl = document.getElementById('status');

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = 'status ' + (isError ? 'error' : 'success');
  statusEl.style.display = 'block';
}

function hideStatus() {
  statusEl.style.display = 'none';
}

function parseModeFromKey(key) {
  if (!key || typeof key !== 'string') return null;
  const k = key.trim().toLowerCase();
  if (k.endsWith('-control')) return 'control';
  if (k.endsWith('-agentic') || k.endsWith('-agent') || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(k)) return 'agent';
  return null;
}

async function validateWithPortal(key) {
  const url = VALIDATE_URL + '?api_key=' + encodeURIComponent(key.trim());
  if (typeof console !== 'undefined' && console.log) {
    console.log('[sIsland Options] Validating key with backend:', url.replace(/api_key=[^&]+/, 'api_key=***'));
  }
  const res = await fetch(url);
  if (typeof console !== 'undefined' && console.log) {
    console.log('[sIsland Options] Validate response:', res.status, res.statusText);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { error: (data.error || res.statusText || 'Request failed') };
  }
  if (!data.valid || !data.mode) {
    return { error: (data.error || 'Invalid response from server') };
  }
  return data.mode === 'agentic' ? 'agent' : data.mode;
}

saveBtn.addEventListener('click', async () => {
  const raw = (apiKeyInput.value || '').trim();
  if (!raw) {
    showStatus('Please enter an API key.', true);
    return;
  }

  const mode = parseModeFromKey(raw);
  if (!mode) {
    showStatus('Invalid format. Use UUID or UUID-agent or UUID-control.', true);
    return;
  }

  saveBtn.disabled = true;
  hideStatus();
  showStatus('Validating key with backend…', false);

  try {
    const portalResult = await validateWithPortal(raw);
    if (typeof portalResult === 'object' && portalResult !== null && portalResult.error) {
      showStatus(portalResult.error, true);
      saveBtn.disabled = false;
      return;
    }
    if (portalResult === null) {
      showStatus('Key not found in portal or backend unreachable. Only keys that exist in the portal (PostgreSQL) can be used.', true);
      saveBtn.disabled = false;
      return;
    }
    const finalMode = portalResult !== mode ? portalResult : mode;
    await chrome.storage.local.set({
      [STORAGE_KEY]: raw,
      [STORAGE_MODE]: finalMode,
    });
    showStatus('Saved. Mode: ' + finalMode + '. You can close this page and use the extension.', false);
    apiKeyInput.value = '';
  } catch (e) {
    if (typeof console !== 'undefined' && console.error) {
      console.error('[sIsland Options] Validate request failed:', e);
    }
    showStatus('Could not reach portal (' + (e && e.message ? e.message : 'network error') + ').', true);
  } finally {
    saveBtn.disabled = false;
  }
});

clearBtn.addEventListener('click', async () => {
  await chrome.storage.local.remove([STORAGE_KEY, STORAGE_MODE]);
  apiKeyInput.value = '';
  hideStatus();
  showStatus('API key cleared. Enter a new key to use the extension.', false);
});

chrome.storage.local.get([STORAGE_KEY, STORAGE_MODE], (data) => {
  if (data[STORAGE_KEY]) {
    apiKeyInput.placeholder = 'Key saved. Enter a new key to replace.';
  }
});
