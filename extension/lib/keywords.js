/**
 * Keyword lists by safety category. All matching is case-insensitive.
 * Expand or load from remote (e.g. parent settings) later.
 */
const KEYWORD_CATEGORIES = {
  violence: [
    'kill', 'hurt', 'weapon', 'gun', 'blood', 'attack', 'fight',
  ],
  bullying: [
    'hate you', 'ugly', 'stupid', 'loser', 'nobody likes you', 'kill yourself', 'kys',
  ],
  adult: [
    'nsfw', 'adult content', 'explicit',
  ],
  self_harm: [
    'cut myself', 'suicide', 'end my life', 'self harm',
  ],
};

function buildKeywordLookup() {
  const byCategory = {};
  const lowerWords = new Set();
  for (const [category, words] of Object.entries(KEYWORD_CATEGORIES)) {
    byCategory[category] = words.map((w) => w.toLowerCase());
    byCategory[category].forEach((w) => lowerWords.add(w));
  }
  return { byCategory, allLower: [...lowerWords] };
}

const { byCategory } = buildKeywordLookup();

/**
 * Scan text for keywords. Returns { matchedCategories: string[], countByCategory: Record<string, number> }.
 * Does not return the raw matched words (to avoid sending sensitive phrases).
 */
function detectKeywords(text) {
  if (!text || typeof text !== 'string') {
    return { matchedCategories: [], countByCategory: {} };
  }
  const normalized = text.toLowerCase();
  const countByCategory = {};
  const matchedCategories = new Set();

  for (const [category, words] of Object.entries(byCategory)) {
    let count = 0;
    for (const word of words) {
      const re = new RegExp(escapeRegex(word), 'gi');
      const matches = normalized.match(re);
      if (matches && matches.length) {
        count += matches.length;
        matchedCategories.add(category);
      }
    }
    if (count > 0) countByCategory[category] = count;
  }

  return {
    matchedCategories: [...matchedCategories],
    countByCategory,
  };
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Export for content script / processor
if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_KEYWORDS = { detectKeywords, KEYWORD_CATEGORIES };
}
