const PORTAL_API_BASE = (typeof globalThis !== 'undefined' && globalThis.KIDS_SAFETY_CONFIG?.PORTAL_API_BASE) || 'http://localhost:8000';
const VALIDATE_URL = PORTAL_API_BASE.replace(/\/$/, '') + '/api/portal/validate/';
const STORAGE_KEY = 'kidsSafetyApiKey';
if (typeof console !== 'undefined' && console.log) {
  console.log('[Kids Safety Options] Validate URL:', VALIDATE_URL);
}
const STORAGE_MODE = 'kidsSafetyMode';
const STORAGE_OLLAMA_URL = 'kidsSafetyOllamaUrl';

const apiKeyInput = document.getElementById('api-key');
const saveBtn = document.getElementById('save-btn');
const clearBtn = document.getElementById('clear-btn');
const currentKeyInput = document.getElementById('current-key');
const newKeyInput = document.getElementById('new-key');
const changeKeyBtn = document.getElementById('change-key-btn');
const ollamaUrlInput = document.getElementById('ollama-url');
const saveOllamaBtn = document.getElementById('save-ollama-btn');
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
    console.log('[Kids Safety Options] Validating key with backend:', url.replace(/api_key=[^&]+/, 'api_key=***'));
  }
  const res = await fetch(url);
  if (typeof console !== 'undefined' && console.log) {
    console.log('[Kids Safety Options] Validate response:', res.status, res.statusText);
  }
  if (!res.ok) return null;
  const data = await res.json();
  if (!data.valid || !data.mode) return null;
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
    const portalMode = await validateWithPortal(raw);
    if (portalMode === null) {
      showStatus('Key not found in portal or backend unreachable. Only keys that exist in the portal (PostgreSQL) can be used.', true);
      saveBtn.disabled = false;
      return;
    }
    const finalMode = portalMode !== mode ? portalMode : mode;
    await chrome.storage.local.set({
      [STORAGE_KEY]: raw,
      [STORAGE_MODE]: finalMode,
    });
    showStatus('Saved. Mode: ' + finalMode + '. You can close this page and use the extension.', false);
    apiKeyInput.value = '';
  } catch (e) {
    if (typeof console !== 'undefined' && console.error) {
      console.error('[Kids Safety Options] Validate request failed:', e);
    }
    showStatus('Could not reach portal (' + (e && e.message ? e.message : 'network error') + ').', true);
  } finally {
    saveBtn.disabled = false;
  }
});

changeKeyBtn.addEventListener('click', async () => {
  const currentRaw = (currentKeyInput.value || '').trim();
  const newRaw = (newKeyInput.value || '').trim();
  if (!currentRaw || !newRaw) {
    showStatus('Enter both current and new API key.', true);
    return;
  }
  if (currentRaw === newRaw) {
    showStatus('New key must be different from current key.', true);
    return;
  }

  const stored = await new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY], (data) => resolve(data[STORAGE_KEY] || ''));
  });
  if (!stored) {
    showStatus('No API key is set. Use the form above to save a key first.', true);
    return;
  }
  if (currentRaw !== stored) {
    showStatus('Current API key does not match the saved key.', true);
    return;
  }

  const newMode = parseModeFromKey(newRaw);
  if (!newMode) {
    showStatus('New key has invalid format. Use UUID-agent or UUID-control.', true);
    return;
  }

  changeKeyBtn.disabled = true;
  hideStatus();
  showStatus('Validating new key with backend…', false);

  try {
    const portalMode = await validateWithPortal(newRaw);
    if (portalMode === null) {
      showStatus('New key not found in portal or backend unreachable. Only keys that exist in the portal can be used.', true);
      changeKeyBtn.disabled = false;
      return;
    }
    const finalMode = portalMode === 'agentic' ? 'agent' : portalMode;
    await chrome.storage.local.set({
      [STORAGE_KEY]: newRaw,
      [STORAGE_MODE]: finalMode,
    });
    showStatus('API key changed. Mode: ' + finalMode + '.', false);
    currentKeyInput.value = '';
    newKeyInput.value = '';
  } catch (e) {
    if (typeof console !== 'undefined' && console.error) {
      console.error('[Kids Safety Options] Change key failed:', e);
    }
    showStatus('Could not reach portal (' + (e && e.message ? e.message : 'network error') + ').', true);
  } finally {
    changeKeyBtn.disabled = false;
  }
});

clearBtn.addEventListener('click', async () => {
  await chrome.storage.local.remove([STORAGE_KEY, STORAGE_MODE]);
  apiKeyInput.value = '';
  hideStatus();
  showStatus('API key cleared. Enter a new key to use the extension.', false);
});

saveOllamaBtn.addEventListener('click', async () => {
  const url = (ollamaUrlInput.value || '').trim();
  await chrome.storage.local.set({ [STORAGE_OLLAMA_URL]: url || null });
  showStatus(url ? 'Ollama URL saved.' : 'Ollama URL cleared.', false);
});

chrome.storage.local.get([STORAGE_KEY, STORAGE_MODE, STORAGE_OLLAMA_URL], (data) => {
  if (data[STORAGE_KEY]) {
    apiKeyInput.placeholder = 'Key saved. Enter a new key to replace.';
  }
  if (data[STORAGE_OLLAMA_URL]) {
    ollamaUrlInput.value = data[STORAGE_OLLAMA_URL];
  }
});
