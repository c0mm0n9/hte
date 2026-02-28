# Postman API tests for HTE backend

Use these files in [Postman] to test the backend containers (Agent Gateway, Media Checking, Fact Checking).

## Prerequisites

1. Backend containers running, e.g.:
   ```bash
   cd backend/services
   docker compose up -d
   ```
2. **Agent Gateway** → `http://localhost:8003` (ensure `agent_gateway/.env` has LLM and service URLs; set `AGENT_GATEWAY_ALLOWED_API_KEYS=test-key` to use the test requests, or leave empty to skip key validation)
3. **Media Checking** → `http://localhost:8000`
4. **Fact Checking** → `http://localhost:8001` (ensure `fact_checking/.env` has provider API keys if you run fact-check requests)

## Import into Postman

1. Open Postman (app or web).
2. **Import collection**: Collections → **Import** → **Import from Postman** → choose `HTE-Backend-API-Tests.postman_collection.json`.  
   When prompted, allow **experimental script import** so test scripts (assertions) are imported.
3. **Import environment** (optional): Environments → **Import** → **Import from Postman** → choose `HTE-Backend-Local.postman_environment.json`.
4. Select the **HTE Backend (Local)** environment in the environment dropdown so `{{media_base}}`, `{{fact_base}}`, and `{{agent_base}}` resolve.

## What’s in the collection

| Request | Service | Purpose |
|--------|---------|--------|
| **Health check** | Agent | `GET /healthz` → expect `{ "status": "ok" }` |
| **Agent run (prompt only)** | Agent | `POST /v1/agent/run` with `api_key`, `prompt` → expect `trust_score`, `fake_facts`, `fake_media` |
| **Agent run (prompt + website_content)** | Agent | `POST /v1/agent/run` with `api_key`, `prompt`, `website_content` |
| **Agent run – invalid body (4xx)** | Agent | `POST /v1/agent/run` without `api_key` → expect 422 |
| **Health check** | Media | `GET /healthz` → expect `{ "status": "ok" }` |
| **Media check (image URL)** | Media | `POST /v1/media/check` with local sample `{{media_base}}/samples/sample.png` |
| **Deepfake check (video URL)** | Media | `POST /v1/deepfake/check` with local sample `{{media_base}}/samples/sample.mp4` (add `sample.mp4` to `media_checking/samples/` for video tests) |
| **Media check – missing media_url (400)** | Media | `POST /v1/media/check` with invalid body → expect 400 |
| **Health check** | Fact | `GET /healthz` → expect `{ "status": "ok" }` |
| **Fact check** | Fact | `POST /v1/fact/check` with a fact string → check response shape |

Each request has **tests** that run after the response (e.g. status code, required fields). Run a request and check the **Test Results** (or equivalent) panel to see pass/fail.

## Running tests

- Send each request manually and review the test results for that request.
- If you use a runner or CLI that supports Postman/Postman collections, you can run the whole collection against the **HTE Backend (Local)** environment.

## Variables

The collection and environment define:

- `media_base` = `http://localhost:8000` (Media Checking)
- `fact_base` = `http://localhost:8001` (Fact Checking)
- `agent_base` = `http://localhost:8003` (Agent Gateway)

Change these in the environment (or in the collection variables) to point at another host/port (e.g. staging).

## Media checking and local files

Media check requests use **local sample files** served by the Media Checking service at `GET /samples/<filename>`:

- **sample.png** is included in `media_checking/samples/` (minimal 1×1 PNG). The “Media check (image URL)” request uses `{{media_base}}/samples/sample.png`.
- For **video** tests, add your own `sample.mp4` to `media_checking/samples/`. The “Deepfake check (video URL)” request uses `{{media_base}}/samples/sample.mp4`. Rebuild the media_checking container after adding files so they are copied into the image, or mount the `samples` folder when running Docker.
