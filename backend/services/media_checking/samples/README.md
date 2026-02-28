# Sample media for API tests

- **sample.png** – Minimal 1×1 PNG. Used by Postman/collection requests that call `/v1/media/check` with a local file URL.
- **sample.mp4** – Optional. Add a small video file here to test `/v1/deepfake/check` with `{{media_base}}/samples/sample.mp4`.

The service serves these at `GET /samples/<filename>` so requests can use `media_url: "http://localhost:8000/samples/sample.png"` (or `{{media_base}}/samples/sample.png` in the collection).
