# Parents Portal Backend (Django)

This Django project provides the API for the parents portal. It does **not** include the detection services in `services/` (those run in Docker and are used by the extension/API gateway).

The app uses **PostgreSQL** when `POSTGRES_DB` is set (e.g. via `.env`); otherwise it falls back to SQLite for local dev.

## Database: PostgreSQL in Docker

To run PostgreSQL in Docker and persist data:

```bash
cd hte/backend
cp .env.example .env
# Edit .env and set POSTGRES_PASSWORD if you want something other than 'postgres'

docker compose up -d
```

This starts Postgres 16 with a volume `postgres_data`. Connection defaults (from `.env.example`): database `hte`, user `postgres`, host `localhost`, port `5432`.

Then run migrations and start Django (see below). Django will connect using the `POSTGRES_*` variables from `.env`.

To stop the database: `docker compose down`. Data is kept in the volume. To remove data too: `docker compose down -v`.

## Setup

```bash
cd hte/backend
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
# If using Postgres: ensure .env is set (or export POSTGRES_DB=hte etc.) so Django uses PostgreSQL
python manage.py migrate
python manage.py createsuperuser   # optional, for admin access
```

## Run

```bash
python manage.py runserver
```

- API base: http://127.0.0.1:8000 (use 127.0.0.1; on some systems `localhost` resolves to IPv6 and Django may be unreachable)
- Admin: http://127.0.0.1:8000/admin/
- Portal API: http://127.0.0.1:8000/api/portal/

**Port 8000**: This Django app uses port 8000. The FastAPI services in `services/` (Media Checking, Agent Gateway, etc.) use other ports (8001–8004) when running locally or in Docker so they do not conflict.

## Portal API

- `GET /api/portal/dashboard/` — Dashboard data (devices + recent visited sites with detection flags)
- `GET /api/portal/devices/` — List devices (authenticated parent only)
- `POST /api/portal/devices/` — Add a device. Body: `{ "label", "device_type": "control"|"agentic", "agentic_prompt?" }` (agentic_prompt required when device_type is agentic)
- `DELETE /api/portal/devices/<device_id>/` — Remove a device (only if it belongs to the parent)
- `GET /api/portal/visited-sites/` — All visited sites (parent’s devices only)
- `GET /api/portal/visited-sites/<device_id>/` — Visited sites for one device
- `POST /api/portal/record-visit/` — Record a visit (for extension/gateway). Body: `{ "device_id" (int or uuid string), "url", "title?", "ai_detected?", "fake_news_detected?", "harmful_content_detected?" }`

Parents add/remove **devices** from the portal. Each device has: label, generated UUID, type (control = predetermined settings TBD; agentic = parent-defined prompt for agentic AI). Use the extension with the device UUID or POST to `record-visit/` to log visits.
