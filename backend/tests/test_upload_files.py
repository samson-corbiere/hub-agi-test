"""PUT /sessions/{session_id}/files/{name}: receive a session file (docs/api-contract.md)."""

import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from capturekit.app import create_app

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


def damaged(body: bytes) -> bytes:
    """The same bytes with the last one flipped, as a garbled transfer."""
    return body[:-1] + bytes([body[-1] ^ 0xFF])


def corrupt_upload(client, name, body):
    """Upload bytes that don't match the header (the header is the real file's hash)."""
    return put_file(client, name, damaged(body), sha=sha256(body))


def test_body_not_matching_the_header_is_corrupt(client, db, data_dir, registered, example_files):
    body = example_files["video.mp4"]

    response = corrupt_upload(client, "video.mp4", body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    row = file_row(db, "video.mp4")
    assert row["status"] == "corrupt"
    assert row["received_at"] is None
    assert stored_files(data_dir) == {}


def test_body_not_matching_the_declared_hash_is_corrupt(client, db, data_dir, registered):
    # Self-consistent upload (header == body hash), but not the file meta.json declared.
    other = b"frame_index,t_ns\n0,1\n"

    response = put_file(client, "frames.csv", other)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert file_row(db, "frames.csv")["status"] == "corrupt"
    assert stored_files(data_dir) == {}


def test_corrupt_file_can_be_uploaded_again(client, db, data_dir, registered, example_files):
    body = example_files["imu.csv"]
    assert corrupt_upload(client, "imu.csv", body).status_code == 422

    response = put_file(client, "imu.csv", body)

    assert response.status_code == 201
    assert response.json()["status"] == "received"
    row = file_row(db, "imu.csv")
    assert row["status"] == "received"
    assert row["size"] == len(body)
    assert row["received_at"] is not None
    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/imu.csv": body}


def stored_path(data_dir, name, session_id=EXAMPLE_ID):
    return data_dir / "sessions" / session_id / name


def test_replaying_a_received_file_does_not_rewrite_it(
    client, db, data_dir, registered, example_files
):
    body = example_files["video.mp4"]
    first = put_file(client, "video.mp4", body)
    assert first.status_code == 201
    row_before = file_row(db, "video.mp4")
    stat_before = stored_path(data_dir, "video.mp4").stat()

    replay = put_file(client, "video.mp4", body)

    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert file_row(db, "video.mp4") == row_before
    stat_after = stored_path(data_dir, "video.mp4").stat()
    assert (stat_after.st_ino, stat_after.st_mtime_ns) == (
        stat_before.st_ino,
        stat_before.st_mtime_ns,
    )
    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/video.mp4": body}


def test_different_content_for_a_received_file_is_a_conflict(
    client, db, data_dir, registered, example_files
):
    body = example_files["frames.csv"]
    assert put_file(client, "frames.csv", body).status_code == 201
    row_before = file_row(db, "frames.csv")
    stat_before = stored_path(data_dir, "frames.csv").stat()

    response = put_file(client, "frames.csv", b"frame_index,t_ns\n0,1\n")

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    assert file_row(db, "frames.csv") == row_before
    assert stored_path(data_dir, "frames.csv").stat().st_mtime_ns == stat_before.st_mtime_ns
    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/frames.csv": body}


def test_garbled_replay_of_a_received_file_is_a_conflict(
    client, db, data_dir, registered, example_files
):
    # Checks are ordered: "already received, hash differs" wins over "corrupt".
    body = example_files["imu.csv"]
    assert put_file(client, "imu.csv", body).status_code == 201
    row_before = file_row(db, "imu.csv")

    response = corrupt_upload(client, "imu.csv", body)

    assert response.status_code == 409
    assert file_row(db, "imu.csv") == row_before
    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/imu.csv": body}


# The real limit is 1 GB; tests lower it so they never send that much. The example's
# imu.csv is exactly at this limit and video.mp4 is above it.
SMALL_LIMIT = 7462


@pytest.fixture
def small_limit_client(database_url, db, data_dir):
    app = create_app(database_url=database_url, data_dir=data_dir, max_file_size=SMALL_LIMIT)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("content_length", "expected_status"),
    [(1_000_000_001, 413), (1_000_000_000, 201)],
    ids=["1 GB + 1 byte", "exactly 1 GB"],
)
def test_default_limit_is_one_gigabyte(
    client, registered, example_files, content_length, expected_status
):
    # Only the declared Content-Length is large: the test client doesn't check it against
    # the body, so the default limit is exercised without sending a gigabyte.
    body = example_files["frames.csv"]

    response = put_file(client, "frames.csv", body, headers={"Content-Length": str(content_length)})

    assert response.status_code == expected_status


