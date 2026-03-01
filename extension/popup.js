const DEFAULT_GATEWAY_BASE = (typeof globalThis !== 'undefined' && globalThis.KIDS_SAFETY_CONFIG?.GATEWAY_BASE_URL) || 'http://127.0.0.1:8003';
const STORAGE_KEY = 'kidsSafetyApiKey';
const STORAGE_MODE = 'kidsSafetyMode';
const STORAGE_GATEWAY_BASE_URL = 'kidsSafetyGatewayBaseUrl';

async function getGatewayBaseUrl() {
  const data = await new Promise((r) => chrome.storage.local.get([STORAGE_GATEWAY_BASE_URL], (d) => r(d)));
  const base = (data[STORAGE_GATEWAY_BASE_URL] || DEFAULT_GATEWAY_BASE).toString().trim();
  return base.replace(/\/$/, '');
}

const DEBUG = true;
function log(...args) {
  if (DEBUG) console.log('[sIsland Popup]', ...args);
}

const setupPanel = document.getElementById('setup-panel');
const controlPanel = document.getElementById('control-panel');
const agentPanel = document.getElementById('agent-panel');
const openOptionsLink = document.getElementById('open-options');
const pageUrlEl = document.getElementById('page-url');
const messageEl = document.getElementById('message');
const sendBtn = document.getElementById('send-btn');
const replyEl = document.getElementById('reply');
const explainActionsEl = document.getElementById('explain-actions');
const explainOutputEl = document.getElementById('explain-output');
const explainFlashcardsBtn = document.getElementById('explain-flashcards');
const explainAudioBtn = document.getElementById('explain-audio');
const explainVideoBtn = document.getElementById('explain-video');

let lastAgentResponse = null;

function showPanel(panel) {
  setupPanel.classList.remove('active');
  controlPanel.classList.remove('active');
  agentPanel.classList.remove('active');
  panel.classList.add('active');
}

async function getStoredKeyAndMode() {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY, STORAGE_MODE], (data) => {
      resolve({ apiKey: data[STORAGE_KEY] || null, mode: data[STORAGE_MODE] || null });
    });
  });
}

async function getCurrentTabUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.url || '';
}

function setReply(text, isError = false, isHtml = false) {
  const raw = text || 'No reply.';
  replyEl.classList.toggle('empty', !text);
  replyEl.classList.toggle('error', isError);
  replyEl.innerHTML = isHtml ? raw : raw
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function getPageTextAndMediaUrls() {
  const body = document.body;
  if (!body) return { text: '', mediaUrls: [], imageUrls: [], videoUrls: [] };
  const selectors = ['main', 'article', '[role="main"]', '.article-body', '.post-content', '.content', '.entry-content', '.story-body'];
  let el = body;
  for (const sel of selectors) {
    try {
      const found = document.querySelector(sel);
      if (found && (found.innerText || found.textContent || '').length > 100) {
        el = found;
        break;
      }
    } catch (_) {}
  }
  const text = ((el.innerText || el.textContent || '') + (el === body ? '' : ' ' + (body.innerText || body.textContent || ''))).trim().slice(0, 50000);
  const mediaUrls = [];
  const imageUrls = [];
  const videoUrls = [];
  try {
    document.querySelectorAll('img[src]').forEach(function (img) {
      try {
        const u = new URL(img.src, document.baseURI);
        if (u.protocol === 'http:' || u.protocol === 'https:') {
          mediaUrls.push(u.href);
          imageUrls.push(u.href);
        }
      } catch (_) {}
    });
    document.querySelectorAll('video source[src], video[src]').forEach(function (v) {
      const src = v.src || v.getAttribute('src');
      if (!src) return;
      try {
        const u = new URL(src, document.baseURI);
        if (u.protocol === 'http:' || u.protocol === 'https:') {
          mediaUrls.push(u.href);
          videoUrls.push(u.href);
        }
      } catch (_) {}
    });
  } catch (_) {}
  return { text, mediaUrls, imageUrls, videoUrls };
}

/** Injectable: collect only image/video URLs (no page text). Used when only media check is enabled. */
function getMediaUrlsOnlyInPage() {
  const imageUrls = [];
  const videoUrls = [];
  try {
    document.querySelectorAll('img[src]').forEach(function (img) {
      try {
        const u = new URL(img.src, document.baseURI);
        if (u.protocol === 'http:' || u.protocol === 'https:') imageUrls.push(u.href);
      } catch (_) {}
    });
    document.querySelectorAll('video source[src], video[src]').forEach(function (v) {
      const src = v.src || v.getAttribute('src');
      if (!src) return;
      try {
        const u = new URL(src, document.baseURI);
        if (u.protocol === 'http:' || u.protocol === 'https:') videoUrls.push(u.href);
      } catch (_) {}
    });
  } catch (_) {}
  return { imageUrls: imageUrls.slice(0, 20), videoUrls: videoUrls.slice(0, 5) };
}

/** Get only media URLs and page URL (no page text). Use when only media check is enabled. */
async function getPageMediaOnly() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return { imageUrls: [], videoUrls: [], website_url: '' };
  try {
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'GET_MEDIA_URLS_ONLY' });
    if (result && (Array.isArray(result.imageUrls) || Array.isArray(result.videoUrls))) {
      return {
        imageUrls: result.imageUrls || [],
        videoUrls: result.videoUrls || [],
        website_url: result.website_url || tab.url || '',
      };
    }
  } catch (_) {}
  try {
    const inj = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: getMediaUrlsOnlyInPage });
    const r = inj && inj[0] && inj[0].result;
    if (r) return { imageUrls: r.imageUrls || [], videoUrls: r.videoUrls || [], website_url: tab.url || '' };
  } catch (_) {}
  return { imageUrls: [], videoUrls: [], website_url: tab.url || '' };
}

