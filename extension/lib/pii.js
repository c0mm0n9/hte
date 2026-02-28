/**
 * PII detection and redaction. Used only locally; redacted content must never be sent.
 */
const PII_PATTERNS = [
  {
    name: 'email',
    regex: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    replace: '[EMAIL]',
  },
  {
    name: 'phone',
    regex: /(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}([-.\s]?\d{2,4})?/g,
    replace: '[PHONE]',
  },
  {
    name: 'ssn',
    regex: /\b\d{3}-\d{2}-\d{4}\b/g,
    replace: '[SSN]',
  },
  {
    name: 'credit_card',
    regex: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g,
    replace: '[CARD]',
  },
  // Simple address-like (number + street name) – can be expanded
  {
    name: 'address_like',
    regex: /\b\d{1,6}\s+[\w\s]{3,40}(street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|blvd)\b/gi,
    replace: '[ADDRESS]',
  },
];

/**
 * Redact PII from text. Returns { redacted: string, detectedTypes: string[] }.
 */
function redactPII(text) {
  if (!text || typeof text !== 'string') {
    return { redacted: '', detectedTypes: [] };
  }
  let redacted = text;
  const detectedTypes = new Set();

  for (const { name, regex, replace: repl } of PII_PATTERNS) {
    const re = new RegExp(regex.source, regex.flags);
    if (re.test(redacted)) {
      detectedTypes.add(name);
    }
    redacted = redacted.replace(new RegExp(regex.source, regex.flags), repl);
  }

  return {
    redacted,
    detectedTypes: [...detectedTypes],
  };
}

/**
 * Check if text contains PII (for deciding whether to skip sending).
 */
function hasPII(text) {
  if (!text || typeof text !== 'string') return false;
  for (const { regex } of PII_PATTERNS) {
    if (regex.test(text)) return true;
  }
  return false;
}

if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_PII = { redactPII, hasPII, PII_PATTERNS };
}
