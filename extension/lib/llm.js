/**
 * Use an open-source LLM to extract important content from page text.
 * Supports: Ollama (local), or fallback to truncated text.
 */
const EXTRACT_PROMPT_PREFIX =
  'Extract and summarize the key facts, claims, and important information from this web page content for fact-checking and safety. Be concise (max 500 words).\n\nPage content:\n';
const MAX_DIRECT_LENGTH = 12000;

/**
 * Call Ollama /api/generate to get a summary. Returns extracted text or null on error.
 * @param {string} pageText - Full page text
 * @param {string} ollamaUrl - Base URL e.g. http://localhost:11434
 * @param {string} model - Model name (default llama3.2 or whatever is available)
 */
async function extractWithOllama(pageText, ollamaUrl, model) {
  const base = ollamaUrl.replace(/\/$/, '');
  const url = base + '/api/generate';
  const prompt = EXTRACT_PROMPT_PREFIX + pageText.slice(0, 30000);
  const body = { model: model || 'llama3.2', prompt, stream: false };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return (data.response || '').trim() || null;
}

/**
 * Extract important content: use Ollama if configured, else return truncated page text.
 * @param {string} pageText
 * @param {string|null} ollamaUrl - From options
 * @returns {Promise<string>} Content to send as extracted_content
 */
async function extractImportantContent(pageText, ollamaUrl) {
  if (!pageText || typeof pageText !== 'string') return '';
  const text = pageText.trim();
  if (!text) return '';

  if (ollamaUrl && ollamaUrl.trim()) {
    const extracted = await extractWithOllama(text, ollamaUrl.trim());
    if (extracted) return extracted;
  }

  return text.slice(0, MAX_DIRECT_LENGTH);
}

if (typeof globalThis !== 'undefined') {
  globalThis.KIDS_SAFETY_LLM = { extractImportantContent, extractWithOllama };
}
