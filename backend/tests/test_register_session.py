"""POST /sessions: register a session from its meta.json (docs/api-contract.md)."""

from sqlalchemy import text

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
