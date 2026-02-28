# Portal–Extension Connection & Database Plan

## Overview

- **Parents** register via **Django REST Framework (DRF)**.
- After registration, parents **add kids** and **link extensions** (one extension instance = one “device” tied to one kid).
- Each device runs in one of **two modes** (set by parent in portal):
  - **Agent mode**: User can chat with an agent to ask “Is this content real?” and “Is this AI-generated?”. No blocking.
  - **Control mode**: Extension checks blacklist + harmful content; if match → **block page** and **play an AI-generated explainer video**.
- The **extension** uses a **device token** for all API calls; FastAPI and Django share the same DB for mode, blacklist, block events, and optional agent history.

---

## 1. How portal and extension connect

### Linking flow

1. **Parent** logs into the portal (DRF auth), goes to “My kids” → picks a kid (or creates one) → “Add device / Link extension”.
2. **Portal** creates a **Device** record and generates a **unique pairing token** (e.g. UUID or short code). Optionally the parent gives the device a name (e.g. “Chrome on laptop”).
3. **Parent** sees a **pairing code** (and/or QR / link) and enters it (or opens the link) **in the extension**.
4. **Extension** sends the pairing code to the gateway; gateway validates it, returns a **long‑lived device token** and links the Device to the Kid. Extension stores the device token (e.g. in `chrome.storage.local`).
5. From then on, the extension sends **every request** with the **device token**. Gateway resolves Device → Kid → Parent.
6. **Parent** sets **mode** (Agent | Control) and **blacklist** (Control only) per kid in the portal. Extension fetches or receives mode/blacklist so it knows whether to show the agent chat (Agent mode) or run block checks (Control mode).

So: **one Device = one extension install = one Kid**. The “connection” is the device token. **Mode and blacklist** define Agent vs Control behaviour.

### Two implementation options for the code

| Option | Where pairing is validated | Device token issued by |
|--------|----------------------------|--------------------------|
| **A**  | FastAPI gateway            | FastAPI (calls Django to create/lookup Device, or reads shared DB) |
| **B**  | Django (DRF)               | Django (DRF endpoint); FastAPI only accepts token and writes to DB |

Recommendation: **Option B** for v1 – Django owns “parent, kid, device, pairing”. DRF exposes:
- `POST /api/auth/register/` – parent registration
- `POST /api/kids/` – add kid (parent must be authenticated)
- `POST /api/kids/{id}/devices/` – create device, return **pairing_code** (short-lived, e.g. 6‑digit) and **device_token** (long‑lived, for extension)
- `POST /api/devices/pair/` (or extension-only) – extension calls with pairing_code; backend validates and returns device_token (or 404 if already used / expired)

FastAPI gateway: **Agent mode** – chat (fact-check, AI-generated check); **Control mode** – check blacklist + harmful content, return allow/block + explainer video URL; write block events to shared DB.

---

## 2. Database schema (Django + shared with FastAPI)

Use a **single database** (e.g. PostgreSQL) that both **Django** and **FastAPI** use. Django owns migrations and model definitions; FastAPI reads/writes the same tables (via SQLAlchemy, Django ORM, or raw SQL).

### Core entities

```
User (Django auth)     →  Parent
Kid                    →  belongs to Parent (ForeignKey User)
Device                 →  one extension install; belongs to Kid; has device_token, mode (agent | control)
BlacklistEntry         →  URL or domain blocked for a Kid (Control mode); parent-defined
Report                 →  (optional) payload from extension; belongs to Device
Alert                  →  (optional) notification for parent; belongs to Kid
BlockEvent             →  record when Control mode blocked a page; Device + url + reason + video
ExplainerVideo         →  reason → video_url for “why you shouldn’t access this” (AI-generated)
AgentConversation      →  (optional) Agent mode chat thread; Device or Kid
AgentMessage           →  (optional) single message in a conversation
```

### Suggested Django models (portal backend)

