const GATEWAY_BASE_URL = 'http://localhost:8000';
const AGENT_CHAT_URL = GATEWAY_BASE_URL + '/v1/agent/chat';

const pageUrlEl = document.getElementById('page-url');
const messageEl = document.getElementById('message');
const sendBtn = document.getElementById('send-btn');
const replyEl = document.getElementById('reply');

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

async function sendToAgent() {
  const url = await getCurrentTabUrl();
  const message = (messageEl.value || '').trim();
  if (!message) {
    setReply('Please enter a question.', true);
    return;
  }

  sendBtn.disabled = true;
  setReply('Asking the agent…');

  try {
    const res = await fetch(AGENT_CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        message: message,
        device_token: null,
        media_urls: null,
      }),
    });

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

sendBtn.addEventListener('click', sendToAgent);

getCurrentTabUrl().then((url) => {
  pageUrlEl.textContent = url || '—';
});
