const GATEWAY_BASE_URL = 'http://localhost:8000';
const VALIDATE_URL = GATEWAY_BASE_URL + '/v1/auth/validate';
const STORAGE_KEY = 'kidsSafetyApiKey';
const STORAGE_MODE = 'kidsSafetyMode';
const STORAGE_OLLAMA_URL = 'kidsSafetyOllamaUrl';

const apiKeyInput = document.getElementById('api-key');
const saveBtn = document.getElementById('save-btn');
const clearBtn = document.getElementById('clear-btn');
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
  if (k.endsWith('-agent') || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(k)) return 'agent';
  return null;
}

async function validateWithGateway(key) {
  const res = await fetch(VALIDATE_URL, {
    method: 'GET',
    headers: { 'X-API-Key': key.trim() },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.mode || parseModeFromKey(key);
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

  try {
    const gatewayMode = await validateWithGateway(raw);
    if (gatewayMode !== null && gatewayMode !== mode) {
      showStatus('Gateway returned mode "' + gatewayMode + '". Using that.', false);
    }
    const finalMode = gatewayMode || mode;
    await chrome.storage.local.set({
      [STORAGE_KEY]: raw,
      [STORAGE_MODE]: finalMode,
    });
    showStatus('Saved. Mode: ' + finalMode + '. You can close this page and use the extension.', false);
    apiKeyInput.value = '';
  } catch (e) {
    showStatus('Could not reach gateway. Key saved for mode "' + mode + '". Try again later.', true);
    await chrome.storage.local.set({
      [STORAGE_KEY]: raw,
      [STORAGE_MODE]: mode,
    });
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