```python
# accounts: use Django's User (or AbstractUser) for parents
# No extra model needed if you use built-in User for registration.

# kids/models.py
class Kid(models.Model):
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kids')
    name = models.CharField(max_length=255)  # display name, e.g. "Emma"
    # Optional: birth_year, avatar, timezone, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# devices/models.py
class Device(models.Model):
    class Mode(models.TextChoices):
        AGENT = 'agent', 'Agent'    # User asks agent: real? AI-generated?
        CONTROL = 'control', 'Control'  # Blacklist + harmful content → block + explainer video

    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=255, blank=True)  # e.g. "Chrome on laptop"
    device_token = models.CharField(max_length=64, unique=True, db_index=True)  # long-lived; extension sends this
    pairing_code = models.CharField(max_length=16, unique=True, null=True, blank=True, db_index=True)  # short-lived, 6–8 chars
    pairing_code_expires_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.CONTROL)  # agent | control
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# blacklist/models.py  (Control mode: parent-defined blocked URLs/domains per kid)
class BlacklistEntry(models.Model):
    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name='blacklist_entries')
    value = models.CharField(max_length=2048)  # URL or domain (e.g. "example.com" or "https://example.com/path")
    is_domain_only = models.BooleanField(default=True)  # True = match whole domain; False = exact URL
    created_at = models.DateTimeField(auto_now_add=True)

# control/models.py  (Control mode: block events + explainer videos)
class BlockEvent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='block_events')
    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name='block_events')
    url = models.URLField(max_length=2048)
    domain = models.CharField(max_length=253, blank=True)
    reason = models.CharField(max_length=64)  # e.g. "blacklist", "harmful_content"
    explainer_video_url = models.URLField(max_length=2048, blank=True)  # video shown to child
    created_at = models.DateTimeField(auto_now_add=True)

class ExplainerVideo(models.Model):
    """Maps block reason → AI-generated explainer video URL (global or per-tenant)."""
    reason = models.CharField(max_length=64, unique=True)  # e.g. "blacklist", "harmful_content"
    title = models.CharField(max_length=255, blank=True)
    video_url = models.URLField(max_length=2048)
    created_at = models.DateTimeField(auto_now_add=True)

# agent/models.py  (optional: Agent mode conversation history for parent review)
class AgentConversation(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='agent_conversations')
    kid = models.ForeignKey(Kid, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_conversations')
    page_url = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AgentMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    conversation = models.ForeignKey(AgentConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

# reports/models.py  (optional; e.g. for stats or legacy report ingestion)
class Report(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='reports')
    # Denormalized for easy querying (optional but useful)
    kid_id = models.IntegerField(null=True, blank=True, db_index=True)
    ts = models.DateTimeField()  # from extension payload
    url = models.URLField(max_length=2048, blank=True)
    domain = models.CharField(max_length=253, blank=True, db_index=True)
    keywords = models.JSONField(default=dict)   # { "matchedCategories": [], "countByCategory": {} }
    audio = models.JSONField(default=dict)      # { "has_audio": false }
    video = models.JSONField(default=dict)      # { "has_video": false }
    created_at = models.DateTimeField(auto_now_add=True)

# alerts/models.py
class Alert(models.Model):
    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name='alerts')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='alerts')
    report = models.OneToOneField(Report, on_delete=models.SET_NULL, null=True, blank=True, related_name='alert')
    kind = models.CharField(max_length=64)  # e.g. "malicious_site", "risky_keywords", "blocked_content"
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.WARNING)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict)   # e.g. { "url": "...", "domain": "..." }
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Flow summary

| Step | Who | What |
|------|-----|------|
| 1 | Parent | Registers (DRF) → User created |
| 2 | Parent | Adds Kid (DRF) → Kid created |
| 3 | Parent | “Add device” for Kid (DRF) → Device created, pairing_code + device_token; set **mode** (agent \| control) |
| 4 | Parent | (Control) Adds **blacklist** entries (URLs/domains) for Kid |
| 5 | Parent | Gives pairing_code to child; child enters it in extension |
| 6 | Extension | Calls pairing endpoint with pairing_code → receives device_token + **mode**; stores them |
| 7a | Extension (Agent) | User asks “Is this real? AI-generated?” → POST to FastAPI agent chat → show reply |
| 7b | Extension (Control) | On navigate: POST to FastAPI control/check (device_token, url) → allow or block + video_url; if block → show overlay + play explainer video |
| 8 | FastAPI | Agent: fact_check + media_check → reply. Control: check blacklist + harmful → BlockEvent + ExplainerVideo URL |
| 9 | Parent | Portal: view block events, blacklist, (optional) agent conversation history per kid/device |

---

## 3. Token and security

- **device_token**: Long-lived, high-entropy (e.g. 32 bytes hex or UUID). Stored in `Device.device_token`; extension sends it on every report. FastAPI (or Django) validates it and resolves Device.
- **pairing_code**: Short-lived (e.g. 15 min), one-time use. After successful pairing, clear `pairing_code` and `pairing_code_expires_at` (or mark Device as “paired” so the code cannot be reused).
- **CORS**: Allow extension origin or use a non-browser client pattern; FastAPI/Django allow the gateway URL you use from the extension.
- **HTTPS**: Use HTTPS in production for both portal and gateway so device_token is not sent in clear text.

---

## 4. API summary (for implementation)

### Django (DRF) – portal backend

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/auth/register/` | Parent registration |
| POST | `/api/auth/login/` | Parent login (token / session) |
| GET/POST | `/api/kids/` | List / create kids |
| GET/PATCH/DELETE | `/api/kids/{id}/` | Kid detail / update / delete |
| POST | `/api/kids/{id}/devices/` | Create device → returns pairing_code + device_token |
| GET/PATCH/DELETE | `/api/kids/{id}/devices/` | List / revoke devices; PATCH to set **mode** (agent \| control) |
| POST | `/api/devices/pair/` | Extension: `{ "pairing_code": "..." }` → `{ "device_token": "...", "mode": "agent" \| "control" }` |
| GET/POST/DELETE | `/api/kids/{id}/blacklist/` | List / add / remove blacklist entries (Control mode) |
| GET | `/api/kids/{id}/block-events/` | List block events (Control mode history) |
| GET | `/api/kids/{id}/alerts/` | List alerts (parent dashboard) |
| GET | `/api/kids/{id}/agent-conversations/` | (Optional) List agent chat threads |
| PATCH | `/api/alerts/{id}/read/` | Mark alert as read |
| GET/POST | `/api/explainer-videos/` | (Admin or portal) List / set reason → video_url for block explainers |

