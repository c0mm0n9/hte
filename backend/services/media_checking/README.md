## AI Media Checking Service (Images & Video)

Python/FastAPI service that takes an **image or video URL**, downloads it, and calls Hive AI's **AI Image & Video Detection** model to detect **AI-generated media and deepfakes**. For videos, it chunks long inputs with FFmpeg and returns per‑chunk scores and labels.

### API

- **POST** `/v1/media/check` (primary) and `/v1/deepfake/check` (alias)
  - **Request body**
    ```json
    {
      "media_url": "https://example.com/media.mp4",
      "chunk_seconds": 10,
      "max_chunks": 100,
      "type_hint": "video"
    }
    ```
    - `media_url` (string, required): Publicly accessible URL to the image or video.
    - `chunk_seconds` (int, optional): Target chunk duration in seconds (videos only; defaults from env).
    - `max_chunks` (int, optional): Maximum number of chunks to process (videos only; defaults from env).
    - `type_hint` (string, optional): `"image"` or `"video"` to force behavior; otherwise the service auto-detects.
  - **Response body (shape)**
    ```json
    {
      "media_url": "https://example.com/media.mp4",
      "media_type": "video",
      "duration_seconds": 123.4,
      "chunk_seconds": 10,
      "provider": "hive_ai",
      "chunks": [
        {
          "index": 0,
          "start_seconds": 0.0,
          "end_seconds": 10.0,
          "ai_generated_score": 0.95,
          "deepfake_score": 0.1,
          "label": "ai_generated",
          "provider_raw": { "...": "Hive response for this chunk" }
        }
      ]
    }
    ```
    - `ai_generated_score`: Hive class score for `ai_generated` (0–1, may be `null` if missing).
    - `deepfake_score`: Hive class score for `deepfake` (0–1, may be `null`).
    - `label`: Derived label per chunk:
      - `"deepfake"`: `deepfake_score >= DEEPFAKE_DEEPFAKE_THRESHOLD`.
      - `"ai_generated"`: `ai_generated_score >= DEEPFAKE_AI_GENERATED_THRESHOLD`.
      - `"not_ai_generated"`: both scores low (≤ unlikely threshold).
      - `"unknown"`: anything else.

For **images**, the service returns a **single chunk**:

```json
{
  "media_url": "https://example.com/image.png",
  "media_type": "image",
  "duration_seconds": 0.0,
  "chunk_seconds": 0,
  "provider": "hive_ai",
  "chunks": [
    {
      "index": 0,
      "start_seconds": 0.0,
      "end_seconds": 0.0,
      "ai_generated_score": 0.97,
      "deepfake_score": 0.0,
      "label": "ai_generated",
      "provider_raw": { "...": "Hive response for this image" }
    }
  ]
}
```

- **GET** `/healthz`
  - Returns `{"status": "ok"}` when the service is healthy.

### Environment configuration

Env vars are read via `DEEPFAKE_` prefix (for historical reasons):

- **Chunking & limits**
  - `DEEPFAKE_CHUNK_SECONDS` (int, default `10`)
  - `DEEPFAKE_MAX_CHUNKS` (int, default `300`)
  - `DEEPFAKE_MAX_VIDEO_BYTES` (int, optional): Hard cap on downloaded video size.
  - `DEEPFAKE_MAX_DURATION_SECONDS` (int, optional): Reject videos longer than this many seconds.

- **Provider selection**
  - `DEEPFAKE_PROVIDER_NAME`:
    - `"hive_ai"` (default): Use Hive AI Image & Video Detection API.
    - `"local_sample"`: Use the sample local provider stub in `app/providers/local_sample.py`.

- **Hive AI settings**
  - `DEEPFAKE_HIVE_API_KEY` (string, required for `hive_ai`): Your Hive API key.
  - `DEEPFAKE_HIVE_TASK_SYNC_URL` (string, default `https://api.thehive.ai/api/v2/task/sync`)
  - `DEEPFAKE_HIVE_TIMEOUT_SECONDS` (float, default `60`)
  - `DEEPFAKE_HIVE_MAX_CONCURRENCY` (int, default `4`): Max concurrent chunk requests.

- **Label thresholds**
  - `DEEPFAKE_AI_GENERATED_THRESHOLD` (float, default `0.9`)
  - `DEEPFAKE_DEEPFAKE_THRESHOLD` (float, default `0.5`)
  - `DEEPFAKE_UNLIKELY_THRESHOLD` (float, default `0.2`)

### How Hive AI integration works

- Each chunk is sent to Hive via:
  - `POST https://api.thehive.ai/api/v2/task/sync`
  - Header: `Authorization: Token <DEEPFAKE_HIVE_API_KEY>`
  - Multipart form field: `media` = chunk bytes (`video/mp4`).
- The service parses the response, looking for the `ai_generated` and `deepfake` classes in the first `output[0].classes` array, then derives scores and a label per chunk.

### Local sample provider

To plug in your own local / self‑hosted detector:

1. Set `DEEPFAKE_PROVIDER_NAME=local_sample`.
2. Edit `app/providers/local_sample.py` to load your model and compute `ai_generated_score` / `deepfake_score` from each `VideoChunk`.
3. Return a `ChunkResult` instance; the shared label helper will compute a label based on your scores and thresholds.

This keeps the HTTP surface the same while letting you swap out the underlying detector.

### Running locally (without Docker)

```bash
cd backend/services/media_checking
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DEEPFAKE_HIVE_API_KEY="your_api_key_here"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker build & run

```bash
cd backend/services/media_checking

docker build -t ai-media-checker .

docker run --rm -p 8000:8000 \
  -e DEEPFAKE_HIVE_API_KEY="your_api_key_here" \
  ai-media-checker
```

Then call:

```bash
curl -X POST http://localhost:8000/v1/media/check \
  -H "Content-Type: application/json" \
  -d '{"media_url": "https://example.com/video.mp4"}'
```
