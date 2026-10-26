"""Receiving session files: stream to a temporary file while hashing, verify, store.

Files live at <data_dir>/sessions/<session_id>/<name>. A body is first streamed into a
temporary file in that same directory, then either moved into place atomically or
deleted.
"""

import contextlib
import hashlib
import os
import re
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from capturekit.models import FileStatus, SessionFile
from capturekit.schemas import FileOut

# The only files a session uploads (meta.json is the POST /sessions body).
UPLOADED_FILE_NAMES = frozenset({"video.mp4", "imu.csv", "frames.csv"})

SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# Largest accepted file body: 1 GB, in decimal bytes (docs/api-contract.md).
MAX_FILE_SIZE = 1_000_000_000


class BodyTooLarge(Exception):
    """The body is larger than the size limit."""


class AlreadyReceivedDifferently(Exception):
    """The file was already received with another hash."""


class CorruptUpload(Exception):
    """The body's hash doesn't match the header or the hash declared in meta.json."""


@dataclass
class Upload:
    """A body received into a temporary file in its session directory."""

    path: Path
    sha256: str
    size: int


class FileStore:
    def __init__(
        self, data_dir: Path, make_db_session: Callable[[], Session], max_size: int
    ) -> None:
        self.data_dir = data_dir
        self.make_db_session = make_db_session
        self.max_size = max_size

    def session_dir(self, session_id: uuid.UUID) -> Path:
        return self.data_dir / "sessions" / str(session_id)

    async def receive(self, request: Request, session_id: uuid.UUID, name: str) -> Upload:
        """Stream the request body into a temporary file in the session directory.

        Only one chunk is held in memory at a time, and hashing and disk writes run in
        the threadpool so the event loop keeps serving other requests. Raises
        BodyTooLarge as soon as more than max_size bytes have arrived. On any error,
        including the client going away, the temporary file is removed.
        """
        out, path = await run_in_threadpool(self._create_temp_file, session_id, name)
        digest = hashlib.sha256()
        size = 0
        try:
            with out:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > self.max_size:
                        raise BodyTooLarge
                    await run_in_threadpool(_hash_and_write, digest, out, chunk)
                # The file must be on disk before it is moved into place and marked
                # received.
                await run_in_threadpool(_flush_and_fsync, out)
        except BaseException:
            await run_in_threadpool(self.discard, path)
            raise
        return Upload(path=path, sha256=digest.hexdigest(), size=size)

    def _create_temp_file(self, session_id: uuid.UUID, name: str) -> tuple[BinaryIO, Path]:
        directory = self.session_dir(session_id)
        while True:
            directory.mkdir(parents=True, exist_ok=True)
            try:
                fd, temp = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".part")
            except FileNotFoundError:
                # A concurrent request removed the directory as it was empty: recreate.
                continue
            return os.fdopen(fd, "wb"), Path(temp)

    def store(
        self, session_id: uuid.UUID, name: str, header_sha256: str, upload: Upload
    ) -> tuple[FileOut, bool]:
        """Record the upload and move it into place. Returns (file, newly received).

        Raises AlreadyReceivedDifferently or CorruptUpload (after marking the file
        corrupt). Checks follow the order of the contract's table.
        """
        with self.make_db_session() as db:
            # The row lock serialises concurrent uploads of the same file: the first one
            # moves its file into place and commits, the others then see it received.
            file = db.get_one(SessionFile, (session_id, name), with_for_update=True)
            if file.status == FileStatus.RECEIVED:
                if upload.sha256 != file.sha256:
                    raise AlreadyReceivedDifferently(
                        f"{name} was already received with SHA-256 {file.sha256}; "
                        f"this upload's SHA-256 is {upload.sha256}."
                    )
                return FileOut.from_model(file), False
            if upload.sha256 != header_sha256 or upload.sha256 != file.sha256:
                file.status = FileStatus.CORRUPT
                db.commit()
                raise CorruptUpload(
                    f"{name} is corrupt: received SHA-256 {upload.sha256}, but the "
                    f"X-Content-SHA256 header says {header_sha256} and meta.json "
                    f"declares {file.sha256}."
                )
            destination = self.session_dir(session_id) / name
            # Same directory, so this is a rename: readers see either no file or the
            # complete one, never a partial one.
            os.replace(upload.path, destination)
            _fsync_directory(destination.parent)
            file.status = FileStatus.RECEIVED
            file.size = upload.size
            file.received_at = func.now()
            db.commit()
            db.refresh(file)
            return FileOut.from_model(file), True

    @staticmethod
    def discard(temp_path: Path) -> None:
        """Delete a temporary file (if still there) and its directory if now empty."""
        temp_path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):  # not empty: other files live there
            temp_path.parent.rmdir()


def _hash_and_write(digest: "hashlib._Hash", out: BinaryIO, chunk: bytes) -> None:
    digest.update(chunk)
    out.write(chunk)


def _flush_and_fsync(out: BinaryIO) -> None:
    out.flush()
    os.fsync(out.fileno())


def _fsync_directory(directory: Path) -> None:
    """Make a rename in directory durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
