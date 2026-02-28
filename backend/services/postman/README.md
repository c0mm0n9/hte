# Postman API tests for HTE backend

Use these files in [Postman] to test all backend AI service containers.

## Collections

| File | Description |
|------|-------------|
| **HTE-All-AI-Services.postman_collection.json** | **Recommended.** Single collection with all AI services and Postman tests for every request. |
| HTE-Backend-API-Tests.postman_collection.json | Legacy: Agent Gateway, Media Checking, Fact Checking only (no AI Text Detector or Info Graph). |

## Prerequisites

1. Backend containers running, e.g.:
   ```bash
   cd backend/services
   docker compose up -d
   ```
2. Service URLs (default with Docker):
   - **Media Checking** → `http://localhost:8000`
   - **Fact Checking** → `http://localhost:8001` (ensure `fact_checking/.env` has provider API keys for fact-check requests)
   - **AI Text Detector** → `http://localhost:8002` (ensure `ai_text_detector/.env` has provider API keys)
   - **Agent Gateway** → `http://localhost:8003` (ensure `agent_gateway/.env` has LLM and service URLs; set `AGENT_GATEWAY_ALLOWED_API_KEYS=test-key` for test requests, or leave empty to skip key validation)
   - **Info Graph** → `http://localhost:8004` (ensure `info_graph/.env` has provider API keys)

## Import into Postman

1. Open Postman (app or web).
2. **Import collection**: Collections → **Import** → **Import from Postman** → choose `HTE-All-AI-Services.postman_collection.json`.  
   When prompted, allow **experimental script import** so test scripts (assertions) are imported.
3. **Import environment** (optional): Environments → **Import** → **Import from Postman** → choose `HTE-Backend-Local.postman_environment.json`.
4. Select the **HTE Backend (Local)** environment so `{{media_base}}`, `{{fact_base}}`, `{{ai_text_detector_base}}`, `{{agent_base}}`, and `{{info_graph_base}}` resolve.

## What’s in HTE-All-AI-Services

Every request has **tests** (status code and response shape). Run a request and check the **Test Results** panel.

| Folder | Requests | Purpose |
|--------|----------|--------|
| **Agent Gateway Service** | Health check; Agent run (prompt only); Agent run (prompt + website_content); Agent run – invalid body (4xx) | `GET /healthz`, `POST /v1/agent/run` |
| **Media Checking Service** | Health check; Media check (image URL); Deepfake check (video URL); Media/Deepfake upload; Invalid body (4xx) | `GET /healthz`, `POST /v1/media/check`, `POST /v1/deepfake/check`, upload variants |
| **Fact Checking Service** | Health check; Fact check | `GET /healthz`, `POST /v1/fact/check` |
| **AI Text Detector Service** | Health check; POST ai-detect (success, short text); POST ai-detect (empty/whitespace/missing – 400/422) | `GET /healthz`, `POST /v1/ai-detect` |
| **Info Graph Service** | Health check; Build info graph; Build – invalid body (422) | `GET /healthz`, `POST /v1/info-graph/build` |

## Running tests

- Send each request manually and review the test results for that request.
- Or run the whole collection: Collection → **Run** → choose **HTE All AI Services** and **HTE Backend (Local)** → Run. All requests run in sequence and tests are reported.

## Variables

The collection and environment define:

- `media_base` = `http://localhost:8000` (Media Checking)
- `fact_base` = `http://localhost:8001` (Fact Checking)
- `ai_text_detector_base` = `http://localhost:8002` (AI Text Detector)
- `agent_base` = `http://localhost:8003` (Agent Gateway)
- `info_graph_base` = `http://localhost:8004` (Info Graph)

Change these in the environment to point at another host/port (e.g. staging).

## Media checking and local files

Media check requests use **local sample files** served by the Media Checking service at `GET /samples/<filename>`:

- **sample.png** is included in `media_checking/samples/` (minimal 1×1 PNG). The “Media check (image URL)” request uses `{{media_base}}/samples/sample.png`.
- For **video** tests, add your own `sample.mp4` to `media_checking/samples/`. Rebuild the media_checking container after adding files, or mount the `samples` folder when running Docker.

Upload requests (Media check – upload image file, Deepfake check – upload video file) require you to set the file path in the request body to a local file on your machine.
