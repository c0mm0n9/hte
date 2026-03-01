# Dummy Validate Service

Dummy API key and validate endpoints for local/testing. Dockerized.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health check |
| GET | `/api_key` | Returns a dummy API key (`{ "api_key": "..." }`) |
| GET | `/validate/?api_key=<key>` | Validates key; same response shape as portal (`valid`, `mode`, optional `prompt`) |

## Run with Docker Compose

```bash
cd dummy-validate
docker compose up -d
```

- Service: `http://localhost:8080` (override with `PORT` in `.env`).

## Example

```bash
# Get a dummy key
curl http://localhost:8080/api_key

# Validate it
curl "http://localhost:8080/validate/?api_key=dummy-00000000-0000-0000-0000-000000000001-control"
```

## Environment (optional)

See `.env.example`. You can set `DUMMY_VALIDATE_KEYS` (comma-separated), `DUMMY_VALIDATE_MODE` (`control` \| `agentic`), and `DUMMY_VALIDATE_PROMPT`.