async function getPageContentWithMedia() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    log('getPageContentWithMedia: no active tab');
    return { text: '', mediaUrls: [], imageBlobs: [], videoBlobs: [], videoUrls: [], imageUrls: [] };
  }
  log('getPageContentWithMedia: tabId=', tab.id, 'url=', tab.url);

  try {
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_CONTENT_WITH_MEDIA' });
    const hasText = result && (result.text || '').trim().length > 0;
    const hasMedia = result && ((result.imageUrls && result.imageUrls.length > 0) || (result.videoUrls && result.videoUrls.length > 0));
    if (result && (hasText || hasMedia)) {
      log('getPageContentWithMedia: content script GET_PAGE_CONTENT_WITH_MEDIA ok, text length=', (result.text || '').length);
      return result;
    }
    log('getPageContentWithMedia: content script returned empty text');
  } catch (e) {
    log('getPageContentWithMedia: sendMessage GET_PAGE_CONTENT_WITH_MEDIA failed', e?.message || e);
  }

  try {
    const fallback = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_CONTENT' });
    if (fallback && (fallback.text || '').trim().length > 0) {
      log('getPageContentWithMedia: fallback GET_PAGE_CONTENT ok, text length=', (fallback.text || '').length);
      var urls = fallback.mediaUrls || [];
      var imgUrls = [];
      var vidUrls = [];
      urls.forEach(function (u) {
        var lower = (u || '').toLowerCase();
        if (/\.(mp4|webm|ogg|mov|avi|mkv)(\?|$)/.test(lower) || lower.includes('video')) vidUrls.push(u);
        else imgUrls.push(u);
      });
      return {
        text: fallback.text,
        mediaUrls: urls,
        imageBlobs: [],
        videoBlobs: [],
        imageUrls: imgUrls.slice(0, 20),
        videoUrls: vidUrls.slice(0, 5),
        website_url: tab.url || '',
      };
    }
    log('getPageContentWithMedia: fallback returned empty text');
  } catch (e) {
    log('getPageContentWithMedia: sendMessage GET_PAGE_CONTENT failed', e?.message || e);
  }

  try {
    const inj = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: getPageTextAndMediaUrls,
    });
    const r = inj && inj[0] && inj[0].result;
    if (r && (r.text || '').trim().length > 0) {
      log('getPageContentWithMedia: executeScript ok, text length=', (r.text || '').length);
      return {
        text: r.text,
        mediaUrls: r.mediaUrls || [],
        imageBlobs: [],
        videoBlobs: [],
        videoUrls: r.videoUrls || [],
        imageUrls: r.imageUrls || [],
        website_url: tab.url || '',
      };
    }
    log('getPageContentWithMedia: executeScript returned empty or no result', r ? 'result keys=' + Object.keys(r || {}).join(',') : 'no result');
  } catch (e) {
    log('getPageContentWithMedia: executeScript failed', e?.message || e);
  }

  log('getPageContentWithMedia: all methods failed, returning empty');
  return { text: '', mediaUrls: [], imageBlobs: [], videoBlobs: [], videoUrls: [], imageUrls: [], website_url: '' };
}

