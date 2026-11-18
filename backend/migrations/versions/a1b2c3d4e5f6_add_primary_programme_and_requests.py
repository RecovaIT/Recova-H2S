"""Add primary_programme, programme_configuration_status, and programme_requests.

Revision ID: a1b2c3d4e5f6
Revises: cd2178bcb554
Create Date: 2026-11-18 03:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "cd2178bcb554"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("primary_programme", sa.String(length=32), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("programme_configuration_status", sa.String(length=32), nullable=False, server_default="configured"),
    )

    # Backfill existing single-track orgs to that primary programme; multi-track orgs require admin selection.
    op.execute(
        """
        UPDATE organizations
        SET primary_programme = enabled_tracks[1],
            programme_configuration_status = 'configured'
        WHERE cardinality(enabled_tracks) = 1
        """
    )
    op.execute(
        """
        UPDATE organizations
        SET primary_programme = enabled_tracks[1],
            programme_configuration_status = 'pending_selection'
        WHERE cardinality(enabled_tracks) > 1
        """
    )

    op.create_table(
        "programme_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_programme", sa.String(length=32), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_programme_requests_organization_id", "programme_requests", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_programme_requests_organization_id", table_name="programme_requests")
    op.drop_table("programme_requests")
    op.drop_column("organizations", "programme_configuration_status")
    op.drop_column("organizations", "primary_programme")
