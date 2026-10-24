"""Streaming a request body to a temporary file while hashing it."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

# The only files a session uploads (meta.json is the POST /sessions body).
UPLOADED_FILE_NAMES = frozenset({"video.mp4", "imu.csv", "frames.csv"})

SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# Largest accepted file body: 1 GB, in decimal bytes (docs/api-contract.md).
MAX_FILE_SIZE = 1_000_000_000


class BodyTooLarge(Exception):
    """The body is larger than the size limit."""


@dataclass
class Upload:
    """A body received into a temporary file next to its final location."""

    path: Path
    sha256: str
    size: int

    def move_to(self, destination: Path) -> None:
        """Atomically put the file at destination, replacing what is there.

        The temporary file is in the same directory, so this is a rename: readers see
        either the old file or the complete new one, never a partial one.
        """
        os.replace(self.path, destination)
        _fsync_directory(destination.parent)

    def discard(self) -> None:
        self.path.unlink(missing_ok=True)


def _fsync_directory(directory: Path) -> None:
    """Make a rename in directory durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


async def receive_upload(request: Request, directory: Path, name: str, max_size: int) -> Upload:
    """Stream the request body into a temporary file in directory, chunk by chunk.

    Only one chunk is held in memory at a time. Raises BodyTooLarge as soon as more than
    max_size bytes have arrived. On any error, including the client going away, the
    temporary file is removed.
    """
    directory.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".part")
    path = Path(temp)
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_size:
                    raise BodyTooLarge
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            # The file must be on disk before it is moved into place and marked received.
            await run_in_threadpool(os.fsync, out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return Upload(path=path, sha256=digest.hexdigest(), size=size)
