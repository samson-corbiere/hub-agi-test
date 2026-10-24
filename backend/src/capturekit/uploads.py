"""Streaming a request body to a temporary file while hashing it."""

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from starlette.requests import Request


@dataclass
class Upload:
    """A body received into a temporary file next to its final location."""

    path: Path
    sha256: str
    size: int

    def move_to(self, destination: Path) -> None:
        """Atomically put the file at destination, replacing what is there."""
        os.replace(self.path, destination)

    def discard(self) -> None:
        self.path.unlink(missing_ok=True)


async def receive_upload(request: Request, directory: Path, name: str) -> Upload:
    """Stream the request body into a temporary file in directory, chunk by chunk."""
    directory.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".part")
    path = Path(temp)
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            async for chunk in request.stream():
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return Upload(path=path, sha256=digest.hexdigest(), size=size)