function base64ToBlob(base64, contentType) {
  const bin = atob(base64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: contentType || 'application/octet-stream' });
}

function fileNameFromUrl(url) {
  try {
    const path = new URL(url).pathname;
    const name = path.split('/').pop() || 'image';
    return name.length > 80 ? name.slice(0, 80) : name;
  } catch (_) {
    return 'image';
  }
}

function extensionFromContentType(contentType) {
  if (!contentType) return '';
  const m = (contentType || '').toLowerCase();
  if (m.includes('png')) return '.png';
  if (m.includes('jpeg') || m.includes('jpg')) return '.jpg';
  if (m.includes('gif')) return '.gif';
  if (m.includes('webp')) return '.webp';
  if (m.includes('mp4')) return '.mp4';
  if (m.includes('webm')) return '.webm';
  return '';
}

function filenameFromUrl(url, prefix, defaultExt) {
  try {
    const path = new URL(url).pathname;
    const name = path.split('/').pop() || prefix;
    const sane = name.length > 60 ? name.slice(0, 60) : name;
    return sane.includes('.') ? sane : sane + defaultExt;
  } catch (_) {
    return prefix + defaultExt;
  }
}

const MAX_IMAGE_BYTES = 3 * 1024 * 1024;
const MAX_VIDEO_BYTES = 15 * 1024 * 1024;

/** Fetch media URLs in extension context (avoids CORS). Returns { imageBlobs: [{ blob, contentType, filename }], videoBlobs } */
async function fetchMediaUrlsInExtension(imageUrls, videoUrls) {
  const imageBlobs = [];
  for (let i = 0; i < (imageUrls || []).length; i++) {
    try {
      const res = await fetch(imageUrls[i], { method: 'GET', credentials: 'omit' });
      if (!res.ok) continue;
      const blob = await res.blob();
      if (blob.size > MAX_IMAGE_BYTES) continue;
      const contentType = blob.type || 'application/octet-stream';
      const ext = extensionFromContentType(contentType) || '.png';
      const filename = filenameFromUrl(imageUrls[i], 'image_' + i, ext);
      imageBlobs.push({ blob, contentType, filename });
    } catch (_) {}
  }
  const videoBlobs = [];
  for (let i = 0; i < (videoUrls || []).length; i++) {
    try {
      const res = await fetch(videoUrls[i], { method: 'GET', credentials: 'omit' });
      if (!res.ok) continue;
      const blob = await res.blob();
      if (blob.size > MAX_VIDEO_BYTES) continue;
      const contentType = blob.type || 'application/octet-stream';
      const ext = extensionFromContentType(contentType) || '.mp4';
      const filename = filenameFromUrl(videoUrls[i], 'video_' + i, ext);
      videoBlobs.push({ blob, contentType, filename });
    } catch (_) {}
  }
  return { imageBlobs, videoBlobs };
}

