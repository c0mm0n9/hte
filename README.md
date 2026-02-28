# s-island

**A safe island for your child—amid a sea of harmful content.**

s-island helps families keep kids safe online with real-time protection, parental control (whitelist/blacklist), and optional AI-powered checks—without spying on private messages. Parents get clear risk summaries and device management; children keep their privacy.

---

## What’s in this repo

| Part | Description |
|------|-------------|
| **Frontend** (`hte/frontend`) | Next.js app: landing page, login/register, about, **parents portal** (devices, visited sites, whitelist/blacklist). |
| **Backend** (`hte/backend`) | Django + PostgreSQL: portal API (auth, devices, visited list, record-visit). |
| **Extension** (`hte/extension`) | Chrome extension (Manifest V3): **Control** mode (blocking) and **Agent** mode (ask “Is this real?” / “AI-generated?”). Same emerald/s-island theme as the web app. |
| **Gateway** (`hte/gateway`) | FastAPI service used by the extension for agent chat and validation. |
| **Backend services** (`hte/backend/services`) | Optional microservices (agent gateway, fact-checking, media-checking, etc.) for full AI flows. |

---

## Quick start

### 1. Database (PostgreSQL)

```bash
cd hte/backend
cp .env.example .env
# Edit .env if you want a different POSTGRES_PASSWORD

docker compose up -d
```

### 2. Backend (Django)

```bash
cd hte/backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

- API: **http://127.0.0.1:8000/api/portal/**
- Admin: **http://127.0.0.1:8000/admin/** (create a superuser with `createsuperuser` if needed)

### 3. Frontend (Next.js)

```bash
cd hte/frontend
npm install
npm run dev
```

- App: **http://localhost:3000**  
  (Landing, login, register, about, parents portal at `/portal`.)

### 4. Extension (Chrome)

1. Get an API key from the parents portal (add a device, copy its API key).
2. Open **Chrome** → `chrome://extensions/` → **Developer mode** → **Load unpacked** → select the `hte/extension` folder.
3. Click the extension icon → **Open extension options** → paste the API key → **Save and validate**.

Use **127.0.0.1** for the backend in the extension (see `extension/config.js`) so the extension can reach Django on machines where `localhost` is IPv6.

### 5. Gateway (optional, for Agent mode)

If you use Agent mode (“Is this real?” / “AI-generated?”), run the gateway:

```bash
cd hte/gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

Set `GATEWAY_BASE_URL` in `extension/config.js` to `http://127.0.0.1:8003` (or your gateway URL).

---

## Project structure

```
hte/
├── frontend/          # Next.js (App Router), Tailwind, s-island theme
├── backend/           # Django + portal app, PostgreSQL
│   ├── portal/        # API: auth, devices, visited sites, record-visit
│   └── services/      # Optional: agent_gateway, fact_checking, media_checking, etc.
├── extension/         # Chrome extension (popup, options, blocked page)
├── gateway/           # FastAPI gateway for extension (agent/validate)
└── README.md          # (this file lives at repo root; subfolders have their own READMEs)
```

---

## Features

- **Landing & branding**: s-island tagline, benefits, reviews carousel, Outfit + DM Sans.
- **Parents portal**: Devices, per-device whitelist/blacklist, visited sites with detection flags (harmful content, personal info leak, predators). Visit detail modal; no Google search in visited list.
- **Extension**: Control mode (blocking by blacklist), Agent mode (analyze page with gateway). Same emerald/s-island UI as the web app.
- **Backend**: Record visits from extension; filter out Google search from visited list; validate API keys; dashboard for parents.

---

## Docs in subfolders

- **Backend**: [hte/backend/README.md](hte/backend/README.md) — Django setup, Docker Postgres, portal API.
- **Frontend**: [hte/frontend/README.md](hte/frontend/README.md) — Next.js dev and deploy.
- **Extension**: [hte/extension/README.md](hte/extension/README.md) — API key, Agent/Control mode, loading in Chrome, config.
- **Gateway**: [hte/gateway/README.md](hte/gateway/README.md) — Endpoints and env for the local processor.

---

## Tech stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, TypeScript.
- **Backend**: Django 5, PostgreSQL, django-cors-headers.
- **Extension**: Vanilla JS, Manifest V3, Chrome APIs.
- **Gateway**: FastAPI (Python).

---

## License

Proprietary / internal use unless otherwise stated.
