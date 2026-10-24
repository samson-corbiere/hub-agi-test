# CaptureKit

[![CI](https://github.com/samson-corbiere/hub-agi-test/actions/workflows/ci.yml/badge.svg)](https://github.com/samson-corbiere/hub-agi-test/actions/workflows/ci.yml)

Synchronized video + IMU capture on iPhone, uploaded reliably in the background.

CaptureKit records first-person video and motion-sensor data on one clock, the kind of data used to train robots on real-world behaviour. A React Native app provides the UI. All capture, storage and upload is native Swift, exposed to React Native through an Expo module. A FastAPI + Postgres backend receives sessions and verifies every file end to end.

> Status: in progress. See the [spec](https://github.com/samson-corbiere/hub-agi-test/issues/1) and its tickets.

## What a session contains

| File | Content |
|---|---|
| `video.mp4` | H.264, 1080p portrait, 30 fps locked, stabilization off, no audio |
| `imu.csv` | `t_ns,ax,ay,az,gx,gy,gz`: acceleration (m/s², incl. gravity) and rotation rate (rad/s) at ~100 Hz |
| `frames.csv` | `frame_index,t_ns`: presentation timestamp of every written frame |
| `meta.json` | device, OS, fps, resolution, camera intrinsics, time ranges, file sizes and SHA-256 |

Every `t_ns` is nanoseconds on the phone's monotonic clock, shared by frames and IMU samples. The exact format is in [`contract/`](contract/) and [`docs/api-contract.md`](docs/api-contract.md).

## Layout

```
app/                     React Native (Expo dev build), UI only
  modules/capture/       Expo module in Swift: capture, storage, upload
    ios/CaptureCore/     Pure Swift package with all the logic, tested with `swift test`
backend/                 FastAPI + SQLAlchemy + Alembic, pytest, ruff
contract/                Shared JSON Schema + example session (owner-only)
docs/                    API contract, ADRs, testing procedures
infra/                   Docker Compose support files
```

## Running locally

Requirements: Xcode, Node, Docker, [uv](https://docs.astral.sh/uv/), ffmpeg (only to regenerate the example session).

```sh
cp .env.example .env              # then edit the password
docker compose up -d --wait       # Postgres on port 5433 (dev + test databases)

cd backend && uv sync && uv run pytest     # backend + contract tests
cd app/modules/capture/ios/CaptureCore && swift test
```

App and API run instructions arrive with their tickets.

## Known limitations

- iOS only.
- Single-request uploads, so recordings are capped at 10 minutes (~750 MB).
- Local network only: plain HTTP to the Mac's LAN IP, no authentication.

## Next steps

- Android (Kotlin, CameraX, SensorManager, WorkManager).
- Chunked, resumable uploads that survive force-quit, for multi-GB recordings.
- ARKit depth and 3D pose.
- Authentication.
- Separate raw accelerometer and gyroscope streams.
- Full iOS build in CI.

## License

[MIT](LICENSE)
