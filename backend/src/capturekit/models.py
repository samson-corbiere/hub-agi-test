"""ORM mapping of the tables created by the Alembic migrations.

The migrations create the schema; tests/test_migrations.py checks these models still
match it.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class FileStatus(StrEnum):
    EXPECTED = "expected"
    RECEIVED = "received"
    CORRUPT = "corrupt"


class Base(DeclarativeBase):
    pass


class CaptureSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    platform: Mapped[str] = mapped_column(Text)
    device_model: Mapped[str] = mapped_column(Text)
    os_version: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    files: Mapped[list["SessionFile"]] = relationship(
        back_populates="session",
        order_by="SessionFile.name",
        lazy="selectin",
        passive_deletes=True,
    )


class SessionFile(Base):
    __tablename__ = "session_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ({})".format(", ".join(f"'{status}'" for status in FileStatus)),
            name="ck_session_files_status",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[FileStatus] = mapped_column(Text, server_default=FileStatus.EXPECTED)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[CaptureSession] = relationship(back_populates="files")
