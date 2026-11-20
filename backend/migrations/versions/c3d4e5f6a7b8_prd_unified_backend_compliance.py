"""Add participant_account_links, authority_scopes, notice_recipients, consent metadata, and idempotency keys.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-18 23:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.create_unique_constraint("uq_organizations_idempotency_key", "organizations", ["idempotency_key"])

    # Ensure any single-track org created without primary_programme is safely backfilled
    op.execute(
        """
        UPDATE organizations
        SET primary_programme = enabled_tracks[1],
            programme_configuration_status = 'configured'
        WHERE primary_programme IS NULL AND cardinality(enabled_tracks) = 1
        """
    )

    op.add_column(
        "portal_invitations",
        sa.Column("accepted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.create_table(
        "participant_account_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_source", sa.String(length=32), nullable=False, server_default="invitation"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_participant_link_user_org"),
        sa.UniqueConstraint("patient_id", name="uq_participant_link_patient"),
    )
    op.create_index("ix_participant_account_links_organization_id", "participant_account_links", ["organization_id"])
    op.create_index("ix_participant_account_links_user_id", "participant_account_links", ["user_id"])
    op.create_index("ix_participant_account_links_patient_id", "participant_account_links", ["patient_id"])

    # Allow a verified portal user to hold separate facility-scoped Patient links across organisations
    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS patients_portal_user_id_key")
    op.execute("CREATE INDEX IF NOT EXISTS ix_patients_portal_user_id ON patients (portal_user_id)")

    # Backfill existing Patient.portal_user_id links
    op.execute(
        """
        INSERT INTO participant_account_links (id, organization_id, user_id, patient_id, verified_at, verification_source)
        SELECT id, organization_id, portal_user_id, id, COALESCE(updated_at, NOW()), 'migration_backfill'
        FROM patients
        WHERE portal_user_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    op.create_table(
        "authority_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("assigned_emirates", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("assigned_facility_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("can_publish", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("can_view_reports", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("min_suppression_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("granted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_authority_scopes_user_id", "authority_scopes", ["user_id"])
    op.create_index("ix_authority_scopes_organization_id", "authority_scopes", ["organization_id"])

    op.add_column("track_enrollments", sa.Column("authority_actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("track_enrollments", sa.Column("authority_reason", sa.Text(), nullable=True))
    op.add_column("track_enrollments", sa.Column("history", postgresql.JSONB(), nullable=False, server_default="[]"))

    op.add_column("consents", sa.Column("policy_version", sa.String(length=40), nullable=False, server_default="v1.0"))
    op.add_column("consents", sa.Column("authority_to_act", sa.String(length=80), nullable=False, server_default="self"))
    op.add_column("consents", sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    op.add_column("check_ins", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.create_unique_constraint("uq_checkin_patient_idem", "check_ins", ["patient_id", "idempotency_key"])

    op.add_column("cognitive_assessments", sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("track_enrollments.id", ondelete="SET NULL"), nullable=True))
    op.add_column("cognitive_assessments", sa.Column("task_version", sa.String(length=60), nullable=True))
    op.add_column("cognitive_assessments", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.create_index("ix_cognitive_assessments_enrollment_id", "cognitive_assessments", ["enrollment_id"])
    op.create_unique_constraint("uq_cognitive_patient_idem", "cognitive_assessments", ["patient_id", "idempotency_key"])

    op.add_column("public_health_notices", sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True))
    op.add_column("public_health_notices", sa.Column("facility_ids", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("public_health_notices", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.add_column("public_health_notices", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("public_health_notices", sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("public_health_notices", sa.Column("withdrawn_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_public_health_notices_organization_id", "public_health_notices", ["organization_id"])
    op.create_unique_constraint("uq_notice_idem", "public_health_notices", ["idempotency_key"])

    op.create_table(
        "notice_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("notice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_health_notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_delivery_status", sa.String(length=30), nullable=False, server_default="in_app_available"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_recipient_user"),
    )
    op.create_index("ix_notice_recipients_notice_id", "notice_recipients", ["notice_id"])
    op.create_index("ix_notice_recipients_user_id", "notice_recipients", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notice_recipients_user_id", table_name="notice_recipients")
    op.drop_index("ix_notice_recipients_notice_id", table_name="notice_recipients")
    op.drop_table("notice_recipients")

    op.drop_constraint("uq_notice_idem", "public_health_notices", type_="unique")
    op.drop_index("ix_public_health_notices_organization_id", table_name="public_health_notices")
    op.drop_column("public_health_notices", "withdrawn_by_id")
    op.drop_column("public_health_notices", "withdrawn_at")
    op.drop_column("public_health_notices", "starts_at")
    op.drop_column("public_health_notices", "idempotency_key")
    op.drop_column("public_health_notices", "facility_ids")
    op.drop_column("public_health_notices", "organization_id")

    op.drop_constraint("uq_cognitive_patient_idem", "cognitive_assessments", type_="unique")
    op.drop_index("ix_cognitive_assessments_enrollment_id", table_name="cognitive_assessments")
    op.drop_column("cognitive_assessments", "idempotency_key")
    op.drop_column("cognitive_assessments", "task_version")
    op.drop_column("cognitive_assessments", "enrollment_id")

    op.drop_constraint("uq_checkin_patient_idem", "check_ins", type_="unique")
    op.drop_column("check_ins", "idempotency_key")

    op.drop_column("consents", "actor_user_id")
    op.drop_column("consents", "authority_to_act")
    op.drop_column("consents", "policy_version")

    op.drop_column("track_enrollments", "history")
    op.drop_column("track_enrollments", "authority_reason")
    op.drop_column("track_enrollments", "authority_actor_id")

    op.drop_index("ix_authority_scopes_organization_id", table_name="authority_scopes")
    op.drop_index("ix_authority_scopes_user_id", table_name="authority_scopes")
    op.drop_table("authority_scopes")

    op.drop_index("ix_participant_account_links_patient_id", table_name="participant_account_links")
    op.drop_index("ix_participant_account_links_user_id", table_name="participant_account_links")
    op.drop_index("ix_participant_account_links_organization_id", table_name="participant_account_links")
    op.drop_table("participant_account_links")

    op.drop_column("portal_invitations", "accepted_by_user_id")
    op.drop_constraint("uq_organizations_idempotency_key", "organizations", type_="unique")
    op.drop_column("organizations", "idempotency_key")
