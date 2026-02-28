const CONFIG = {
  GATEWAY_BASE_URL: 'http://localhost:8000',
};

const DEBUG = true;
function log(...args) {
  if (DEBUG) console.log('[Kids Safety BG]', ...args);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'PAGE_SIGNAL' && message.payload) {
    log('PAGE_SIGNAL received (report posting disabled)', message.payload?.url);
    sendResponse({ ok: true });
  }
  return true;
});

log('service worker started');