### FastAPI – extension gateway

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/agent/chat` | Body: `{ "device_token", "url", "message", "context?" }` → fact_check + media_check → `{ "reply": "..." }` |
| POST | `/v1/control/check` | Body: `{ "device_token", "url" }` → check blacklist + harmful → `{ "allowed": bool, "reason?", "video_url?" }`; if block, write BlockEvent |
| GET | `/v1/control/config` | (Optional) Header: device_token → `{ "mode", "blacklist": [...] }` so extension can sync |

### Extension behaviour by mode

- **Pairing**: Extension calls `POST /api/devices/pair/` with pairing_code; stores `device_token` and `mode`. If no token, show “Link in parent portal”.
- **Agent mode**: Show chat UI; on send, POST to FastAPI `/v1/agent/chat` with device_token, current page URL, and message; display reply.
- **Control mode**: Before or on page load, POST to FastAPI `/v1/control/check` with device_token and URL. If `allowed: false`, show block overlay and play `video_url` (AI-generated explainer).

---

## 5. Next steps

1. **Django**: Create apps `accounts`, `kids`, `devices`, `blacklist`, `control`, `agent`, (optional) `reports`, `alerts`; add models including **Device.mode**, **BlacklistEntry**, **BlockEvent**, **ExplainerVideo**, **AgentConversation** / **AgentMessage**; run migrations.
2. **DRF**: Registration, kids CRUD, device create + pairing (return mode), **blacklist** CRUD per kid, **block-events** list, (optional) agent-conversations list; **explainer-videos** config; permissions so only the parent accesses their data.
3. **FastAPI**: **Agent** – `POST /v1/agent/chat` (device_token, url, message) → fact_check + media_check → reply. **Control** – `POST /v1/control/check` (device_token, url) → blacklist + harmful check → allow or block + video_url; write BlockEvent. Optional `GET /v1/control/config` for extension to sync mode/blacklist.
4. **Extension**: Pairing UI + store device_token and **mode**. **Agent mode**: chat UI, call `/v1/agent/chat`, show reply. **Control mode**: on navigate call `/v1/control/check`; if block → overlay + play explainer video from `video_url`.
5. **Explainer videos**: Produce or host AI-generated shorts (e.g. “Why you shouldn’t visit this site”); store reason → video_url in **ExplainerVideo**; gateway returns URL in block response.
6. **Portal (Next.js)**: Register/login, add kid, add device (pairing code + set mode), **blacklist** management, block events list, (optional) agent conversation history, explainer video config.

This gives you a full plan for **Agent mode** (chat: real? AI-generated?) and **Control mode** (blacklist + harmful content → block + AI explainer video), with a single DB and clear APIs.
