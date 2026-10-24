# API contract

> **Owner-only.** This file, `contract/meta.schema.json` and `contract/example-session/` define what the app sends and what the backend accepts. Agents working on `app/` or `backend/` must not edit them. If the contract looks wrong, stop and raise it with the project owner.

Source of truth for the decisions: spec issue #1.

## Conventions

- Base URL: `http://<mac-lan-ip>:8000`. Plain HTTP on the local network only, no authentication (known limitation).
- JSON bodies use `Content-Type: application/json`. File bodies are raw bytes (`Content-Type: application/octet-stream`), never multipart.
- Errors return `{"detail": "<human-readable reason>"}`.
- All `*_t_ns` values are integers: nanoseconds on the device's monotonic host clock (time since boot). Video frame timestamps and IMU timestamps share this clock.
- Session ids are UUID v4 generated on the device when recording starts.

## Session files

| Name | Format |
|---|---|
| `video.mp4` | H.264, 1080×1920 portrait, 30 fps locked, no audio |
| `imu.csv` | Header `t_ns,ax,ay,az,gx,gy,gz`. Acceleration in m/s² including gravity, rotation rate in rad/s. ~100 Hz. Starts before the first frame, ends after the last. |
| `frames.csv` | Header `frame_index,t_ns`. One row per written frame, presentation timestamp. `frame_index` starts at 0. |
| `meta.json` | Defined by `contract/meta.schema.json`. Sent as the `POST /sessions` body; not uploaded as a file. |

Only `video.mp4`, `imu.csv` and `frames.csv` are uploaded with `PUT`. `contract/example-session/` is a complete, consistent example.

## Upload sequence

1. `POST /sessions` with `meta.json`.
2. Only after it succeeds (200 or 201): one `PUT` per file in `meta.files`, in any order or in parallel.
3. A session is complete when every declared file is `received`.

Every request may be replayed by the client (background URLSession retries, app relaunch). The server must make replays harmless.

## Endpoints

### `GET /health`

`200 {"status": "ok"}`

### `POST /sessions`

Body: `meta.json` (validated against the schema).

| Case | Response |
|---|---|
| New `session_id` | `201`, session object (see below). Creates one file row with status `expected` per entry in `files`. |
| Same `session_id`, identical body | `200`, session object. Nothing created or changed. |
| Same `session_id`, different body | `409` |
| Body fails the schema | `422` |

### `PUT /sessions/{session_id}/files/{name}`

Headers: `X-Content-SHA256: <lowercase hex SHA-256 of the body being sent>` (required), `Content-Length` (when known).
Body: raw file bytes.

The server streams the body to a temporary file while hashing it, never holding the whole file in memory. It moves the file into place atomically only when the computed hash equals both the `X-Content-SHA256` header and the hash declared for that name in `meta.json`.

Checks are applied in this order. The first matching row wins:

| Case | Response | File row after |
|---|---|---|
| `session_id` unknown | `404` | — |
| `name` not one of `video.mp4`, `imu.csv`, `frames.csv` | `400` | — |
| `X-Content-SHA256` missing or not 64 lowercase hex characters | `400` | unchanged |
| Body larger than 1 GB = 1 000 000 000 bytes (from `Content-Length`, or while streaming) | `413` | unchanged |
| File already `received`, computed hash equals the stored hash | `200`, file not rewritten | `received` |
| File already `received`, computed hash differs | `409`, stored file untouched | `received` |
| Computed hash differs from the header or from the declared hash | `422`, nothing kept on disk | `corrupt` |
| Computed hash equals both | `201` | `received`, with `size` and `received_at` |

A `corrupt` file can be uploaded again; a matching upload turns it `received`.

Response body for 200/201: the file object.

### `GET /sessions?limit=50&offset=0`

`200 {"items": [session, ...], "limit": 50, "offset": 0, "total": <int>}`, newest `created_at` first. `limit` is between 1 and 200 (default 50); `offset` ≥ 0.

### `GET /sessions/{session_id}`

`200` session object plus `"meta": { ...the stored meta.json... }`. Unknown id → `404`.

## Objects

Session:

```json
{
  "id": "3f1c2a4e-8b7d-4c6a-9e2f-1a2b3c4d5e6f",
  "created_at": "2026-10-24T17:30:00Z",
  "device_model": "iPhone16,1",
  "os_version": "26.1",
  "duration_s": 0.967,
  "files": [ file, ... ],
  "received_count": 2,
  "expected_count": 3,
  "complete": false
}
```

`duration_s = (video_end_t_ns - video_start_t_ns) / 1e9`. `complete` is true when `received_count == expected_count`.

File:

```json
{
  "name": "video.mp4",
  "size": 45366,
  "sha256": "<declared hash>",
  "status": "expected",
  "received_at": null
}
```

`status` is one of `expected`, `received`, `corrupt`. `size` is the declared size until the file is received, then the received size.

## Client error handling (app side)

| Outcome | App behaviour |
|---|---|
| Network error, `5xx` | Retry automatically, up to 3 attempts, then `failed` with a Retry action |
| `409`, `422`, other `4xx` | `failed` immediately, reason shown, no automatic retry |
