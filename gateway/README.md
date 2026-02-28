# Kids Safety – Local processor (gateway)

FastAPI **local processor** for the extension: Agent mode (chat: is content real? AI-generated?). Config (gateway URL, API key, etc.) lives in the **extension**; this service uses **env vars** only.

## Endpoints

- **GET /v1/auth/validate** – Header `X-API-Key` → `{ "valid": true, "mode": "agent" | "control" }`
- **POST /v1/agent/chat** – Header `X-API-Key` (agent key). Body: `url`, `message`, `extracted_content?`, `media_urls?` → `{ "reply": "..." }`

## Env (optional)

- `GATEWAY_FACT_CHECK_BASE_URL` (default `http://localhost:8001`)
- `GATEWAY_MEDIA_CHECK_BASE_URL` (default `http://localhost:8002`)
- `GATEWAY_FACT_CHECK_TIMEOUT_SECONDS` (default 30)
- `GATEWAY_MEDIA_CHECK_TIMEOUT_SECONDS` (default 60)

## Run

From the **gateway** directory (the one that contains `app`):

```bash
cd gateway
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Extension config (in `extension/config.js` and popup/options) sets the gateway URL the client uses.
