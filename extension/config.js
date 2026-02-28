/**
 * Extension config. Portal = Django backend (validate, record-visit). Gateway = agent_gateway (analyze).
 */
const CONFIG = {
  PORTAL_API_BASE: 'http://localhost:8000',
  GATEWAY_BASE_URL: 'http://localhost:8003',
};

// Export for use in background (service worker); content scripts use via global if needed.
if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_CONFIG = CONFIG;
}