/** Build multipart/form-data for POST /v1/agent/run: api_key, prompt, website_content, website_url, file(s). */
function buildAgentRunFormData(options) {
  const form = new FormData();
  form.append('api_key', options.api_key || '');
  form.append('prompt', (options.prompt || '').trim() || 'Analyze this content for safety. Is it real or AI-generated?');
  form.append('website_content', (options.website_content || '').trim() || '');
  form.append('website_url', (options.website_url || '').trim() || '');
  if (options.send_fact_check) form.append('send_fact_check', 'true');
  if (options.send_media_check) form.append('send_media_check', 'true');
  const imageBlobs = options.imageBlobs || [];
  const videoBlobs = options.videoBlobs || [];
  imageBlobs.forEach(function (item, i) {
    if (item && item.blob) {
      form.append('file', item.blob, item.filename || 'image_' + i + '.png');
    } else if (item && item.base64) {
      const ext = extensionFromContentType(item.contentType) || '.png';
      const b = base64ToBlob(item.base64, item.contentType);
      form.append('file', b, item.filename || 'image_' + i + ext);
    }
  });
  videoBlobs.forEach(function (item, i) {
    if (item && item.blob) {
      form.append('file', item.blob, item.filename || 'video_' + i + '.mp4');
    } else if (item && item.base64) {
      const ext = extensionFromContentType(item.contentType) || '.mp4';
      const b = base64ToBlob(item.base64, item.contentType);
      form.append('file', b, item.filename || 'video_' + i + ext);
    }
  });
  return form;
}

