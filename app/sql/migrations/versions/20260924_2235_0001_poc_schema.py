"""Esquema final de la POC

Revision ID: 0001_poc_schema
Revises:
Create Date: 2026-09-24 22:35:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_poc_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("original_file_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("detected_fields_count", sa.Integer(), nullable=True),
        sa.Column("corrections_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'requires_review', 'failed')",
            name=op.f("ck_form_imports_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_imports")),
    )
    op.create_index(op.f("ix_form_imports_status"), "form_imports", ["status"], unique=False)

    op.create_table(
        "form_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_form_templates_status_valid")),
        sa.CheckConstraint("latest_version >= 1", name=op.f("ck_form_templates_latest_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_templates")),
    )
    op.create_index("ix_form_templates_created_at_id", "form_templates", ["created_at", "id"], unique=False)

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_keys")),
        sa.UniqueConstraint("idempotency_key", "scope", name="uq_idempotency_keys_key_scope"),
    )
    op.create_index(op.f("ix_idempotency_keys_expires_at"), "idempotency_keys", ["expires_at"], unique=False)

    op.create_table(
        "worker_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'error')",
            name=op.f("ck_worker_tasks_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_tasks")),
    )
    op.create_index("ix_worker_tasks_status_available_at", "worker_tasks", ["status", "available_at"], unique=False)
    op.create_index(
        "uq_worker_tasks_active_dedupe_key",
        "worker_tasks",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'processing') AND dedupe_key IS NOT NULL"),
    )

    op.create_table(
        "form_template_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_import_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_form_template_versions_version_positive")),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["form_templates.id"],
            name=op.f("fk_form_template_versions_template_id_form_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["form_imports.id"],
            name=op.f("fk_form_template_versions_source_import_id_form_imports"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_template_versions")),
        sa.UniqueConstraint("template_id", "version", name="uq_form_template_versions_template_id_version"),
    )
    op.create_index(
        op.f("ix_form_template_versions_source_import_id"),
        "form_template_versions",
        ["source_import_id"],
        unique=False,
    )

    op.create_table(
        "form_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("template_version_id", sa.UUID(), nullable=False),
        sa.Column("job_demo_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("values_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'submitted')", name=op.f("ck_form_responses_status_valid")),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["form_templates.id"],
            name=op.f("fk_form_responses_template_id_form_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["form_template_versions.id"],
            name=op.f("fk_form_responses_template_version_id_form_template_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_responses")),
    )
    op.create_index(op.f("ix_form_responses_job_demo_id"), "form_responses", ["job_demo_id"], unique=False)
    op.create_index(
        op.f("ix_form_responses_template_version_id"),
        "form_responses",
        ["template_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_form_responses_template_id_created_at_id",
        "form_responses",
        ["template_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("response_id", sa.UUID(), nullable=False),
        sa.Column("field_id", sa.String(length=20), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("file_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('photo')", name=op.f("ck_attachments_type_valid")),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["form_responses.id"],
            name=op.f("fk_attachments_response_id_form_responses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
    )
    op.create_index("ix_attachments_response_id_field_id", "attachments", ["response_id", "field_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attachments_response_id_field_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_form_responses_template_id_created_at_id", table_name="form_responses")
    op.drop_index(op.f("ix_form_responses_template_version_id"), table_name="form_responses")
    op.drop_index(op.f("ix_form_responses_job_demo_id"), table_name="form_responses")
    op.drop_table("form_responses")
    op.drop_index(op.f("ix_form_template_versions_source_import_id"), table_name="form_template_versions")
    op.drop_table("form_template_versions")
    op.drop_index(
        "uq_worker_tasks_active_dedupe_key",
        table_name="worker_tasks",
        postgresql_where=sa.text("status IN ('pending', 'processing') AND dedupe_key IS NOT NULL"),
    )
    op.drop_index("ix_worker_tasks_status_available_at", table_name="worker_tasks")
    op.drop_table("worker_tasks")
    op.drop_index(op.f("ix_idempotency_keys_expires_at"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_form_templates_created_at_id", table_name="form_templates")
    op.drop_table("form_templates")
    op.drop_index(op.f("ix_form_imports_status"), table_name="form_imports")
    op.drop_table("form_imports")
