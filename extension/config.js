/**
 * Extension config. Portal = Django backend (validate, record-visit). Gateway = agent_gateway (analyze).
 * Use 127.0.0.1 so Django is reachable when localhost resolves to IPv6 (::1).
 */
const CONFIG = {
  PORTAL_API_BASE: 'http://127.0.0.1:8000',
  GATEWAY_BASE_URL: 'http://127.0.0.1:8003',
};

// Export for use in background (service worker); content scripts use via global if needed.
if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_CONFIG = CONFIG;
}
