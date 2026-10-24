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


def all_file_rows(db):
    return (
        db.execute(text("SELECT * FROM session_files ORDER BY session_id, name")).mappings().all()
    )


@pytest.mark.parametrize(
    "session_id",
    ["0b6f6a3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b", "not-a-uuid"],
    ids=["unknown uuid", "not a uuid"],
)
def test_unknown_session_is_not_found(client, db, data_dir, registered, example_files, session_id):
    files_before = all_file_rows(db)

    response = put_file(client, "imu.csv", example_files["imu.csv"], session_id=session_id)

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert all_file_rows(db) == files_before
    assert stored_files(data_dir) == {}


def test_unknown_session_wins_over_a_bad_name(client, data_dir):
    response = put_file(client, "evil.sh", b"x", session_id="0b6f6a3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b")

    assert response.status_code == 404
    assert stored_files(data_dir) == {}


@pytest.mark.parametrize("name", ["meta.json", "evil.sh", "VIDEO.MP4", "imu.csv.part", ".imu.csv"])
def test_name_not_an_uploaded_file_is_rejected(client, db, data_dir, registered, name):
    files_before = all_file_rows(db)

    response = put_file(client, name, b"payload")

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)
    assert all_file_rows(db) == files_before
    assert stored_files(data_dir) == {}


IMU_SHA = "e6877f3da50f05ed3807afc68ee413f7847fde736f8e444b9abfa42bb05e20d6"
MALFORMED_HEADERS = {
    "missing": None,
    "empty": "",
    "uppercase": IMU_SHA.upper(),
    "63 chars": IMU_SHA[:-1],
    "65 chars": IMU_SHA + "a",
    "not hex": "g" + IMU_SHA[1:],
}


@pytest.mark.parametrize("header", MALFORMED_HEADERS.values(), ids=MALFORMED_HEADERS.keys())
def test_missing_or_malformed_hash_header_is_rejected(
    client, db, data_dir, registered, example_files, header
):
    files_before = all_file_rows(db)
    headers = {"Content-Type": "application/octet-stream"}
    if header is not None:
        headers["X-Content-SHA256"] = header

    response = client.put(
        f"/sessions/{EXAMPLE_ID}/files/imu.csv", content=example_files["imu.csv"], headers=headers
    )

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)
    assert all_file_rows(db) == files_before
    assert stored_files(data_dir) == {}
