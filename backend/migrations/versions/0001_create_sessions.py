"""Create sessions and session_files.

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        # Client-generated UUID v4 (meta.session_id).
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("device_model", sa.Text(), nullable=False),
        sa.Column("os_version", sa.Text(), nullable=False),
        # The full meta.json as received.
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])

    op.create_table(
        "session_files",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="expected"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id", "name", name="pk_session_files"),
        sa.CheckConstraint(
            "status IN ('expected', 'received', 'corrupt')",
            name="ck_session_files_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("session_files")
    op.drop_index("ix_sessions_created_at", table_name="sessions")
    op.drop_table("sessions")
