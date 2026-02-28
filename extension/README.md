# sIsland – Browser Extension

Chrome extension (Manifest V3) with **Agent mode** (ask if content is real or AI-generated) and optional reporting/control features.

## API key (required)

The portal generates API keys (e.g. `53c7fbc2-06be-4a5e-b8d2-43b5e0232efd-agent`). Before using the extension:

1. Get an API key from the parent portal.
2. Click the extension icon → **Open extension options to enter API key** (or right‑click the icon → Options).
3. Paste the key and click **Save and validate**. The suffix sets the mode: `-agent` = Agent mode, `-control` = Control mode.
4. After saving, the popup shows the correct mode (Agent chat or Control status).

The extension sends the key in the **X-API-Key** header to the gateway. The gateway validates format and mode.

## Agent mode

- In Agent mode, click the extension icon to open the chat popup.
- Enter a question such as “Is this content real?” or “Is this AI-generated?” and click **Ask agent**.
- The extension **reads the full page** (text + image/video URLs), optionally runs a **local open-source LLM** (Ollama) to extract important content, then sends to the gateway: **extracted_content**, **media_urls**, **url**, **message**. The gateway uses this for fact-checking and media-checking.
- **Local LLM**: In Options, set **Ollama URL** (e.g. `http://localhost:11434`) and run Ollama with a model (`ollama pull llama3.2`). The extension sends page text to Ollama to extract key facts; that summary is sent as `extracted_content`. If Ollama is not set, truncated page text is sent.
- **Requires**: Gateway running (see `gateway/`); optionally fact-checking and media-checking services for full answers.

## What it does (other / optional)

- **Keyword detection**: Scans page text for safety categories (violence, bullying, adult, self-harm). Only category names and counts are sent, never raw phrases.
- **PII detection & redaction**: Detects email, phone, SSN, credit card, address-like patterns. PII is never sent; it is stripped locally.
- **Video hint**: Sets `video.has_video` when the page contains a `<video>` element (for future deepfake/media checks).
- **Reporting**: Page signals (PAGE_SIGNAL) are still collected by the content script and sent to the background; **posting to the gateway report endpoint is disabled** (the `/v1/safety/report` endpoint was removed from use because it returns 404).

## Structure

```
extension/
├── manifest.json       # Manifest V3, action with popup
├── popup.html / popup.js   # Agent mode: chat UI, asks gateway /v1/agent/chat
├── config.js           # Gateway base URL
├── background.js       # Service worker (handles PAGE_SIGNAL; report posting disabled)
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

### 2. Verify keyword detection

Open any page that contains one of the sample keywords (e.g. the word “weapon” or “violence”). With the test server running, you should see `matchedCategories` and `countByCategory` in the logged report. Or use a local HTML file:

```html
<!-- test-page.html -->
<body><p>This page has the word weapon and violence.</p></body>
```

Open it in Chrome (`file:///.../test-page.html`). Keyword detection still runs; report posting to the gateway is disabled.

### 3. Inspect the extension

- **Background (service worker)**: `chrome://extensions/` → find “sIsland” → click **Service worker** to open DevTools. Check **Console** for `[sIsland BG]` logs.
- **Content script**: On any page, open DevTools (F12) → **Console**. Look for `[sIsland Content]`; you can also run `KIDS_SAFETY_PROCESSOR.processPageText('some text with weapon')`.
- **Popup**: Right‑click the extension icon → **Inspect popup**; Console shows `[sIsland Popup]` logs.

### 4. Debugging (why the extension isn't working)

Logs use the prefix **`[sIsland Popup]`**, **`[sIsland Content]`**, **`[sIsland BG]`**. Set `DEBUG = true` in popup.js, content.js, and background.js (default on).

- **"Could not read page text"**: In **Popup console** see which step failed (sendMessage = content script not in tab → reload page; executeScript failed = restricted URL). In **Page console** check for `getPageText: … text length=0` if content script is present.
- **Gateway errors**: Popup console shows `sendToAgent: gateway error` with status and body.
- **Background**: Service worker console shows `PAGE_SIGNAL received` (report posting is disabled).

### 5. Quick checklist

| Step | What to do |
|------|------------|
| Load | Load unpacked from `extension` folder |
| Browse | Open a normal or test page (http/https); reload after installing/updating |
| Analyze | Click extension icon → Agent → Analyze page |
| Debug | Inspect popup + page DevTools Console; filter by "sIsland" |

## Config

Edit `config.js`:

- **GATEWAY_BASE_URL**: FastAPI gateway base (default `http://localhost:8000`). Used for `/v1/agent/chat` and `/v1/agent/analyze` only; report endpoint posting is disabled.

## Extending

- **Keywords**: Edit `lib/keywords.js` (`KEYWORD_CATEGORIES`) or load lists from storage/remote.
- **PII**: Add patterns in `lib/pii.js` (`PII_PATTERNS`).
- **Audio**: Set `audio.has_audio` in content when you add audio capture/analysis.
- **Auth**: Add an API key or token in `config.js` and set headers in `background.js` when calling the gateway.
