/**
 * Content script: extracts safe signals from the page (keywords, url/domain).
 * Also responds to GET_PAGE_CONTENT with full text + media URLs for the Agent LLM.
 */
(function () {
  const processor = globalThis.KIDS_SAFETY_PROCESSOR;

  function getPageText() {
    const body = document.body;
    if (!body) return '';
    const el = document.querySelector('main, article, [role="main"]') || body;
    return (el.innerText || el.textContent || '').slice(0, 50000);
  }

  /** Collect absolute URLs of images and videos on the page (for AI-generated check). */
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

  chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
    if (msg.type === 'GET_PAGE_CONTENT') {
      sendResponse({ text: getPageText(), mediaUrls: getMediaUrls() });
    }
    return false;
  });

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

    chrome.runtime.sendMessage({ type: 'PAGE_SIGNAL', payload }).catch(() => {});
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
})();
