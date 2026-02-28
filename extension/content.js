/**
 * Content script: extracts safe signals from the page (keywords, url/domain).
 * Also responds to GET_PAGE_CONTENT with full text + media URLs for the Agent LLM.
 */
(function () {
  const DEBUG = true;
  function log(...args) {
    if (DEBUG) console.log('[sIsland Content]', ...args);
  }

  function isExtensionContextValid() {
    try {
      return !!chrome.runtime?.id;
    } catch (_) {
      return false;
    }
  }

  const processor = globalThis.KIDS_SAFETY_PROCESSOR;

  function getPageText() {
    const body = document.body;
    if (!body) {
      log('getPageText: no document.body');
      return '';
    }
    const selectors = ['main', 'article', '[role="main"]', '.article-body', '.post-content', '.content', '.entry-content', '.story-body'];
    let el = body;
    for (const sel of selectors) {
      const found = document.querySelector(sel);
      if (found && (found.innerText || found.textContent || '').length > 100) {
        el = found;
        break;
      }
    }
    const raw = (el.innerText || el.textContent || '').trim();
    const out = (raw || (document.body && (document.body.innerText || document.body.textContent || '').trim()) || '').slice(0, 50000);
    log('getPageText: el=', el.tagName, 'text length=', out.length);
    return out;
  }

  /** Collect absolute URLs of images and videos on the page. */
  function getMediaUrls() {
    const urls = new Set();
    try {
      document.querySelectorAll('img[src]').forEach(function (img) {
        try {
          const u = new URL(img.src, document.baseURI);
          if (u.protocol === 'http:' || u.protocol === 'https:') urls.add(u.href);
        } catch (_) {}
      });
      document.querySelectorAll('video source[src], video[src]').forEach(function (el) {
        const src = el.src || el.getAttribute('src');
        if (!src) return;
        try {
          const u = new URL(src, document.baseURI);
          if (u.protocol === 'http:' || u.protocol === 'https:') urls.add(u.href);
        } catch (_) {}
      });
    } catch (_) {}
    return Array.from(urls);
  }

  const MAX_IMAGES = 5;
  const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
  const MAX_VIDEOS = 1;
  const MAX_VIDEO_BYTES = 5 * 1024 * 1024;

  function blobToBase64(blob) {
    return new Promise(function (resolve, reject) {
      const r = new FileReader();
      r.onload = function () {
        const dataUrl = r.result;
        const base64 = dataUrl.indexOf(',') >= 0 ? dataUrl.split(',')[1] : dataUrl;
        resolve(base64);
      };
      r.onerror = reject;
      r.readAsDataURL(blob);
    });
  }

  async function fetchAsBase64(url, maxBytes) {
    try {
      const res = await fetch(url, { mode: 'cors', credentials: 'omit' });
      if (!res.ok) return null;
      const blob = await res.blob();
      if (blob.size > maxBytes) return null;
      const contentType = blob.type || 'application/octet-stream';
      const base64 = await blobToBase64(blob);
      return { url, base64, contentType };
    } catch (_) {
      return null;
    }
  }

  async function getPageContentWithMedia() {
    const text = getPageText();
    const mediaUrls = getMediaUrls();
    const imageUrls = [];
    const videoUrls = [];
    mediaUrls.forEach(function (u) {
      const lower = u.toLowerCase();
      if (/\.(mp4|webm|ogg|mov|avi|mkv)(\?|$)/.test(lower) || lower.includes('video')) {
        videoUrls.push(u);
      } else {
        imageUrls.push(u);
      }
    });

    const imageBlobs = [];
    for (let i = 0; i < Math.min(MAX_IMAGES, imageUrls.length); i++) {
      const r = await fetchAsBase64(imageUrls[i], MAX_IMAGE_BYTES);
      if (r) imageBlobs.push(r);
    }

    const videoBlobs = [];
    for (let i = 0; i < Math.min(MAX_VIDEOS, videoUrls.length); i++) {
      const r = await fetchAsBase64(videoUrls[i], MAX_VIDEO_BYTES);
      if (r) videoBlobs.push(r);
    }

    return {
      text,
      mediaUrls,
      imageBlobs,
      videoBlobs,
      videoUrls: videoUrls.slice(0, 5),
      imageUrls: imageUrls.slice(0, 10),
    };
  }

  /** Panic overlay: full-page block until user presses "I understood". */
  let panicOverlayEl = null;
  let panicAnalyzingTimeout = null;
  var PANIC_ANALYZING_TIMEOUT_MS = 90000;

  function showPanicOverlay(status, payload) {
    if (panicAnalyzingTimeout) {
      clearTimeout(panicAnalyzingTimeout);
      panicAnalyzingTimeout = null;
    }
    if (status === 'analyzing') {
      panicAnalyzingTimeout = setTimeout(function () {
        panicAnalyzingTimeout = null;
        if (panicOverlayEl) {
          showPanicOverlay('error', { message: 'This is taking longer than usual. You can close this and try again.' });
        }
      }, PANIC_ANALYZING_TIMEOUT_MS);
    }
    if (!document.body) return;
    if (!panicOverlayEl) {
      panicOverlayEl = document.createElement('div');
      panicOverlayEl.id = 'sIsland-panic-overlay';
      panicOverlayEl.style.cssText = [
        'position:fixed;inset:0;z-index:2147483647;',
        'background:rgba(254,247,237,0.97);',
        'display:flex;flex-direction:column;align-items:center;justify-content:center;',
        'padding:24px;font-family:Source Sans 3,system-ui,sans-serif;',
        'box-sizing:border-box;',
      ].join('');
      document.body.appendChild(panicOverlayEl);
    }
    var title = document.createElement('div');
    title.style.cssText = 'font-size:1.1rem;font-weight:600;color:#a89880;margin-bottom:16px;';
    title.textContent = status === 'analyzing' ? 'Checking if this page is safe…' : (status === 'error' ? 'Something went wrong' : 'Is this page safe?');
    var body = document.createElement('div');
    body.style.cssText = 'max-width:420px;text-align:center;color:#6b5344;line-height:1.5;margin-bottom:24px;';
    if (status === 'analyzing') {
      body.textContent = 'Please wait while we analyze the content.';
    } else if (status === 'error') {
      body.textContent = payload && payload.message ? payload.message : 'An error occurred.';
    } else {
      body.textContent = (payload && payload.explanation) ? payload.explanation : 'Analysis complete.';
    }
    var btnWrap = document.createElement('div');
    btnWrap.style.cssText = 'margin-top:8px;';
    if (status !== 'analyzing') {
      var btn = document.createElement('button');
      btn.textContent = 'I understood';
      btn.style.cssText = [
        'padding:12px 24px;font-size:1rem;font-weight:600;color:#fff;',
        'background:#0284c7;border:none;border-radius:8px;cursor:pointer;',
      ].join('');
      btn.onclick = function () {
        if (panicOverlayEl && panicOverlayEl.parentNode) {
          panicOverlayEl.parentNode.removeChild(panicOverlayEl);
          panicOverlayEl = null;
        }
      };
      btnWrap.appendChild(btn);
    }
    panicOverlayEl.innerHTML = '';
    panicOverlayEl.appendChild(title);
    panicOverlayEl.appendChild(body);
    panicOverlayEl.appendChild(btnWrap);
  }

  function updatePanicOverlay(payload) {
    if (!panicOverlayEl || !payload) return;
    if (panicAnalyzingTimeout) {
      clearTimeout(panicAnalyzingTimeout);
      panicAnalyzingTimeout = null;
    }
    showPanicOverlay(payload.status || 'result', payload);
  }

  chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
    function safeSendResponse(value) {
      try {
        if (isExtensionContextValid()) sendResponse(value);
      } catch (_) {}
    }
    if (msg.type === 'GET_PAGE_CONTENT') {
      const text = getPageText();
      const mediaUrls = getMediaUrls();
      log('GET_PAGE_CONTENT: text length=', text.length, 'mediaUrls=', mediaUrls.length);
      safeSendResponse({ text, mediaUrls });
      return false;
    }
    if (msg.type === 'GET_PAGE_CONTENT_WITH_MEDIA') {
      log('GET_PAGE_CONTENT_WITH_MEDIA: start');
      getPageContentWithMedia().then(function (res) {
        log('GET_PAGE_CONTENT_WITH_MEDIA: done text length=', (res && res.text || '').length);
        safeSendResponse(res);
      });
      return true;
    }
    if (msg.type === 'SHOW_PANIC_OVERLAY') {
      showPanicOverlay(msg.status || 'analyzing', msg);
      safeSendResponse({ ok: true });
      return false;
    }
    if (msg.type === 'UPDATE_PANIC_OVERLAY') {
      updatePanicOverlay(msg);
      safeSendResponse({ ok: true });
      return false;
    }
    return false;
  });
  log('content script loaded, message listener attached');

  if (!processor) return;

  function getUrlAndDomain() {
    try {
      const url = window.location.href;
      const domain = window.location.hostname;
      return { url, domain };
    } catch {
      return { url: '', domain: '' };
    }
  }

  function collectAndSend() {
    if (!isExtensionContextValid()) return;
    try {
      const text = getPageText();
      const result = processor.processPageText(text);
      if (!result) return;

      const { url, domain } = getUrlAndDomain();
      const payload = processor.buildReportPayload({
        url,
        domain,
        keywords: result.keywords,
        audio: { has_audio: false },
        video: { has_video: !!document.querySelector('video') },
      });

      chrome.runtime.sendMessage({ type: 'PAGE_SIGNAL', payload }).catch(function () {});
    } catch (_) {}
  }

  let scheduled = null;
  function scheduleSend() {
    if (scheduled) return;
    scheduled = setTimeout(() => {
      scheduled = null;
      collectAndSend();
    }, 1500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleSend);
  } else {
    scheduleSend();
  }

  const observer = new MutationObserver(scheduleSend);
  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  /** Simple predator-risk phrase check (expand or replace with API later). */
  function checkPredatorRisk(text) {
    if (!text || typeof text !== 'string') return false;
    const lower = text.toLowerCase();
    const phrases = [
      'meet in person', 'don\'t tell your parents', 'send your photo',
      'private chat', 'keep this secret', 'meet me alone', 'send your address',
    ];
    for (let i = 0; i < phrases.length; i++) {
      if (lower.includes(phrases[i])) return true;
    }
    return false;
  }

  function sendPageVisit() {
    if (!isExtensionContextValid()) return;
    try {
      const url = window.location.href;
      const title = document.title || '';
      const text = getPageText();
      let has_harmful_content = false;
      let has_pii = false;
      let has_predators = false;
      if (processor) {
        const result = processor.processPageText(text);
        if (result) {
          has_harmful_content = !!(result.keywords && result.keywords.matchedCategories && result.keywords.matchedCategories.length > 0);
          has_pii = !!result.piiDetected;
        }
      }
      has_predators = checkPredatorRisk(text);

      chrome.runtime.sendMessage({
        type: 'PAGE_VISIT',
        url: url,
        title: title,
        has_harmful_content: has_harmful_content,
        has_pii: has_pii,
        has_predators: has_predators,
      }).catch(function () {});
    } catch (_) {}
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', sendPageVisit);
  } else {
    sendPageVisit();
  }
})();