function escapeHtml(s) {
  if (typeof s !== 'string') return '';
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function stripUrls(text) {
  if (typeof text !== 'string') return '';
  return text.replace(/https?:\/\/[^\s<>"\']+/gi, '').replace(/\s{2,}/g, ' ').trim();
}

function formatAgentRunResponse(data) {
  const parts = [];
  let explanation = (data.trust_score_explanation || '').trim();
  if (explanation) {
    explanation = stripUrls(explanation);
    if (explanation) {
      parts.push(explanation.replace(/\n/g, '<br>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>'));
    }
  }
  if (typeof data.trust_score === 'number') {
    const score = Math.max(0, Math.min(100, data.trust_score));
    const tier = score < 40 ? 'low' : score < 65 ? 'mid' : 'high';
    parts.push(
      '<div class="trust-score-bar-wrap">' +
        '<div class="trust-score-label">Trust score: ' + score + ' / 100</div>' +
        '<div class="trust-score-bar-track">' +
          '<div class="trust-score-bar-fill ' + tier + '" style="width:' + score + '%"></div>' +
        '</div>' +
      '</div>'
    );
  }

  const fakeFacts = data.fake_facts || [];
  const trueFacts = data.true_facts || [];
  const allFacts = [
    ...fakeFacts.map(function (f) { return { ...f, isFake: true }; }),
    ...trueFacts.map(function (f) { return { ...f, isFake: false }; }),
  ];
  allFacts.forEach(function (f) {
    const quote = escapeHtml((f.fact || '').trim()) || escapeHtml(f.explanation || 'No quote');
    const cardClass = f.isFake ? 'fact-card fake' : 'fact-card true';
    const verdict = f.isFake ? 'Disputed / likely false' : 'Supported / likely true';
    parts.push(
      '<div class="' + cardClass + '">' +
        '<div class="fact-quote">' + quote + '</div>' +
        '<div class="fact-verdict">' + verdict + '</div>' +
      '</div>'
    );
  });

  const fakeMedia = data.fake_media || [];
  if (fakeMedia.length > 0) {
    parts.push('<strong>Media flagged:</strong>');
    fakeMedia.forEach(function (m, i) {
      const label = (m.media_type || 'Media') + ' ' + (i + 1);
      parts.push((i + 1) + '. ' + escapeHtml(label) + (m.chunks && m.chunks.length ? ' (' + m.chunks.length + ' segments)' : ''));
    });
  }
  if (parts.length === 0) return 'No structured result.';
  return parts.join('<br><br>');
}

async function sendToAgent() {
  const { apiKey, mode } = await getStoredKeyAndMode();
  if (!apiKey) {
    setReply('API key missing. Open options to enter your key.', true);
    return;
  }

  const pageUrl = await getCurrentTabUrl();
  const message = (messageEl.value || '').trim();

  sendBtn.disabled = true;
  if (explainActionsEl) explainActionsEl.classList.remove('visible');
  lastAgentResponse = null;
  setReply('Reading page…');
  log('sendToAgent: pageUrl=', pageUrl);

  try {
    const content = await getPageContentWithMedia();
    const pageText = (content.text || '').trim();
    const allMediaUrls = [...(content.imageUrls || []), ...(content.videoUrls || [])];
    if (!pageText && allMediaUrls.length === 0) {
      log('sendToAgent: no page text and no media');
      setReply('Could not read page content or media. Reload the page and try again, or the site may block access.', true);
      sendBtn.disabled = false;
      return;
    }

    setReply('Downloading media…');
    const { imageBlobs: downloadedImages, videoBlobs: downloadedVideos } = await fetchMediaUrlsInExtension(content.imageUrls || [], content.videoUrls || []);

    setReply('Masking private information…');
    const piiResult = (pageText && globalThis.KIDS_SAFETY_PII && globalThis.KIDS_SAFETY_PII.maskPII)
      ? globalThis.KIDS_SAFETY_PII.maskPII(pageText)
      : { masked: pageText || '', detectedTypes: [] };
    const maskedText = piiResult.masked || pageText || '';
    let websiteContent = (maskedText || '').slice(0, 12000).trim();
    if (downloadedImages.length > 0 || downloadedVideos.length > 0) {
      if (websiteContent) websiteContent += '\n\n';
      websiteContent += 'Attached files: ' + downloadedImages.length + ' image(s), ' + downloadedVideos.length + ' video(s).';
    } else if (allMediaUrls.length > 0) {
      if (websiteContent) websiteContent += '\n\n';
      else websiteContent = 'Page has no extractable text. ';
      websiteContent += 'Media URLs on this page:\n' + (content.imageUrls || []).concat(content.videoUrls || []).slice(0, 20).join('\n');
    }
    websiteContent = websiteContent.slice(0, 50000);
    const websiteUrl = content.website_url || pageUrl || '';

    setReply('Sending to agent gateway…');

    const gatewayBase = await getGatewayBaseUrl();
    const agentRunUrl = gatewayBase + '/v1/agent/run';
    const formData = buildAgentRunFormData({
      api_key: apiKey,
      prompt: message || 'Analyze this content for safety. Is it real or AI-generated?',
      website_content: websiteContent,
      website_url: websiteUrl,
      imageBlobs: downloadedImages,
      videoBlobs: downloadedVideos,
      send_fact_check: true,
      send_media_check: true,
    });

    const res = await fetch(agentRunUrl, {
      method: 'POST',
      body: formData,
    });

    if (res.status === 401 || res.status === 403) {
      const data = await res.json().catch(() => ({}));
      setReply(data.detail || 'Invalid API key. Check options.', true);
      sendBtn.disabled = false;
      return;
    }

    if (!res.ok) {
      const err = await res.text();
      log('sendToAgent: gateway error', res.status, err);
      setReply('Request failed: ' + res.status + '. ' + err, true);
      sendBtn.disabled = false;
      return;
    }

    const data = await res.json();
    log('sendToAgent: success', data);
    lastAgentResponse = data;
    if (explainActionsEl) explainActionsEl.classList.add('visible');
    if (explainOutputEl) { explainOutputEl.classList.remove('visible'); explainOutputEl.innerHTML = ''; }
    setReply(formatAgentRunResponse(data), false, true);
  } catch (e) {
    log('sendToAgent: fetch error', e?.message || e);
    setReply('Could not reach the agent gateway. Is it running at ' + (await getGatewayBaseUrl()) + '?', true);
  } finally {
    sendBtn.disabled = false;
  }
}

openOptionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

const panicBtn = document.getElementById('panic-btn');
if (panicBtn) {
  panicBtn.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      log('panic: no active tab');
      return;
    }
    panicBtn.disabled = true;
    try {
      chrome.runtime.sendMessage({ type: 'PANIC_REQUEST', tabId: tab.id }, () => {
        if (chrome.runtime.lastError) log('panic sendMessage error', chrome.runtime.lastError);
      });
    } finally {
      panicBtn.disabled = false;
    }
  });
}

