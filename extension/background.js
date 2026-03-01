const CONFIG = {
  PORTAL_API_BASE: 'http://127.0.0.1:8000',
  GATEWAY_BASE_URL: 'http://127.0.0.1:8003',
  BLOCKED_REDIRECT_URL: 'https://qweasdzxcsssssss.com',
};

const DEBUG = true;
function log(...args) {
  if (DEBUG) console.log('[sIsland BG]', ...args);
}

function base64ToBlob(base64, contentType) {
  var bin = atob(base64);
  var arr = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: contentType || 'application/octet-stream' });
}

function extensionFromContentType(contentType) {
  if (!contentType) return '';
  var m = (contentType || '').toLowerCase();
  if (m.indexOf('png') !== -1) return '.png';
  if (m.indexOf('jpeg') !== -1 || m.indexOf('jpg') !== -1) return '.jpg';
  if (m.indexOf('gif') !== -1) return '.gif';
  if (m.indexOf('webp') !== -1) return '.webp';
  if (m.indexOf('mp4') !== -1) return '.mp4';
  if (m.indexOf('webm') !== -1) return '.webm';
  return '';
}

var MAX_IMAGE_BYTES_BG = 3 * 1024 * 1024;
var MAX_VIDEO_BYTES_BG = 15 * 1024 * 1024;

function filenameFromUrlBg(url, prefix, defaultExt) {
  try {
    var path = new URL(url).pathname;
    var name = path.split('/').pop() || prefix;
    var sane = name.length > 60 ? name.slice(0, 60) : name;
    return sane.indexOf('.') >= 0 ? sane : sane + defaultExt;
  } catch (_) {
    return prefix + defaultExt;
  }
}

/** Fetch media URLs in extension context; returns Promise<{ imageBlobs, videoBlobs }>. */
function fetchMediaUrlsInExtension(imageUrls, videoUrls) {
  var imageBlobs = [];
  var videoBlobs = [];
  function nextImage(i) {
    if (i >= (imageUrls || []).length) return nextVideo(0);
    var url = imageUrls[i];
    return fetch(url, { method: 'GET', credentials: 'omit' })
      .then(function (res) { return res.ok ? res.blob() : null; })
      .then(function (blob) {
        if (blob && blob.size <= MAX_IMAGE_BYTES_BG) {
          var contentType = blob.type || 'application/octet-stream';
          var ext = extensionFromContentType(contentType) || '.png';
          imageBlobs.push({ blob: blob, contentType: contentType, filename: filenameFromUrlBg(url, 'image_' + i, ext) });
        }
        return nextImage(i + 1);
      })
      .catch(function () { return nextImage(i + 1); });
  }
  function nextVideo(i) {
    if (i >= (videoUrls || []).length) return Promise.resolve({ imageBlobs: imageBlobs, videoBlobs: videoBlobs });
    var url = videoUrls[i];
    return fetch(url, { method: 'GET', credentials: 'omit' })
      .then(function (res) { return res.ok ? res.blob() : null; })
      .then(function (blob) {
        if (blob && blob.size <= MAX_VIDEO_BYTES_BG) {
          var contentType = blob.type || 'application/octet-stream';
          var ext = extensionFromContentType(contentType) || '.mp4';
          videoBlobs.push({ blob: blob, contentType: contentType, filename: filenameFromUrlBg(url, 'video_' + i, ext) });
        }
        return nextVideo(i + 1);
      })
      .catch(function () { return nextVideo(i + 1); });
  }
  return nextImage(0);
}

