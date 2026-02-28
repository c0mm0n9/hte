## Fact Checking Service

FastAPI microservice that exposes a simple JSON API to fact-check a statement using **Exa Answer API** (web search + LLM with structured output).

### Endpoint

- **POST** `/v1/fact/check`
  - Request body:
    ```json
    {
      "fact": "The Eiffel Tower is in Berlin."
    }
    ```
  - Successful response:
    ```json
    {
      "truth_value": false,
      "explanation": "Short explanation of why this is false",
      "provider": "exa",
      "raw_provider_response": { "...": "raw Exa payload" }
    }
    ```

### Configuration

Copy `.env.example` to `.env` and fill in your Exa API key:

```bash
cp .env.example .env
```

Required: one of these for your Exa API key:

- `EXA_API_KEY` (recommended; matches [Exa docs](https://docs.exa.ai))
- `FACTCHECK_EXA_API_KEY`

Optional overrides:

- `FACTCHECK_PROVIDER` (default `exa`)
- `FACTCHECK_EXA_BASE_URL` (default `https://api.exa.ai`)
- `FACTCHECK_EXA_TIMEOUT_SECONDS` (default `30.0`)
- `FACTCHECK_EXA_ANSWER_INCLUDE_TEXT` (default `false`; set `true` to include full text in search results)

### Build and run with Docker

From `backend/services/fact_checking`:

```bash
docker build -t fact-checking-service .

docker run --rm -p 8001:8001 --env-file .env fact-checking-service
```

### Example request

```bash
curl -X POST "http://localhost:8001/v1/fact/check" \
  -H "Content-Type: application/json" \
  -d '{"fact": "The Eiffel Tower is in Paris."}'
```

