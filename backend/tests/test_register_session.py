"""POST /sessions: register a session from its meta.json (docs/api-contract.md)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text

from capturekit.app import create_app

EXAMPLE_ID = "3f1c2a4e-8b7d-4c6a-9e2f-1a2b3c4d5e6f"


def session_rows(db):
    return db.execute(text("SELECT * FROM sessions")).mappings().all()


def file_rows(db):
    return (
        db.execute(text("SELECT * FROM session_files ORDER BY session_id, name")).mappings().all()
    )


def test_example_session_is_registered(client, db, example_meta):
    response = client.post("/sessions", json=example_meta)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == EXAMPLE_ID
    assert body["device_model"] == "iPhone16,1"
    assert body["os_version"] == "26.1"
    assert body["duration_s"] == (5001090123446 - 5000123456789) / 1e9
    assert body["created_at"]
    assert body["received_count"] == 0
    assert body["expected_count"] == 3
    assert body["complete"] is False
    assert sorted(body["files"], key=lambda f: f["name"]) == [
        {
            "name": f["name"],
            "size": f["size"],
            "sha256": f["sha256"],
            "status": "expected",
            "received_at": None,
        }
        for f in sorted(example_meta["files"], key=lambda f: f["name"])
    ]

    [session] = session_rows(db)
    assert str(session["id"]) == EXAMPLE_ID
    assert session["platform"] == "ios"
    assert session["device_model"] == "iPhone16,1"
    assert session["os_version"] == "26.1"
    assert session["meta"] == example_meta
    assert session["created_at"] is not None

    files = file_rows(db)
    assert [(str(f["session_id"]), f["name"], f["size"], f["sha256"]) for f in files] == [
        (EXAMPLE_ID, f["name"], f["size"], f["sha256"])
        for f in sorted(example_meta["files"], key=lambda f: f["name"])
    ]
    assert all(f["status"] == "expected" and f["received_at"] is None for f in files)


def test_replaying_the_same_registration_changes_nothing(client, db, example_meta):
    first = client.post("/sessions", json=example_meta)
    sessions_before = session_rows(db)
    files_before = file_rows(db)

    replay = client.post("/sessions", json=example_meta)

    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert session_rows(db) == sessions_before
    assert file_rows(db) == files_before


def test_same_session_id_with_different_metadata_is_a_conflict(client, db, example_meta):
    client.post("/sessions", json=example_meta)
    sessions_before = session_rows(db)
    files_before = file_rows(db)
    changed = {**example_meta, "interrupted": True}

    response = client.post("/sessions", json=changed)

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    assert session_rows(db) == sessions_before
    assert file_rows(db) == files_before


def test_replay_is_recognised_for_numbers_postgres_normalises(client, db, example_meta):
    # jsonb stores 1.2345e22 as 12345000000000000000000: an exact comparison must not
    # mistake the identical replay for different metadata.
    intrinsics = example_meta["camera_intrinsics"]
    meta = {
        **example_meta,
        "camera_intrinsics": {
            **intrinsics,
            "matrix": [[1.2345e22, 0.0, 0.5], *intrinsics["matrix"][1:]],
        },
    }
    first = client.post("/sessions", json=meta)
    assert first.status_code == 201

    replay = client.post("/sessions", json=meta)

    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert len(session_rows(db)) == 1
    assert len(file_rows(db)) == 3


def without(meta, key):
    return {k: v for k, v in meta.items() if k != key}


def with_files(meta, files):
    return {**meta, "files": files}


INVALID_BODIES = {
    "missing required field": lambda m: without(m, "video_start_t_ns"),
    "unknown top-level field": lambda m: {**m, "extra": 1},
    "wrong type": lambda m: {**m, "fps": "30"},
    "session_id not a UUID v4": lambda m: {**m, "session_id": "not-a-uuid"},
    "unknown platform": lambda m: {**m, "platform": "android"},
    "unknown file name": lambda m: with_files(
        m, [*m["files"][:2], {"name": "evil.sh", "size": 1, "sha256": "0" * 64}]
    ),
    "extra unknown file": lambda m: with_files(
        m, [*m["files"], {"name": "evil.sh", "size": 1, "sha256": "0" * 64}]
    ),
    "path traversal in file name": lambda m: with_files(
        m, [*m["files"][:2], {**m["files"][2], "name": "../frames.csv"}]
    ),
    "duplicate file name": lambda m: with_files(m, [m["files"][0]] * 3),
    "missing file": lambda m: with_files(m, m["files"][:2]),
    "bad sha256": lambda m: with_files(m, [{**m["files"][0], "sha256": "ABC"}, *m["files"][1:]]),
    "negative size": lambda m: with_files(m, [{**m["files"][0], "size": -1}, *m["files"][1:]]),
    "not an object": lambda m: [m],
}


@pytest.mark.parametrize("make_body", INVALID_BODIES.values(), ids=INVALID_BODIES.keys())
def test_body_violating_the_schema_is_rejected(client, db, example_meta, make_body):
    response = client.post("/sessions", json=make_body(example_meta))

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert session_rows(db) == []
    assert file_rows(db) == []


# Bodies the JSON Schema accepts but Postgres cannot store. They must be a 422 (the app
# doesn't retry it), never a 5xx (the app retries a request that can never succeed).
UNSTORABLE_BODIES = {
    "NUL character in a string": lambda m: {**m, "device_model": "a\u0000b"},
    "integer above BIGINT": lambda m: with_files(
        m, [{**m["files"][0], "size": 2**63}, *m["files"][1:]]
    ),
    "integer above int64 in a timestamp": lambda m: {**m, "video_end_t_ns": 2**63},
}


@pytest.mark.parametrize("make_body", UNSTORABLE_BODIES.values(), ids=UNSTORABLE_BODIES.keys())
def test_body_postgres_cannot_store_is_rejected(client, db, example_meta, make_body):
    response = client.post("/sessions", json=make_body(example_meta))

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert session_rows(db) == []
    assert file_rows(db) == []


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_non_finite_number_is_rejected(client, db, example_meta, literal):
    # Python's JSON parser accepts these; JSON and jsonb do not.
    # The matrix entries are unbounded numbers, so only finiteness can reject them.
    intrinsics = example_meta["camera_intrinsics"]
    matrix = [["PLACEHOLDER", 0.0, 0.5], *intrinsics["matrix"][1:]]
    meta = {**example_meta, "camera_intrinsics": {**intrinsics, "matrix": matrix}}
    body = json.dumps(meta).replace('"PLACEHOLDER"', literal)

    response = client.post(
        "/sessions", content=body.encode(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert session_rows(db) == []


def test_unexpected_server_error_returns_json_detail(database_url, example_meta):
    # A database that can't be reached stands in for any unexpected failure.
    unreachable = make_url(database_url).set(port=1)
    app = create_app(database_url=unreachable.render_as_string(hide_password=False))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/sessions", json=example_meta)

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    assert isinstance(response.json()["detail"], str)


def test_body_that_is_not_json_is_rejected(client, db):
    response = client.post(
        "/sessions", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert session_rows(db) == []
