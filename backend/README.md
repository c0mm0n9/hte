# Parents Portal Backend (Django)

This Django project provides the API for the parents portal. It does **not** include the detection services in `services/` (those run in Docker and are used by the extension/API gateway).

## Setup

```bash
cd hte/backend
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional, for admin access
```

## Run

```bash
python manage.py runserver
```

- API base: http://localhost:8000
- Admin: http://localhost:8000/admin/
- Portal API: http://localhost:8000/api/portal/

## Portal API

- `GET /api/portal/dashboard/` — Dashboard data (devices + recent visited sites with detection flags)
- `GET /api/portal/devices/` — List devices (authenticated parent only)
- `POST /api/portal/devices/` — Add a device. Body: `{ "label", "device_type": "control"|"agentic", "agentic_prompt?" }` (agentic_prompt required when device_type is agentic)
- `DELETE /api/portal/devices/<device_id>/` — Remove a device (only if it belongs to the parent)
- `GET /api/portal/visited-sites/` — All visited sites (parent’s devices only)
- `GET /api/portal/visited-sites/<device_id>/` — Visited sites for one device
- `POST /api/portal/record-visit/` — Record a visit (for extension/gateway). Body: `{ "device_id" (int or uuid string), "url", "title?", "ai_detected?", "fake_news_detected?", "harmful_content_detected?" }`

Parents add/remove **devices** from the portal. Each device has: label, generated UUID, type (control = predetermined settings TBD; agentic = parent-defined prompt for agentic AI). Use the extension with the device UUID or POST to `record-visit/` to log visits.
