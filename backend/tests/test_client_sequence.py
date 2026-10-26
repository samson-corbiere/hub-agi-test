"""The full upload sequence of the app, replayed with contract/example-session/."""

import hashlib
import subprocess

import pytest
from sqlalchemy import text

from capturekit.config import REPO_DIR

EXAMPLE_ID = "3f1c2a4e-8b7d-4c6a-9e2f-1a2b3c4d5e6f"


def upload_everything(client, meta, files):
    """What the app does: POST meta.json, then one PUT per declared file."""
    registration = client.post("/sessions", json=meta)
    puts = {
        name: client.put(
            f"/sessions/{meta['session_id']}/files/{name}",
            content=body,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Content-SHA256": hashlib.sha256(body).hexdigest(),
            },
        )
        for name, body in files.items()
    }
    return registration, puts


def test_example_session_upload_and_full_replay(client, db, data_dir, example_meta, example_files):
    registration, puts = upload_everything(client, example_meta, example_files)

    assert registration.status_code == 201
    assert {name: r.status_code for name, r in puts.items()} == dict.fromkeys(example_files, 201)

    rows = db.execute(text("SELECT * FROM session_files ORDER BY name")).mappings().all()
    declared = {f["name"]: f for f in example_meta["files"]}
    assert [(r["name"], r["status"], r["size"], r["sha256"]) for r in rows] == [
        (name, "received", declared[name]["size"], declared[name]["sha256"])
        for name in sorted(declared)
    ]
    assert all(r["received_at"] is not None for r in rows)

    session_dir = data_dir / "sessions" / EXAMPLE_ID
    assert sorted(p.name for p in session_dir.iterdir()) == sorted(example_files)
    for name, body in example_files.items():
        assert (session_dir / name).read_bytes() == body
    mtimes = {name: (session_dir / name).stat().st_mtime_ns for name in example_files}

    # The app replays everything (relaunch, background retries): nothing changes.
    replay_registration, replay_puts = upload_everything(client, example_meta, example_files)

    assert replay_registration.status_code == 200
    session = replay_registration.json()
    assert session["received_count"] == session["expected_count"] == 3
    assert session["complete"] is True
    assert {name: r.status_code for name, r in replay_puts.items()} == dict.fromkeys(
        example_files, 200
    )
    for name in example_files:
        assert replay_puts[name].json() == puts[name].json()
    assert db.execute(text("SELECT * FROM session_files ORDER BY name")).mappings().all() == rows
    assert sorted(p.name for p in session_dir.iterdir()) == sorted(example_files)
    for name, body in example_files.items():
        assert (session_dir / name).read_bytes() == body
        assert (session_dir / name).stat().st_mtime_ns == mtimes[name]


@pytest.mark.parametrize("directory", ["data", "backend/data"])
def test_default_data_directory_is_ignored_by_git(directory):
    # DATA_DIR defaults to ./data; the server runs from the repo root or from backend/.
    received = f"{directory}/sessions/{EXAMPLE_ID}/video.mp4"
    result = subprocess.run(["git", "check-ignore", "-q", received], cwd=REPO_DIR)
    assert result.returncode == 0, f"{received} is not ignored by git"
