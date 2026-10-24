"""PUT /sessions/{session_id}/files/{name}: receive a session file (docs/api-contract.md)."""

import hashlib

import pytest
from sqlalchemy import text

EXAMPLE_ID = "3f1c2a4e-8b7d-4c6a-9e2f-1a2b3c4d5e6f"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_file(client, name, body, *, sha=None, session_id=EXAMPLE_ID, headers=None):
    headers = {
        "Content-Type": "application/octet-stream",
        "X-Content-SHA256": sha if sha is not None else sha256(body),
        **(headers or {}),
    }
    return client.put(f"/sessions/{session_id}/files/{name}", content=body, headers=headers)


def file_row(db, name, session_id=EXAMPLE_ID):
    return (
        db.execute(
            text("SELECT * FROM session_files WHERE session_id = :id AND name = :name"),
            {"id": session_id, "name": name},
        )
        .mappings()
        .one()
    )


def stored_files(data_dir):
    """Every file under DATA_DIR, as {relative path: bytes}."""
    if not data_dir.exists():
        return {}
    return {
        str(path.relative_to(data_dir)): path.read_bytes()
        for path in data_dir.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def registered(client, example_meta):
    response = client.post("/sessions", json=example_meta)
    assert response.status_code == 201
    return example_meta


@pytest.mark.parametrize("name", ["video.mp4", "imu.csv", "frames.csv"])
def test_valid_file_is_received(client, db, data_dir, registered, example_files, name):
    body = example_files[name]

    response = put_file(client, name, body)

    assert response.status_code == 201
    result = response.json()
    assert result["name"] == name
    assert result["size"] == len(body)
    assert result["sha256"] == sha256(body)
    assert result["status"] == "received"
    assert result["received_at"]

    row = file_row(db, name)
    assert row["status"] == "received"
    assert row["size"] == len(body)
    assert row["received_at"] is not None

    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/{name}": body}
