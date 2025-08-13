# Smart Hospital API

A small Flask API for an IoT patient-vitals scenario (course assignment).  
Runs locally with SQLite; exposes REST endpoints for device registration and vital-sign ingestion plus basic read APIs. Includes simple idempotency for reliable POST retries.

---

## Features

- REST endpoints:
  - **POST** `/api/v1/devices/register` — register a device (issues per-device API key)
  - **POST** `/api/v1/patients/{patient_id}/vitals` — ingest vital-signs (idempotent)
  - **GET** `/api/v1/patients/{patient_id}/latest` — latest reading
  - **GET** `/api/v1/patients/{patient_id}/history` — paged history (`from`,`to`,`page`,`page_size`)
- Admin utilities (local dev):
  - **POST** `/admin/init-db` (or `GET ?confirm=yes`) — create tables + seed `p_001`
  - **GET** `/admin/db-path` — show SQLite file path
  - **GET** `/admin/routes` — list loaded routes
- CORS enabled
- `.env` support for config
- Idempotency via `Idempotency-Key` header to avoid duplicate inserts
- Includes `wsgi.py` for production WSGI servers (e.g., gunicorn/Azure)

---

## Requirements

- Python **3.9+**
- `pip`

All dependencies are in `requirements.txt`.


