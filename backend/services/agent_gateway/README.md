# Agent Gateway

FastAPI service: orchestrates LLM actions, ai_text_detector, media_checking, fact_checking, info_graph, content_safety; returns trust score and explanation.

## Port 8003 and Docker

- The extension calls **http://127.0.0.1:8003** for `/v1/agent/run`.
- **Docker Compose** maps **8003** to the `agent_gateway` container.
- If you run **both** Docker and local uvicorn, only one process can bind to 8003.

### Option A: Use Docker (recommended if other services are in Docker)

From `backend/services/`:

```bash
docker compose up -d agent_gateway
```

If you get **404** on `POST /v1/agent/run`, rebuild the image so the container has the latest code:

```bash
docker compose build agent_gateway
docker compose up -d agent_gateway
```

### Option B: Run locally on 8003 (stop Docker agent_gateway first)

1. Free port 8003:
   ```bash
   docker stop hte-agent-gateway
   ```
2. From **this directory** (`backend/services/agent_gateway`):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8003
   ```
3. Check startup logs: you should see `Route: POST /agent/run` (under prefix `/v1`). Then open http://127.0.0.1:8003/healthz and http://127.0.0.1:8003/v1/agent/run (POST with JSON body).

### Option C: Run locally on another port (e.g. 8007)

If you want Docker and local agent_gateway at the same time:

1. Run uvicorn on a different port:
   ```bash
   cd backend/services/agent_gateway
   uvicorn app.main:app --reload --port 8007
   ```
2. Point the extension at 8007: in `extension/config.js` set `GATEWAY_BASE_URL: 'http://127.0.0.1:8007'` (or use extension options if supported).

## Verify routes

On startup the app logs registered routes. You should see at least:

- `GET /healthz`
- `POST /agent/run` (served as `/v1/agent/run`)

If `POST /v1/agent/run` returns **404**, the process on 8003 is either not this app (e.g. wrong service or old image) or the router failed to load (check for import errors in the startup log).
