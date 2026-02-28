# sIsland Extension – Design (Two Modes)

## System architecture (high level)

| Part | Stack | Purpose |
|------|--------|---------|
| **Parents website** | **Django** (backend) + **Next.js** (frontend) | Parent dashboard: kids, devices, **mode & blacklist** per kid, stats, alerts. |
| **APIs** | **FastAPI** | Extension gateway: **Agent** (chat, fact-check, AI-generated check), **Control** (blacklist + harmful-content check, block response). |

---

## Extension: two modes

The extension operates in **one of two modes** per device/kid (set by the parent in the portal):

| Mode | Purpose | User experience |
|------|--------|-----------------|
| **Agent mode** | Let the user ask about the current page | User can **text an agent** to ask: “Is this content real?” and “Is this content AI-generated?”. Extension sends page context (URL, optional summary); backend uses fact_checking + media_checking and replies. No blocking. |
| **Control mode** | Enforce safety for the child | Extension **checks every navigation**: (1) Is the site on the **parent’s blacklist**? (2) Does the page have **harmful content** (e.g. keywords, threat intel)? If yes → **block the page** and **play an AI-generated video** explaining why the child shouldn’t access it. |

---

## Agent mode (ask the agent)

- **UI**: Chat / “Ask agent” panel (popup or side panel) where the user types questions about the **current page**.
- **Questions supported** (conceptually):
  - “Is the content on this page **real** (factual) or not?” → backend uses **fact_checking** (and optionally page content/URL).
  - “Is the content on this page **AI-generated**?” → backend uses **media_checking** (e.g. Hive AI) for images/video on the page; for text, optional text-AI detector or “we can’t tell” response.
- **Flow**:
  1. User opens agent UI, optionally selects “current page” context.
  2. Extension sends to FastAPI: **device_token**, **current page URL** (and optionally redacted text summary or image/video URLs), **user message**.
  3. FastAPI: validates token, calls fact_checking and/or media_checking as needed, optionally an LLM to summarize; returns **agent reply** (e.g. “This content appears to be …”, “This image is likely AI-generated.”).
  4. Extension shows the reply in the chat. Optionally store conversation history (backend or local) for parent review or continuity.
- **Privacy**: No PII sent; page content can be summarized or only URL + public metadata sent; media_checking can work on image/video URLs only.

---

## Control mode (block + explain)

- **Checks on each navigation** (or on load):
  1. **Blacklist**: Is the current **URL or domain** in the **parent-defined blacklist** for this kid? (Stored in portal DB; extension or FastAPI fetches/syncs list, or FastAPI resolves per request.)
  2. **Harmful content**: Does the page match **harmful content** rules? (e.g. known malicious site, threat intel, or local keyword scan; optional server-side scan.)
- **If either check fails**:
  - **Block** the page (replace with extension’s block page / overlay).
  - **Play an AI-generated video** that explains why the child shouldn’t access this website (e.g. “This site isn’t safe because …”; video can be pre-generated per “reason” or generic, hosted by you).
- **Flow**:
  1. User navigates to a URL.
  2. Extension (or FastAPI) checks blacklist + harmful content.
  3. If **allow** → page loads normally.
  4. If **block** → extension shows block overlay and plays the chosen **explainer video** (e.g. by reason: “blocked_by_blacklist”, “harmful_content”).
- **Parent**: In portal, manages **blacklist** (per kid or per device) and optionally **harmful-content** policy; can see **block events** (URL, reason, time) in dashboard.

---

## High-level architecture (two modes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  sIsland Extension                                                            │
│  Mode = Agent | Control (per device, from portal)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  AGENT MODE                          │  CONTROL MODE                         │
│  • Chat UI                           │  • On navigate / load:                │
│  • User asks: “Real? AI-generated?”   │    • Check blacklist (parent-set)     │
│  • Send: url, message, [context]      │    • Check harmful content             │
│  • Show agent reply                  │  • If block: overlay + play           │
│  • Backend: fact_check + media_check │    AI-generated explainer video       │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                    │
                    ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FastAPI gateway                                                             │
│  • Agent: /v1/agent/chat (message + page url/context) → fact_check,          │
│          media_check → reply                                                  │
│  • Control: /v1/control/check (device_token, url) → blacklist + harmful      │
│            → allow | block + reason (+ video_id or video_url)                 │
│  • Blacklist: from DB (per Kid); harmful: rules or external intel           │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Django (portal) + shared DB                                                │
│  • Parents: kids, devices, mode (agent | control) per device/kid            │
│  • Blacklist (URLs/domains) per kid                                          │
│  • Block events, agent conversation history (optional)                      │
│  • Explainer videos: metadata (reason → video_url) or storage                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Principles

- **Agent mode**: No blocking; user-driven questions; backend uses existing **fact_checking** and **media_checking** to answer “real?” and “AI-generated?”.
- **Control mode**: Parent-defined **blacklist** + **harmful content**; block + **AI-generated explainer video** for the child.
- **Privacy**: No PII in agent or control requests; page content can be URL/summary only.
- **Mode and blacklist** are set in the **parents portal** and applied per device/kid.

---

## Relation to existing backend

- **media_checking** (Hive AI): Used in **Agent mode** to answer “Is this image/video AI-generated?”; optionally used in Control mode if you scan media on the page for harm.
- **fact_checking**: Used in **Agent mode** to answer “Is this content real?”.
- **FastAPI**: Single gateway for both **Agent** (chat, fact-check, AI-generated) and **Control** (check URL, return allow/block + video).
- **Django**: Portal for parents – **mode** (agent vs control) per kid/device, **blacklist** per kid, **block events**, optional **conversation history** and **explainer video** config.

---

## Next steps

1. **Portal**: Add **mode** (agent | control) to Device or Kid; add **Blacklist** model (e.g. URL/domain per Kid); API for FastAPI to read blacklist and mode.
2. **FastAPI**:  
   - **Agent**: `POST /v1/agent/chat` (device_token, url, message, optional context) → call fact_check + media_check → return reply.  
   - **Control**: `POST /v1/control/check` (device_token, url) → check blacklist + harmful → return `{ "allowed": bool, "reason?", "video_url?" }`.
3. **Extension**:  
   - **Agent**: Chat UI, send message + page URL to gateway, show reply.  
   - **Control**: Before load or on load, call check endpoint; if block → show overlay and play video (e.g. `<video src="…">` from gateway or CDN).
4. **Explainer videos**: Produce or host AI-generated shorts per block reason; store mapping (reason → video_url) in config or DB; gateway returns `video_url` in block response.
