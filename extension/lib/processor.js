/**
 * Local processor: runs keyword detection and PII redaction on page text.
 * Returns only data safe to send (no PII).
 */
function processPageText(text) {
  if (!text || typeof text !== 'string') return null;

  const keywordDetector = globalThis.KIDS_SAFETY_KEYWORDS?.detectKeywords;
  const pii = globalThis.KIDS_SAFETY_PII;

  if (!keywordDetector || !pii) return null;

  const { redacted, detectedTypes } = pii.redactPII(text);
  const keywordResult = keywordDetector(redacted);

  if (detectedTypes.length > 0 && redacted.trim().length === 0) {
    return null;
  }

  return {
    keywords: {
      matchedCategories: keywordResult.matchedCategories,
      countByCategory: keywordResult.countByCategory,
    },
    piiDetected: detectedTypes.length > 0,
    piiTypes: detectedTypes,
  };
}

/**
 * Build payload for the gateway (no PII): url, domain, keywords, optional audio/video placeholders.
 */
function buildReportPayload(options) {
  const {
    url = '',
    domain = '',
    keywords = { matchedCategories: [], countByCategory: {} },
    audio = { has_audio: false },
    video = { has_video: false },
  } = options;

  return {
    ts: new Date().toISOString(),
    url: url.replace(/^(https?:\/\/[^/]+).*/, '$1'),
    domain: domain || (url ? new URL(url).hostname : ''),
    keywords,
    audio,
    video,
  };
}

if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_PROCESSOR = { processPageText, buildReportPayload };
}
