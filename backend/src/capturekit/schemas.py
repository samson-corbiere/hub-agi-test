"""Response bodies, as defined in docs/api-contract.md ("Objects")."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from capturekit.models import Session, SessionFile


class FileOut(BaseModel):
    name: str
    size: int
    sha256: str
    status: Literal["expected", "received", "corrupt"]
    received_at: datetime | None

    @classmethod
    def from_model(cls, file: SessionFile) -> "FileOut":
        return cls(
            name=file.name,
            size=file.size,
            sha256=file.sha256,
            status=file.status,
            received_at=file.received_at.astimezone(UTC) if file.received_at else None,
        )


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    device_model: str
    os_version: str
    duration_s: float
    files: list[FileOut]
    received_count: int
    expected_count: int
    complete: bool

    @classmethod
    def from_model(cls, session: Session) -> "SessionOut":
        files = [FileOut.from_model(f) for f in session.files]
        received = sum(1 for f in files if f.status == "received")
        meta = session.meta
        return cls(
            id=session.id,
            created_at=session.created_at.astimezone(UTC),
            device_model=session.device_model,
            os_version=session.os_version,
            duration_s=(meta["video_end_t_ns"] - meta["video_start_t_ns"]) / 1e9,
            files=files,
            received_count=received,
            expected_count=len(files),
            complete=received == len(files),
        )
