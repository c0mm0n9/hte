const CONFIG = {
  PORTAL_API_BASE: 'http://localhost:8000',
  GATEWAY_BASE_URL: 'http://localhost:8003',
  BLOCKED_REDIRECT_URL: 'https://qweasdzxcsssssss.com',
};

const DEBUG = true;
function log(...args) {
  if (DEBUG) console.log('[sIsland BG]', ...args);
}

const BLACKLIST_CACHE_MS = 5 * 60 * 1000;
let blacklistCache = { list: null, at: 0 };

function isHostBlacklisted(hostname, blacklist) {
  if (!hostname || !Array.isArray(blacklist) || blacklist.length === 0) return false;
  const h = hostname.toLowerCase();
  for (let i = 0; i < blacklist.length; i++) {
    const v = (blacklist[i] || '').toLowerCase().trim();
    if (!v) continue;
    if (h === v || h.endsWith('.' + v)) return true;
  }
  return false;
}

function getBlacklist(apiKey, cb) {
  const now = Date.now();
  if (blacklistCache.list && (now - blacklistCache.at) < BLACKLIST_CACHE_MS) {
    cb(blacklistCache.list);
    return;
  }
  const base = (CONFIG.PORTAL_API_BASE || '').replace(/\/$/, '');
  if (!base) {
    cb([]);
    return;
  }
  const url = base + '/api/portal/blacklist/?api_key=' + encodeURIComponent(apiKey);
  fetch(url)
    .then(function (res) {
      if (!res.ok) {
        blacklistCache.list = [];
        blacklistCache.at = Date.now();
        cb([]);
        return;
      }
      return res.json();
    })
    .then(function (data) {
      const list = Array.isArray(data && data.blacklist) ? data.blacklist : [];
      blacklistCache.list = list;
      blacklistCache.at = Date.now();
      cb(list);
    })
    .catch(function () {
      blacklistCache.list = [];
      blacklistCache.at = Date.now();
      cb([]);
    });
}

function checkAndBlockNavigation(tabId, url) {
  if (!tabId || !url) return;
  try {
    const u = new URL(url);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return;
    if (url.startsWith(chrome.runtime.getURL(''))) return;
  } catch (_) {
    return;
  }
  chrome.storage.local.get(['kidsSafetyApiKey'], function (data) {
    const apiKey = data.kidsSafetyApiKey;
    if (!apiKey) return;
    getBlacklist(apiKey, function (list) {
      const hostname = (function () {
        try {
          return new URL(url).hostname;
        } catch (_) {
          return '';
        }
      })();
      if (!isHostBlacklisted(hostname, list)) return;
      log('blocking blacklisted:', url);
      const blockedPage = chrome.runtime.getURL('blocked.html?to=' + encodeURIComponent(CONFIG.BLOCKED_REDIRECT_URL));
      chrome.tabs.update(tabId, { url: blockedPage });
    });
  });
}

function isGoogleSearchUrl(url) {
  try {
    var u = new URL(url);
    var host = (u.hostname || '').toLowerCase().replace(/^www\./, '');
    var path = (u.pathname || '').toLowerCase();
    return host.indexOf('google') !== -1 && path.indexOf('/search') !== -1;
  } catch (_) {
    return false;
  }
}

function recordVisit(apiKey, url, title, has_harmful_content, has_pii, has_predators) {
  if (!apiKey || !url) return;
  if (isGoogleSearchUrl(url)) {
    log('skip record-visit: google search', url.slice(0, 50));
    return;
  }
  const base = (CONFIG.PORTAL_API_BASE || '').replace(/\/$/, '');
  if (!base) return;
  const recordUrl = base + '/api/portal/record-visit/';
  fetch(recordUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: apiKey,
      url: url,
      title: title || '',
      has_harmful_content: !!has_harmful_content,
      has_pii: !!has_pii,
      has_predators: !!has_predators,
    }),
  }).then(function (res) {
    if (res.ok) log('record-visit ok', url.slice(0, 50));
    else log('record-visit failed', res.status);
  }).catch(function (e) {
    log('record-visit error', e?.message);
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'PAGE_SIGNAL' && message.payload) {
    log('PAGE_SIGNAL received (report posting disabled)', message.payload?.url);
    sendResponse({ ok: true });
  }
  if (message.type === 'PAGE_VISIT' && message.url) {
    chrome.storage.local.get(['kidsSafetyApiKey'], function (data) {
      recordVisit(
        data.kidsSafetyApiKey,
        message.url,
        message.title,
        message.has_harmful_content,
        message.has_pii,
        message.has_predators,
      );
    });
    sendResponse({ ok: true });
  }
  return true;
});

chrome.webNavigation.onBeforeNavigate.addListener(function (details) {
  if (details.frameId !== 0) return;
  checkAndBlockNavigation(details.tabId, details.url);
});

log('service worker started');
