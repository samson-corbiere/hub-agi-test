"""Regenerate contract/example-session/ (owner-only).

Produces a 1 s, 30-frame portrait H.264 video, matching frames.csv, a 100 Hz
imu.csv that starts 50 ms before the first frame and ends 50 ms after the last,
and a meta.json whose sizes and SHA-256 are computed from the written files.

Requires ffmpeg. Run from the backend project:
    uv run python ../contract/tools/make_example_session.py
"""

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "example-session"

SESSION_ID = "3f1c2a4e-8b7d-4c6a-9e2f-1a2b3c4d5e6f"
FPS = 30
FRAME_COUNT = 30
WIDTH, HEIGHT = 1080, 1920
IMU_RATE_HZ = 100
# Arbitrary but realistic "time since boot" (~1 h 23 min) so values aren't trivially small.
VIDEO_START_T_NS = 5_000_123_456_789
FRAME_INTERVAL_NS = 1_000_000_000 // FPS
IMU_INTERVAL_NS = 1_000_000_000 // IMU_RATE_HZ
IMU_MARGIN_NS = 50_000_000


def write_video(path: Path) -> None:
    # fmt: off
    args = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={FPS}",
        "-frames:v", str(FRAME_COUNT),
        "-c:v", "libx264", "-preset", "veryslow", "-crf", "45", "-pix_fmt", "yuv420p",
        "-an", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
        str(path),
    ]
    # fmt: on
    subprocess.run(args, check=True)


def frame_times() -> list[int]:
    return [VIDEO_START_T_NS + i * FRAME_INTERVAL_NS for i in range(FRAME_COUNT)]


def imu_times(video_start: int, video_end: int) -> list[int]:
    t, end, times = video_start - IMU_MARGIN_NS, video_end + IMU_MARGIN_NS, []
    while t <= end:
        times.append(t)
        t += IMU_INTERVAL_NS
    return times


def imu_row(t_ns: int, t0: int) -> list[str]:
    # Phone held upright and gently rotating about its vertical axis.
    s = (t_ns - t0) / 1e9
    ax, ay, az = 0.05 * math.sin(2 * math.pi * s), -9.81, 0.02
    gx, gy, gz = 0.0, 0.5 * math.sin(2 * math.pi * 0.5 * s), 0.0
    return [str(t_ns)] + [f"{v:.6f}" for v in (ax, ay, az, gx, gy, gz)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_video(OUT / "video.mp4")

    frames = frame_times()
    with (OUT / "frames.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["frame_index", "t_ns"])
        w.writerows([i, t] for i, t in enumerate(frames))

    imu = imu_times(frames[0], frames[-1])
    with (OUT / "imu.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["t_ns", "ax", "ay", "az", "gx", "gy", "gz"])
        w.writerows(imu_row(t, imu[0]) for t in imu)

    meta = {
        "session_id": SESSION_ID,
        "platform": "ios",
        "device_model": "iPhone16,1",
        "os_version": "26.1",
        "fps": FPS,
        "resolution": {"width": WIDTH, "height": HEIGHT},
        "camera_intrinsics": {
            "matrix": [[1480.5, 0.0, 539.5], [0.0, 1480.5, 959.5], [0.0, 0.0, 1.0]],
            "reference_width": WIDTH,
            "reference_height": HEIGHT,
        },
        "video_start_t_ns": frames[0],
        "video_end_t_ns": frames[-1],
        "frame_count": len(frames),
        "imu_start_t_ns": imu[0],
        "imu_end_t_ns": imu[-1],
        "imu_rate_hz": IMU_RATE_HZ,
        "imu_sample_count": len(imu),
        "interrupted": False,
        "files": [
            {"name": n, "size": (OUT / n).stat().st_size, "sha256": sha256(OUT / n)}
            for n in ("video.mp4", "imu.csv", "frames.csv")
        ],
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