/** Build multipart/form-data for POST /v1/agent/run. */
function buildAgentRunFormData(options) {
  var form = new FormData();
  form.append('api_key', options.api_key || '');
  form.append('prompt', (options.prompt || '').trim() || 'Analyze this content for safety.');
  form.append('website_content', (options.website_content || '').trim() || '');
  form.append('website_url', (options.website_url || '').trim() || '');
  if (options.send_fact_check) form.append('send_fact_check', 'true');
  if (options.send_media_check) form.append('send_media_check', 'true');
  var imageBlobs = options.imageBlobs || [];
  var videoBlobs = options.videoBlobs || [];
  imageBlobs.forEach(function (item, i) {
    if (item && item.blob) {
      form.append('file', item.blob, item.filename || 'image_' + i + '.png');
    } else if (item && item.base64) {
      var ext = extensionFromContentType(item.contentType) || '.png';
      var b = base64ToBlob(item.base64, item.contentType);
      form.append('file', b, 'image_' + i + ext);
    }
  });
  videoBlobs.forEach(function (item, i) {
    if (item && item.blob) {
      form.append('file', item.blob, item.filename || 'video_' + i + '.mp4');
    } else if (item && item.base64) {
      var ext = extensionFromContentType(item.contentType) || '.mp4';
      var b = base64ToBlob(item.base64, item.contentType);
      form.append('file', b, 'video_' + i + ext);
    }
  });
  return form;
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
      // Never block Google (search, mail, etc.)
      const hostLower = (hostname || '').toLowerCase().replace(/^www\./, '');
      if (hostLower === 'google.com' || hostLower.endsWith('.google.com')) return;
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

var STORAGE_GATEWAY_BASE_URL = 'kidsSafetyGatewayBaseUrl';

function runPanicFlow(tabId, apiKey) {
  chrome.storage.local.get([STORAGE_GATEWAY_BASE_URL], function (storageData) {
    const gatewayBase = (storageData[STORAGE_GATEWAY_BASE_URL] || CONFIG.GATEWAY_BASE_URL || '').toString().trim().replace(/\/$/, '');
    const agentRunUrl = gatewayBase + '/v1/agent/run';
    const portalBase = (CONFIG.PORTAL_API_BASE || '').replace(/\/$/, '');
    const validateUrl = portalBase + '/api/portal/validate/?api_key=' + encodeURIComponent(apiKey);

    function sendOverlay(msg) {
      try {
        chrome.tabs.sendMessage(tabId, msg).catch(function (e) {
          log('panic sendOverlay error', e?.message);
        });
      } catch (e) {
        log('panic sendOverlay throw', e?.message);
      }
    }

    sendOverlay({ type: 'SHOW_PANIC_OVERLAY', status: 'analyzing' });

    fetch(validateUrl)
      .then(function (res) { return res.json(); })
      .then(function (data) {
      if (!data.valid || !data.mode) {
        sendOverlay({ type: 'UPDATE_PANIC_OVERLAY', status: 'error', message: data.error || 'Invalid API key.' });
        return;
      }
      var prompt = (data.prompt && data.prompt.trim()) ? data.prompt.trim() : 'Analyze this content and explain in simple terms whether it is safe for a child.';
      var isControl = data.mode === 'control';
      return new Promise(function (resolve, reject) {
        chrome.tabs.sendMessage(tabId, { type: 'GET_PAGE_CONTENT_WITH_MEDIA' }, function (content) {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          resolve({ content: content || {}, prompt: prompt, isControl: isControl });
        });
      });
      })
      .then(function (payload) {
      var content = payload.content;
      var prompt = payload.prompt;
      var isControl = payload.isControl;
      var text = (content && content.text) ? content.text : '';
      var imageUrls = content.imageUrls || [];
      var videoUrls = content.videoUrls || [];
      var websiteContent = (text || '').trim().slice(0, 12000);
      var websiteUrl = (content.website_url || '').trim();
      return Promise.resolve(websiteUrl ? null : chrome.tabs.get(tabId))
        .then(function (tab) {
          var url = websiteUrl || (tab && tab.url ? tab.url : '');
          return fetchMediaUrlsInExtension(imageUrls, videoUrls).then(function (fetched) {
            var nImg = fetched.imageBlobs.length;
            var nVid = fetched.videoBlobs.length;
            if (nImg > 0 || nVid > 0) {
              if (websiteContent) websiteContent += '\n\n';
              else websiteContent = 'Page has no extractable text. ';
              websiteContent += 'Attached files: ' + nImg + ' image(s), ' + nVid + ' video(s).';
            }
            websiteContent = websiteContent.slice(0, 50000);
            return {
              websiteUrl: url,
              websiteContent: websiteContent,
              imageBlobs: fetched.imageBlobs,
              videoBlobs: fetched.videoBlobs,
              prompt: prompt,
              isControl: isControl,
            };
          });
        });
      })
      .then(function (params) {
      var formData = buildAgentRunFormData({
        api_key: apiKey,
        prompt: params.prompt,
        website_content: params.websiteContent,
        website_url: params.websiteUrl,
        send_fact_check: params.isControl,
        send_media_check: params.isControl,
        imageBlobs: params.imageBlobs,
        videoBlobs: params.videoBlobs,
      });
      return fetch(agentRunUrl, { method: 'POST', body: formData });
      })
      .then(function (res) {
      if (!res.ok) {
        res.text().then(function () {
          sendOverlay({ type: 'UPDATE_PANIC_OVERLAY', status: 'error', message: 'Could not get an answer. Try again.' });
        });
        return;
      }
      res.json()
        .then(function (data) {
          var explanation = (data && data.trust_score_explanation != null) ? String(data.trust_score_explanation).trim() : '';
          if (!explanation && data && data.trust_score != null) {
            explanation = 'Trust score: ' + data.trust_score + ' / 100.';
          }
          if (!explanation) explanation = 'Analysis complete.';
          log('panic result received, sending overlay update to tab', tabId);
          sendOverlay({ type: 'UPDATE_PANIC_OVERLAY', status: 'result', explanation: explanation, trust_score: data && data.trust_score });
        })
        .catch(function (err) {
          log('panic res.json error', err && err.message);
          sendOverlay({ type: 'UPDATE_PANIC_OVERLAY', status: 'error', message: 'Invalid response from gateway. Try again.' });
        });
      })
      .catch(function (e) {
        log('panic flow error', e?.message);
        sendOverlay({ type: 'UPDATE_PANIC_OVERLAY', status: 'error', message: e && e.message ? e.message : 'Could not connect. Check your connection and try again.' });
      });
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
  if (message.type === 'PANIC_REQUEST' && message.tabId) {
    chrome.storage.local.get(['kidsSafetyApiKey'], function (data) {
      var apiKey = data.kidsSafetyApiKey;
      if (!apiKey) {
        try {
          chrome.tabs.sendMessage(message.tabId, { type: 'UPDATE_PANIC_OVERLAY', status: 'error', message: 'No API key set. Open extension options to add your key.' });
        } catch (_) {}
        sendResponse({ ok: false });
        return;
      }
      runPanicFlow(message.tabId, apiKey);
      sendResponse({ ok: true });
    });
    return true;
  }
  return true;
});

chrome.webNavigation.onBeforeNavigate.addListener(function (details) {
  if (details.frameId !== 0) return;
  checkAndBlockNavigation(details.tabId, details.url);
});

log('service worker started');