function setExplainButtonsEnabled(enabled) {
  if (explainFlashcardsBtn) explainFlashcardsBtn.disabled = !enabled;
  if (explainAudioBtn) explainAudioBtn.disabled = !enabled;
  if (explainVideoBtn) explainVideoBtn.disabled = !enabled;
}

function showExplainOutput(html) {
  if (!explainOutputEl) return;
  explainOutputEl.innerHTML = html;
  explainOutputEl.classList.add('visible');
}

async function requestExplain(explanationType) {
  const { apiKey } = await getStoredKeyAndMode();
  if (!apiKey) {
    showExplainOutput('<span class="error">API key missing. Open options to enter your key.</span>');
    return;
  }
  if (!lastAgentResponse) {
    showExplainOutput('<span class="error">No analysis result. Run Analyze page first.</span>');
    return;
  }

  setExplainButtonsEnabled(false);
  showExplainOutput('Generating ' + (explanationType === 'flashcards' ? 'flashcards' : explanationType === 'audio' ? 'audio' : 'video') + '…');

  try {
    const gatewayBase = await getGatewayBaseUrl();
    const agentExplainUrl = gatewayBase + '/v1/agent/explain';
    const res = await fetch(agentExplainUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: apiKey,
        response: lastAgentResponse,
        explanation_type: explanationType,
        user_prompt: null,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      let detail = errText;
      try {
        const errJson = JSON.parse(errText);
        if (errJson.detail) detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      } catch (_) {}
      showExplainOutput('<span class="error">' + escapeHtml(detail) + '</span>');
      setExplainButtonsEnabled(true);
      return;
    }

    if (explanationType === 'flashcards') {
      const json = await res.json();
      const cards = json && Array.isArray(json.flashcards) ? json.flashcards : [];
      if (cards.length === 0) {
        showExplainOutput('<span class="error">No flashcards generated.</span>');
      } else {
        const html = cards.map(function (c) {
          const front = escapeHtml((c.front || '').trim());
          const back = escapeHtml((c.back || '').trim()).replace(/\n/g, '<br>');
          return '<div class="flashcard-item"><div class="fc-front">' + front + '</div><div class="fc-back">' + back + '</div></div>';
        }).join('');
        showExplainOutput(html);
      }
    } else {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const filename = explanationType === 'audio' ? 'explanation.mp3' : 'explanation.mp4';
      const mime = explanationType === 'audio' ? 'audio/mpeg' : 'video/mp4';
      const tag = explanationType === 'audio' ? 'audio' : 'video';
      const html = '<' + tag + ' controls src="' + escapeHtml(url) + '" style="max-width:100%;max-height:120px;"></' + tag + '>' +
        '<p style="margin:6px 0 0 0;"><a href="' + escapeHtml(url) + '" download="' + escapeHtml(filename) + '" style="font-size:11px;color:var(--emerald-600);">Download ' + filename + '</a></p>';
      showExplainOutput(html);
    }
  } catch (e) {
    log('requestExplain error', e?.message || e);
    showExplainOutput('<span class="error">' + escapeHtml((e && e.message) || String(e)) + '</span>');
  } finally {
    setExplainButtonsEnabled(true);
  }
}

if (explainFlashcardsBtn) explainFlashcardsBtn.addEventListener('click', () => requestExplain('flashcards'));
if (explainAudioBtn) explainAudioBtn.addEventListener('click', () => requestExplain('audio'));
if (explainVideoBtn) explainVideoBtn.addEventListener('click', () => requestExplain('video'));

sendBtn.addEventListener('click', sendToAgent);

(async function init() {
  const { apiKey, mode } = await getStoredKeyAndMode();

  if (!apiKey) {
    showPanel(setupPanel);
    return;
  }

  if (mode === 'control') {
    showPanel(controlPanel);
    return;
  }

  showPanel(agentPanel);
  getCurrentTabUrl().then((url) => {
    pageUrlEl.textContent = url || '—';
  });
})();