def test_body_over_the_limit_is_rejected(
    small_limit_client, db, data_dir, registered, example_files
):
    files_before = all_file_rows(db)

    response = put_file(small_limit_client, "video.mp4", example_files["video.mp4"])

    assert response.status_code == 413
    assert isinstance(response.json()["detail"], str)
    assert all_file_rows(db) == files_before
    assert stored_files(data_dir) == {}


def test_body_at_the_limit_is_accepted(small_limit_client, registered, example_files):
    body = example_files["imu.csv"]
    assert len(body) == SMALL_LIMIT

    response = put_file(small_limit_client, "imu.csv", body)

    assert response.status_code == 201


def test_body_over_the_limit_without_content_length_is_rejected(
    small_limit_client, db, data_dir, registered, example_files
):
    # A generator body is sent with chunked transfer encoding: no Content-Length, so the
    # limit can only be enforced while streaming.
    body = example_files["video.mp4"]

    def chunks():
        for start in range(0, len(body), 1024):
            yield body[start : start + 1024]

    response = small_limit_client.put(
        f"/sessions/{EXAMPLE_ID}/files/video.mp4",
        content=chunks(),
        headers={"X-Content-SHA256": sha256(body)},
    )

    assert response.status_code == 413
    assert file_row(db, "video.mp4")["status"] == "expected"
    assert stored_files(data_dir) == {}


def test_size_limit_is_checked_before_already_received(
    small_limit_client, db, data_dir, registered, example_files
):
    body = example_files["imu.csv"]
    assert put_file(small_limit_client, "imu.csv", body).status_code == 201
    row_before = file_row(db, "imu.csv")

    response = put_file(small_limit_client, "imu.csv", body + b"0")

    assert response.status_code == 413
    assert file_row(db, "imu.csv") == row_before
    assert stored_files(data_dir) == {f"sessions/{EXAMPLE_ID}/imu.csv": body}


# --- Streaming, over a real HTTP server (see the live_server fixture) ---

CHUNK = 64 * 1024


