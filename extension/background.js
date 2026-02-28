const CONFIG = {
  GATEWAY_BASE_URL: 'http://localhost:8000',
  REPORT_ENDPOINT: '/v1/safety/report',
  SEND_DEBOUNCE_MS: 2000,
  MAX_PAYLOAD_SIZE: 64 * 1024,
};

let reportQueue = [];
let sendTimer = null;

function flushReports() {
  if (reportQueue.length === 0) return;
  const payloads = reportQueue.slice();
  reportQueue = [];
  sendTimer = null;

  const url = CONFIG.GATEWAY_BASE_URL.replace(/\/$/, '') + CONFIG.REPORT_ENDPOINT;
  const body = JSON.stringify({ reports: payloads });

  if (body.length > CONFIG.MAX_PAYLOAD_SIZE) {
    const chunk = payloads.slice(0, 1);
    reportQueue = payloads.slice(1);
    scheduleFlush();
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reports: chunk }),
    }).catch(() => {});
    return;
  }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  }).catch(() => {});
}

function scheduleFlush() {
  if (sendTimer) return;
  sendTimer = setTimeout(() => {
    sendTimer = null;
    flushReports();
  }, CONFIG.SEND_DEBOUNCE_MS);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'PAGE_SIGNAL' && message.payload) {
    reportQueue.push(message.payload);
    scheduleFlush();
    sendResponse({ ok: true });
  }
  return true;
});
