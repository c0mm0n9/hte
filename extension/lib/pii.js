/**
 * PII detection and masking. Replaces with NAME1, ADDRESS1, EMAIL1, etc.
 * Used only locally; masked content is safe to send to gateway.
 */
const PII_PATTERNS = [
  { name: 'email', regex: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, placeholder: 'EMAIL' },
  { name: 'phone', regex: /(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}([-.\s]?\d{2,4})?/g, placeholder: 'PHONE' },
  { name: 'ssn', regex: /\b\d{3}-\d{2}-\d{4}\b/g, placeholder: 'SSN' },
  { name: 'credit_card', regex: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g, placeholder: 'CARD' },
  { name: 'address_like', regex: /\b\d{1,6}\s+[\w\s]{3,40}(street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|blvd)\b/gi, placeholder: 'ADDRESS' },
  // Simple name-like: two or more consecutive capitalized words (e.g. "John Smith", "Dr. Jane Doe")
  { name: 'name', regex: /\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g, placeholder: 'NAME' },
];

/**
 * Mask PII in text. Replaces with NAME1, ADDRESS1, EMAIL1, etc. (numbered per type).
 * Returns { masked: string, detectedTypes: string[] }.
 */
function maskPII(text) {
  if (!text || typeof text !== 'string') {
    return { masked: '', detectedTypes: [] };
  }
  let masked = text;
  const detectedTypes = new Set();

  for (const { name, regex, placeholder } of PII_PATTERNS) {
    let counter = 0;
    masked = masked.replace(new RegExp(regex.source, regex.flags), () => {
      detectedTypes.add(name);
      counter += 1;
      return placeholder + counter;
    });
  }

  return {
    masked,
    detectedTypes: [...detectedTypes],
  };
}

/** Legacy: same as maskPII but returns redacted/detectedTypes keys. */
function redactPII(text) {
  const { masked, detectedTypes } = maskPII(text);
  return { redacted: masked, detectedTypes };
}

function hasPII(text) {
  if (!text || typeof text !== 'string') return false;
  for (const { regex } of PII_PATTERNS) {
    const re = new RegExp(regex.source, regex.flags);
    if (re.test(text)) return true;
  }
  return false;
}

if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_PII = { maskPII, redactPII, hasPII, PII_PATTERNS };
}
