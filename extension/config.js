/**
 * Extension config. For Docker: agent_gateway is on port 8003.
 */
const CONFIG = {
  GATEWAY_BASE_URL: 'http://localhost:8003',
};

// Export for use in background (service worker); content scripts use via global if needed.
if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_CONFIG = CONFIG;
}
