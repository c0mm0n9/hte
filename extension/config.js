/**
 * Extension config. In production, GATEWAY_BASE_URL should point to your FastAPI gateway.
 */
const CONFIG = {
  GATEWAY_BASE_URL: 'http://localhost:8000',
  REPORT_ENDPOINT: '/v1/safety/report',
  SEND_DEBOUNCE_MS: 2000,
  MAX_PAYLOAD_SIZE: 64 * 1024,
};

// Export for use in background (service worker); content scripts use via global if needed.
if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_CONFIG = CONFIG;
}
