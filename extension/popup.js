const GATEWAY_BASE_URL = 'http://localhost:8000';
const AGENT_CHAT_URL = GATEWAY_BASE_URL + '/v1/agent/chat';
const STORAGE_KEY = 'kidsSafetyApiKey';
const STORAGE_MODE = 'kidsSafetyMode';
const STORAGE_OLLAMA_URL = 'kidsSafetyOllamaUrl';

const setupPanel = document.getElementById('setup-panel');
const controlPanel = document.getElementById('control-panel');
const agentPanel = document.getElementById('agent-panel');
const openOptionsLink = document.getElementById('open-options');
const pageUrlEl = document.getElementById('page-url');
const messageEl = document.getElementById('message');
const sendBtn = document.getElementById('send-btn');
const replyEl = document.getElementById('reply');

function showPanel(panel) {
  setupPanel.classList.remove('active');
  controlPanel.classList.remove('active');
  agentPanel.classList.remove('active');
  panel.classList.add('active');
}

async function getStoredKeyAndMode() {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY, STORAGE_MODE], (data) => {
      resolve({ apiKey: data[STORAGE_KEY] || null, mode: data[STORAGE_MODE] || null });
    });
  });
}

async function getCurrentTabUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.url || '';
}

function setReply(text, isError = false) {
  const raw = text || 'No reply.';
  replyEl.classList.toggle('empty', !text);
  replyEl.classList.toggle('error', isError);
  replyEl.innerHTML = raw
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

async function getPageContentFromTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return { text: '', mediaUrls: [] };
  try {
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_CONTENT' });
    return result || { text: '', mediaUrls: [] };
  } catch (_) {
    return { text: '', mediaUrls: [] };
  }
}

async function sendToAgent() {
  const { apiKey } = await getStoredKeyAndMode();
  if (!apiKey) {
    setReply('API key missing. Open options to enter your key.', true);
    return;
  }

  const url = await getCurrentTabUrl();
  const message = (messageEl.value || '').trim();
  if (!message) {
    setReply('Please enter a question.', true);
    return;
  }

  sendBtn.disabled = true;
  setReply('Reading page content…');

  let extractedContent = '';
  let mediaUrls = [];

  try {
    const pageContent = await getPageContentFromTab();
    const pageText = (pageContent.text || '').trim();
    mediaUrls = pageContent.mediaUrls || [];

    setReply('Extracting important content…');
    const ollamaUrl = await new Promise(function (resolve) {
      chrome.storage.local.get([STORAGE_OLLAMA_URL], function (data) {
        resolve(data[STORAGE_OLLAMA_URL] || null);
      });
    });
    if (globalThis.KIDS_SAFETY_LLM && globalThis.KIDS_SAFETY_LLM.extractImportantContent) {
      extractedContent = await globalThis.KIDS_SAFETY_LLM.extractImportantContent(pageText, ollamaUrl);
    } else {
      extractedContent = pageText.slice(0, 12000);
    }

    setReply('Asking the agent…');

    const res = await fetch(AGENT_CHAT_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({
        url: url,
        message: message,
        device_token: null,
        media_urls: mediaUrls.length ? mediaUrls : null,
        extracted_content: extractedContent || null,
      }),
    });

    if (res.status === 401 || res.status === 403) {
      const data = await res.json().catch(() => ({}));
      setReply(data.detail || 'Invalid or wrong-mode API key. Check options.', true);
      return;
    }

    if (!res.ok) {
      const err = await res.text();
      setReply(`Request failed: ${res.status}. ${err}`, true);
      return;
    }

    const data = await res.json();
    setReply(data.reply || 'No reply from agent.');
  } catch (e) {
    setReply('Could not reach the agent. Is the gateway running at ' + GATEWAY_BASE_URL + '?', true);
  } finally {
    sendBtn.disabled = false;
  }
}

openOptionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

sendBtn.addEventListener('click', sendToAgent);

(async function init() {
  const { apiKey, mode } = await getStoredKeyAndMode();

  if (!apiKey) {
    showPanel(setupPanel);
    return;
  }

  if (mode === 'control') {
    showPanel(controlPanel);
    return;
  }

  showPanel(agentPanel);
  getCurrentTabUrl().then((url) => {
    pageUrlEl.textContent = url || '—';
  });
})();
