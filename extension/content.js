/**
 * Content script: extracts safe signals from the page (keywords, url/domain).
 * PII is stripped locally; only non-PII data is sent to the background.
 */
(function () {
  const processor = globalThis.KIDS_SAFETY_PROCESSOR;
  if (!processor) return;

  function getPageText() {
    const body = document.body;
    if (!body) return '';
    const el = document.querySelector('main, article, [role="main"]') || body;
    return (el.innerText || el.textContent || '').slice(0, 50000);
  }

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
