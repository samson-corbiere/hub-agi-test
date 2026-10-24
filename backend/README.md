# CaptureKit backend

FastAPI + Postgres ingest server for CaptureKit sessions. The API is specified in
[`docs/api-contract.md`](../docs/api-contract.md); `meta.json` bodies are validated
against [`contract/meta.schema.json`](../contract/meta.schema.json).

Implemented so far: `GET /health`, `POST /sessions`.

## Setup

From the repo root:

```sh
cp .env.example .env          # then set your own password
docker compose up -d postgres # Postgres on localhost:5433
```

Configuration is read from the environment, falling back to the repo-root `.env`:

| Variable | Used for |
|---|---|
| `DATABASE_URL` | The API and `alembic` |
| `TEST_DATABASE_URL` | The tests. Must name a database ending in `_test`: its schema is dropped and rebuilt on every test run. |
| `DATA_DIR` | Where received files are stored (not used yet) |

Compose creates both the dev database and `<POSTGRES_DB>_test` when its volume is first
created (`infra/postgres/init/`).

## Run

```sh
cd backend
uv sync
uv run alembic upgrade head   # apply migrations to DATABASE_URL
uv run uvicorn capturekit.app:create_app --factory --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` makes the API reachable from an iPhone on the same Wi-Fi at
`http://<mac-lan-ip>:8000` (on macOS: `ipconfig getifaddr en0`). macOS may ask to allow
incoming connections for Python the first time. Check it from the phone or another
machine:

```sh
curl http://<mac-lan-ip>:8000/health   # {"status":"ok"}
```

There is no authentication: run it on a trusted local network only.

## Test and lint

```sh
cd backend
uv run pytest
uv run ruff check . ../contract
uv run ruff format --check . ../contract
```

Tests go through the HTTP API only, against a real Postgres test database. The schema
is created by the Alembic migrations once per run, and every table is emptied before
each test.

## Migrations

Migrations live in `migrations/versions/`. Create a new one with:

```sh
uv run alembic revision -m "describe the change"
```
