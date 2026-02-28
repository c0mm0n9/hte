const GATEWAY_BASE_URL = (typeof globalThis !== 'undefined' && globalThis.KIDS_SAFETY_CONFIG?.GATEWAY_BASE_URL) || 'http://localhost:8003';
const AGENT_RUN_URL = GATEWAY_BASE_URL.replace(/\/$/, '') + '/v1/agent/run';
const STORAGE_KEY = 'kidsSafetyApiKey';
const STORAGE_MODE = 'kidsSafetyMode';
const STORAGE_SEND_FACT = 'kidsSafetySendFactCheck';
const STORAGE_SEND_MEDIA = 'kidsSafetySendMediaCheck';

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
const sendFactCheckEl = document.getElementById('send-fact-check');
const sendMediaCheckEl = document.getElementById('send-media-check');
const sendBtn = document.getElementById('send-btn');
const replyEl = document.getElementById('reply');

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

function setReply(text, isError = false) {
  const raw = text || 'No reply.';
  replyEl.classList.toggle('empty', !text);
  replyEl.classList.toggle('error', isError);
  replyEl.innerHTML = raw
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

async function getPageContentWithMedia() {
  // #region agent log
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H1',location:'popup.js:getPageContentWithMedia:entry',message:'Get content: tab query result',data:{hasTab:!!tab,tabId:tab?.id,tabUrl:(tab?.url||'').slice(0,80)},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  if (!tab?.id) {
    log('getPageContentWithMedia: no active tab');
    return { text: '', mediaUrls: [], imageBlobs: [], videoBlobs: [], videoUrls: [], imageUrls: [] };
  }
  log('getPageContentWithMedia: tabId=', tab.id, 'url=', tab.url);

  try {
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_CONTENT_WITH_MEDIA' });
    if (result && (result.text || '').trim().length > 0) {
      // #region agent log
      fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H2',location:'popup.js:getPageContentWithMedia:content_script_ok',message:'Got data from content script',data:{source:'content_script',textLength:(result.text||'').length},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
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
      // #region agent log
      fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H2',location:'popup.js:getPageContentWithMedia:fallback_ok',message:'Got data from fallback GET_PAGE_CONTENT',data:{source:'fallback',textLength:(fallback.text||'').length},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      log('getPageContentWithMedia: fallback GET_PAGE_CONTENT ok, text length=', (fallback.text || '').length);
      return {
        text: fallback.text,
        mediaUrls: fallback.mediaUrls || [],
        imageBlobs: [],
        videoBlobs: [],
        videoUrls: [],
        imageUrls: [],
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
      // #region agent log
      fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H2',location:'popup.js:getPageContentWithMedia:executeScript_ok',message:'Got data from executeScript',data:{source:'executeScript',textLength:(r.text||'').length},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      log('getPageContentWithMedia: executeScript ok, text length=', (r.text || '').length);
      return {
        text: r.text,
        mediaUrls: r.mediaUrls || [],
        imageBlobs: [],
        videoBlobs: [],
        videoUrls: r.videoUrls || [],
        imageUrls: r.imageUrls || [],
      };
    }
    log('getPageContentWithMedia: executeScript returned empty or no result', r ? 'result keys=' + Object.keys(r || {}).join(',') : 'no result');
  } catch (e) {
    log('getPageContentWithMedia: executeScript failed', e?.message || e);
  }

  // #region agent log
  fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H2',location:'popup.js:getPageContentWithMedia:all_failed',message:'All content sources failed',data:{source:'none',textLength:0},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  log('getPageContentWithMedia: all methods failed, returning empty');
  return { text: '', mediaUrls: [], imageBlobs: [], videoBlobs: [], videoUrls: [], imageUrls: [] };
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

function formatAgentRunResponse(data) {
  const parts = [];
  if (typeof data.trust_score === 'number') {
    parts.push('**Trust score:** ' + data.trust_score + ' / 100');
  }
  const fakeFacts = data.fake_facts || [];
  if (fakeFacts.length > 0) {
    parts.push('**Fake or disputed facts:**');
    fakeFacts.forEach(function (f, i) {
      parts.push((i + 1) + '. ' + (f.explanation || 'No explanation'));
    });
  }
  const fakeMedia = data.fake_media || [];
  if (fakeMedia.length > 0) {
    parts.push('**Media flagged:**');
    fakeMedia.forEach(function (m, i) {
      parts.push((i + 1) + '. ' + (m.media_url || m.media_type || 'Item') + (m.chunks?.length ? ' (' + m.chunks.length + ' segments)' : ''));
    });
  }
  if (parts.length === 0) return 'No structured result.';
  return parts.join('\n\n');
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
  setReply('Reading page…');
  log('sendToAgent: pageUrl=', pageUrl);

  try {
    const content = await getPageContentWithMedia();
    const pageText = (content.text || '').trim();
    // #region agent log
    fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H3',location:'popup.js:sendToAgent:after_getContent',message:'After getPageContentWithMedia',data:{pageTextLength:pageText.length,hasPageText:pageText.length>0,mediaUrlCount:(content.imageUrls||[]).length+(content.videoUrls||[]).length},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    log('sendToAgent: pageText length=', pageText.length);
    if (!pageText) {
      log('sendToAgent: no page text – check popup console and content script console for details');
      setReply('Could not read page text. Reload the page and try again, or the site may block access.', true);
      sendBtn.disabled = false;
      return;
    }

    setReply('Masking private information…');
    const piiResult = globalThis.KIDS_SAFETY_PII && globalThis.KIDS_SAFETY_PII.maskPII
      ? globalThis.KIDS_SAFETY_PII.maskPII(pageText)
      : { masked: pageText, detectedTypes: [] };
    const maskedText = piiResult.masked || pageText;
    log('sendToAgent: masking applied', {
      detectedTypes: piiResult.detectedTypes || [],
      originalLength: pageText.length,
      maskedLength: maskedText.length,
      textChanged: maskedText !== pageText,
    });

    const extracted = maskedText.slice(0, 12000);

    const allMediaUrls = [...(content.imageUrls || []), ...(content.videoUrls || [])];
    const imageCount = (content.imageUrls || []).length;
    const videoCount = (content.videoUrls || []).length;
    log('sendToAgent: media received', {
      imageUrls: imageCount,
      videoUrls: videoCount,
      totalMediaUrls: allMediaUrls.length,
      includedInPayload: Math.min(allMediaUrls.length, 20),
    });
    let websiteContent = (extracted || '').trim();
    if (allMediaUrls.length > 0) {
      websiteContent += '\n\nMedia URLs on this page:\n' + allMediaUrls.slice(0, 20).join('\n');
    }

    setReply('Sending to agent gateway…');

    // #region agent log
    const bodyToSend = { api_key: apiKey, prompt: message || 'Analyze this content for safety. Is it real or AI-generated?', website_content: websiteContent.slice(0, 50000) };
    fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H4',location:'popup.js:sendToAgent:before_fetch',message:'About to send to gateway',data:{agentRunUrl:AGENT_RUN_URL,websiteContentLength:(bodyToSend.website_content||'').length,hasApiKey:!!apiKey},timestamp:Date.now()})}).catch(()=>{});
    // #endregion

    const res = await fetch(AGENT_RUN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyToSend),
    });

    // #region agent log
    fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H5',location:'popup.js:sendToAgent:after_fetch',message:'Gateway response',data:{status:res.status,ok:res.ok},timestamp:Date.now()})}).catch(()=>{});
    // #endregion

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
    setReply(formatAgentRunResponse(data));
  } catch (e) {
    // #region agent log
    fetch('http://127.0.0.1:7559/ingest/50217504-a361-4152-a44d-43637131f823',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1d87d0'},body:JSON.stringify({sessionId:'1d87d0',runId:'ext',hypothesisId:'H4',location:'popup.js:sendToAgent:catch',message:'Fetch threw',data:{errorMessage:(e&&e.message)||String(e)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    log('sendToAgent: fetch error', e?.message || e);
    setReply('Could not reach the agent gateway. Is it running at ' + GATEWAY_BASE_URL + '?', true);
  } finally {
    sendBtn.disabled = false;
  }
}

openOptionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

sendBtn.addEventListener('click', sendToAgent);

if (sendFactCheckEl) {
  sendFactCheckEl.addEventListener('change', () => {
    chrome.storage.local.set({ [STORAGE_SEND_FACT]: sendFactCheckEl.checked });
  });
}
if (sendMediaCheckEl) {
  sendMediaCheckEl.addEventListener('change', () => {
    chrome.storage.local.set({ [STORAGE_SEND_MEDIA]: sendMediaCheckEl.checked });
  });
}

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

  const prefs = await new Promise((r) => {
    chrome.storage.local.get([STORAGE_SEND_FACT, STORAGE_SEND_MEDIA], (d) => r(d));
  });
  if (sendFactCheckEl && prefs[STORAGE_SEND_FACT] !== undefined) sendFactCheckEl.checked = prefs[STORAGE_SEND_FACT];
  if (sendMediaCheckEl && prefs[STORAGE_SEND_MEDIA] !== undefined) sendMediaCheckEl.checked = prefs[STORAGE_SEND_MEDIA];
})();
