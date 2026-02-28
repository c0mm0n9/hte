# Kids Safety – Browser Extension

Chrome extension (Manifest V3) with **Agent mode** (ask if content is real or AI-generated) and optional reporting/control features.

## Agent mode (current)

- Click the extension icon to open the **Agent** popup.
- Enter a question such as “Is this content real?” or “Is this AI-generated?” and click **Ask agent**.
- The extension sends the current page URL and your message to the gateway `POST /v1/agent/chat`; the backend uses fact-checking and (if you provide media URLs) media-checking and returns a reply in the popup.
- **Requires**: Gateway running (see `backend/services/gateway`); optionally fact-checking and media-checking services for full answers.

## What it does (other / optional)

- **Keyword detection**: Scans page text for safety categories (violence, bullying, adult, self-harm). Only category names and counts are sent, never raw phrases.
- **PII detection & redaction**: Detects email, phone, SSN, credit card, address-like patterns. PII is never sent; it is stripped locally.
- **Video hint**: Sets `video.has_video` when the page contains a `<video>` element (for future deepfake/media checks).
- **Reporting**: Batched POST to `GATEWAY_BASE_URL + REPORT_ENDPOINT` with payloads like:
  ```json
  { "reports": [ { "ts", "url", "domain", "keywords", "audio", "video" } ] }
  ```

## Structure

```
extension/
├── manifest.json       # Manifest V3, action with popup
├── popup.html / popup.js   # Agent mode: chat UI, asks gateway /v1/agent/chat
├── config.js           # Gateway URL (background / report endpoint)
├── background.js       # Service worker: queues reports (optional)
├── content.js          # Content script: page signals (optional)
├── lib/
│   ├── keywords.js     # Category lists + detectKeywords()
│   ├── pii.js          # PII patterns + redactPII() / hasPII()
│   └── processor.js    # processPageText(), buildReportPayload()
└── README.md
```

## Load in Chrome

1. Open `chrome://extensions/`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `extension` folder.

Optional: add icons under `icons/` (e.g. `icon-48.png`, `icon-96.png`) and set `"icons": { "48": "icons/icon-48.png", "96": "icons/icon-96.png" }` in `manifest.json`.

## Testing

### 1. Load the extension

Follow **Load in Chrome** above. The extension will appear in your toolbar and run on all sites.

### 2. (Optional) Run the test server to see reports

The extension POSTs to `http://localhost:8000/v1/safety/report`. If nothing is listening, the request fails silently. To see the payload:

```bash
cd extension
node test-server.js
```

Leave this running, then browse in Chrome. After ~2 seconds on a page, the terminal will print the report JSON (url, domain, keywords, audio, video).

### 3. Verify keyword detection

Open any page that contains one of the sample keywords (e.g. the word “weapon” or “violence”). With the test server running, you should see `matchedCategories` and `countByCategory` in the logged report. Or use a local HTML file:

```html
<!-- test-page.html -->
<body><p>This page has the word weapon and violence.</p></body>
```

Open it in Chrome (`file:///.../test-page.html`). After a couple of seconds, the report should show `"violence"` in `keywords.matchedCategories`.

### 4. Inspect the extension

- **Background (service worker)**: `chrome://extensions/` → find “Kids Safety” → click **Service worker** (or “Inspect views: service worker”) to open DevTools. Check **Console** for errors and **Network** for the POST to `safety/report`.
- **Content script**: On any page, open DevTools (F12) → **Console**. The content script runs in the page context; you can test the processor manually, e.g.  
  `KIDS_SAFETY_PROCESSOR.processPageText('some text with weapon')`

### 5. Quick checklist

| Step | What to do |
|------|------------|
| Load | Load unpacked from `extension` folder |
| Server | Run `node test-server.js` in `extension` |
| Browse | Open a normal or test page in Chrome |
| Wait | ~2 s (debounce) |
| See report | Check test-server terminal for JSON |
| Debug | Extension → Service worker → Network / Console |

## Config

Edit `config.js` (or override in background):

- **GATEWAY_BASE_URL**: FastAPI gateway base (default `http://localhost:8000`).
- **REPORT_ENDPOINT**: Path for reports (default `/v1/safety/report`).
- **SEND_DEBOUNCE_MS**: Delay before flushing the report queue (default 2000).
- **MAX_PAYLOAD_SIZE**: Max JSON body size in bytes (default 64KB).

## Gateway contract (for FastAPI)

The extension POSTs to the report endpoint with:

```json
{
  "reports": [
    {
      "ts": "2025-02-28T12:00:00.000Z",
      "url": "https://example.com/page",
      "domain": "example.com",
      "keywords": {
        "matchedCategories": ["violence"],
        "countByCategory": { "violence": 2 }
      },
      "audio": { "has_audio": false },
      "video": { "has_video": true }
    }
  ]
}
```

No PII is included. The gateway can respond with `200` and optionally a body (e.g. `{ "malicious": false }` or block/alert instructions); the extension does not currently act on the response.

## Extending

- **Keywords**: Edit `lib/keywords.js` (`KEYWORD_CATEGORIES`) or load lists from storage/remote.
- **PII**: Add patterns in `lib/pii.js` (`PII_PATTERNS`).
- **Audio**: Set `audio.has_audio` in content when you add audio capture/analysis.
- **Auth**: Add an API key or token in `config.js` and set headers in `background.js` when calling the gateway.