def big_body(size: int) -> bytes:
    return bytes(range(256)) * (size // 256)


def register_with_video(base_url, example_meta, video: bytes) -> str:
    """Register a new session whose video.mp4 is `video`; returns its id."""
    session_id = str(uuid.uuid4())
    files = [
        {"name": "video.mp4", "size": len(video), "sha256": sha256(video)}
        if f["name"] == "video.mp4"
        else f
        for f in example_meta["files"]
    ]
    meta = {**example_meta, "session_id": session_id, "files": files}
    response = httpx2.post(f"{base_url}/sessions", json=meta)
    assert response.status_code == 201
    return session_id


def wait_until(condition, timeout=10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def bytes_being_received(session_dir) -> int:
    """Total size of the temporary files the server is writing in session_dir."""
    if not session_dir.exists():
        return 0
    return sum(p.stat().st_size for p in session_dir.iterdir() if p.name != "video.mp4")


def test_body_is_written_to_disk_while_it_is_still_arriving(
    live_server, db, data_dir, example_meta
):
    # The client stops after sending half of the body and waits to see those bytes on
    # disk before sending the rest. A server that read the whole body before writing it
    # would never get there: the second half doesn't exist yet.
    base_url = live_server()
    body = big_body(4 * 1024 * 1024)
    session_id = register_with_video(base_url, example_meta, body)
    session_dir = data_dir / "sessions" / session_id
    half = len(body) // 2
    seen_on_disk = []

    def chunks():
        for start in range(0, half, CHUNK):
            yield body[start : start + CHUNK]
        assert wait_until(lambda: bytes_being_received(session_dir) >= half - CHUNK), (
            "the first half of the body never reached the disk"
        )
        seen_on_disk.append(bytes_being_received(session_dir))
        for start in range(half, len(body), CHUNK):
            yield body[start : start + CHUNK]

    response = httpx2.put(
        f"{base_url}/sessions/{session_id}/files/video.mp4",
        content=chunks(),
        headers={"X-Content-SHA256": sha256(body)},
        timeout=30,
    )

    assert response.status_code == 201
    assert half - CHUNK <= seen_on_disk[0] < len(body)
    assert file_row(db, "video.mp4", session_id)["status"] == "received"
    assert stored_files(data_dir) == {f"sessions/{session_id}/video.mp4": body}


def test_endless_body_is_cut_off_at_the_limit(live_server, db, data_dir, registered_live):
    # A body with no Content-Length and no end: the server must stop reading it once it
    # passes the limit, instead of reading (or holding) it whole.
    base_url, session_id = registered_live(max_file_size=1024 * 1024)
    sent = 0
    give_up = 256 * 1024 * 1024

    def endless():
        nonlocal sent
        chunk = b"\0" * CHUNK
        while sent < give_up:
            sent += len(chunk)
            yield chunk

    response = httpx2.put(
        f"{base_url}/sessions/{session_id}/files/video.mp4",
        content=endless(),
        headers={"X-Content-SHA256": "0" * 64},
        timeout=30,
    )

    assert response.status_code == 413
    assert sent < give_up // 4
    assert file_row(db, "video.mp4", session_id)["status"] == "expected"
    assert wait_until(lambda: stored_files(data_dir) == {})


def test_interrupted_upload_leaves_nothing_on_disk(live_server, db, data_dir, registered_live):
    base_url, session_id = registered_live()
    session_dir = data_dir / "sessions" / session_id

    def interrupted():
        yield b"\0" * CHUNK
        assert wait_until(lambda: bytes_being_received(session_dir) > 0)
        raise ConnectionAbortedError("the app was killed mid-upload")

    with pytest.raises(ConnectionAbortedError):
        httpx2.put(
            f"{base_url}/sessions/{session_id}/files/video.mp4",
            content=interrupted(),
            headers={"X-Content-SHA256": "0" * 64},
            timeout=30,
        )

    assert wait_until(lambda: stored_files(data_dir) == {}), stored_files(data_dir).keys()
    assert file_row(db, "video.mp4", session_id)["status"] == "expected"


@pytest.fixture
def registered_live(live_server, example_meta):
    """Start a live server and register the example session on it."""

    def start(**options):
        base_url = live_server(**options)
        response = httpx2.post(f"{base_url}/sessions", json=example_meta)
        assert response.status_code == 201
        return base_url, EXAMPLE_ID

    return start


# --- Concurrent uploads of the same file ---
# Retries can overlap (a URLSession retry while the first attempt is still running). To
# make requests overlap for sure, the test locks the file's row itself, lets the uploads
# stream their bodies and queue up behind that lock, then releases it.


class RowLock:
    """A lock on one session_files row, held by the test on its own connection."""

    def __init__(self, conn, session_id, name):
        self.conn = conn
        conn.execute(
            text("SELECT 1 FROM session_files WHERE session_id = :id AND name = :name FOR UPDATE"),
            {"id": session_id, "name": name},
        )
        self.pid = conn.scalar(text("SELECT pg_backend_pid()"))

    def waiters(self, engine) -> int:
        """How many backends are queued, directly or not, behind this lock.

        Only backends blocked by this test's connection count, so other tests running
        against the same database don't disturb it.
        """
        with engine.connect() as conn:
            return conn.scalar(
                text(
                    "WITH RECURSIVE blocked(pid) AS ("
                    "  SELECT pid FROM pg_stat_activity"
                    "  WHERE CAST(:pid AS int) = ANY(pg_blocking_pids(pid))"
                    "  UNION"
                    "  SELECT a.pid FROM pg_stat_activity a, blocked b"
                    "  WHERE b.pid = ANY(pg_blocking_pids(a.pid))"
                    ") SELECT count(*) FROM blocked"
                ),
                {"pid": self.pid},
            )

    def release(self):
        self.conn.rollback()


def queue_uploads(engine, session_id, name, uploads):
    """Run the uploads (callables) so they all wait on the file's row, queued in order.

    Postgres hands a row lock to its waiters first come, first served, so each upload is
    started only once the previous one is queued. Returns their responses, in order.
    """
    with engine.connect() as conn, ThreadPoolExecutor(len(uploads)) as pool:
        lock = RowLock(conn, session_id, name)
        pending = []
        for queued, upload in enumerate(uploads, start=1):
            pending.append(pool.submit(upload))
            if not wait_until(lambda n=queued: lock.waiters(engine) == n):
                lock.release()
                pytest.fail(f"upload {queued} never queued up behind the row lock")
        lock.release()
        return [future.result() for future in pending]


def uploader(base_url, session_id, name, body, sha=None):
    def upload():
        return httpx2.put(
            f"{base_url}/sessions/{session_id}/files/{name}",
            content=body,
            headers={"X-Content-SHA256": sha or sha256(body)},
            timeout=30,
        )

    return upload


def test_concurrent_identical_uploads_store_the_file_once(
    registered_live, engine, db, data_dir, example_files
):
    base_url, session_id = registered_live()
    body = example_files["video.mp4"]
    upload = uploader(base_url, session_id, "video.mp4", body)

    responses = queue_uploads(engine, session_id, "video.mp4", [upload] * 4)

    assert [r.status_code for r in responses] == [201, 200, 200, 200]
    assert len({r.json()["received_at"] for r in responses}) == 1
    row = file_row(db, "video.mp4", session_id)
    assert row["status"] == "received"
    assert row["size"] == len(body)
    assert stored_files(data_dir) == {f"sessions/{session_id}/video.mp4": body}


@pytest.mark.parametrize(
    ("first", "expected_statuses"),
    [("corrupt", [422, 201]), ("good", [201, 409])],
    ids=["corrupt first", "good first"],
)
def test_corrupt_upload_racing_a_good_one(
    registered_live, engine, db, data_dir, example_files, first, expected_statuses
):
    base_url, session_id = registered_live()
    body = example_files["imu.csv"]
    good = uploader(base_url, session_id, "imu.csv", body)
    corrupt = uploader(base_url, session_id, "imu.csv", damaged(body), sha=sha256(body))
    order = [corrupt, good] if first == "corrupt" else [good, corrupt]

    responses = queue_uploads(engine, session_id, "imu.csv", order)

    assert [r.status_code for r in responses] == expected_statuses
    row = file_row(db, "imu.csv", session_id)
    assert row["status"] == "received"
    assert row["size"] == len(body)
    assert stored_files(data_dir) == {f"sessions/{session_id}/imu.csv": body}


@pytest.mark.parametrize(
    ("first", "expected_statuses"),
    [("other", [422, 201]), ("declared", [201, 409])],
    ids=["other content first", "declared content first"],
)
def test_concurrent_uploads_with_different_content(
    registered_live, engine, db, data_dir, example_files, first, expected_statuses
):
    # Both requests are self-consistent (header == body hash). Only the content meta.json
    # declared can be stored: other content is corrupt (422) before the declared file
    # arrives, and a conflict (409) after.
    base_url, session_id = registered_live()
    body = example_files["frames.csv"]
    other = b"frame_index,t_ns\n0,1\n"
    declared = uploader(base_url, session_id, "frames.csv", body)
    different = uploader(base_url, session_id, "frames.csv", other)
    order = [different, declared] if first == "other" else [declared, different]

    responses = queue_uploads(engine, session_id, "frames.csv", order)

    assert [r.status_code for r in responses] == expected_statuses
    row = file_row(db, "frames.csv", session_id)
    stored = stored_path(data_dir, "frames.csv", session_id).read_bytes()
    assert row["status"] == "received"
    assert (row["size"], row["sha256"]) == (len(stored), sha256(stored))
    assert stored == body
    assert stored_files(data_dir) == {f"sessions/{session_id}/frames.csv": body}
