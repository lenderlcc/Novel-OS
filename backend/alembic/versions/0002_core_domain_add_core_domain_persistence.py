"""Add core domain persistence

Revision ID: 0002_core_domain
Revises: 0001_bootstrap
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_core_domain"
down_revision: str | Sequence[str] | None = "0001_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_projects_positive_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_table(
        "audit_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum(
                "PROJECT",
                "REQUIREMENT",
                "DECISION",
                "CHAPTER",
                "CHAPTER_PLAN",
                "CHAPTER_VERSION",
                "LOCK",
                "AUDIT_RECORD",
                name="objecttype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "CREATE",
                "UPDATE",
                "ARCHIVE",
                "VERSION_CREATE",
                "APPROVE",
                "SUPERSEDE",
                "LOCK",
                "UNLOCK",
                name="auditaction",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_audit_records_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_records")),
    )
    op.create_index(
        op.f("ix_audit_records_project_id"), "audit_records", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_records_request_id"), "audit_records", ["request_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_records_target_id"), "audit_records", ["target_id"], unique=False
    )
    op.create_table(
        "chapters",
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=True),
        sa.Column("approved_version", sa.Integer(), nullable=True),
        sa.Column("current_plan_version", sa.Integer(), nullable=True),
        sa.Column("approved_plan_version", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_chapters_positive_sequence")),
        sa.CheckConstraint("version > 0", name=op.f("ck_chapters_positive_version")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_chapters_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapters")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_chapters_id")),
        sa.UniqueConstraint("project_id", "sequence", name=op.f("uq_chapters_project_id")),
    )
    op.create_index(op.f("ix_chapters_project_id"), "chapters", ["project_id"], unique=False)
    op.create_table(
        "decisions",
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("affected_objects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("logical_id", sa.Uuid(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_decisions_positive_version")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_decisions_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["decisions.id"], name=op.f("fk_decisions_supersedes_id_decisions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisions")),
        sa.UniqueConstraint("logical_id", "version", name=op.f("uq_decisions_logical_id")),
    )
    op.create_index(op.f("ix_decisions_logical_id"), "decisions", ["logical_id"], unique=False)
    op.create_index(op.f("ix_decisions_project_id"), "decisions", ["project_id"], unique=False)
    op.create_index(
        "uq_decisions_approved",
        "decisions",
        ["logical_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.create_table(
        "locks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum(
                "PROJECT",
                "REQUIREMENT",
                "DECISION",
                "CHAPTER",
                "CHAPTER_PLAN",
                "CHAPTER_VERSION",
                "LOCK",
                "AUDIT_RECORD",
                name="objecttype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("locked_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.String(length=128), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column(
            "previous_status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "previous_authority",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("scope = 'OBJECT'", name=op.f("ck_locks_object_scope")),
        sa.CheckConstraint("active = (released_at IS NULL)", name=op.f("ck_locks_release_state")),
        sa.CheckConstraint("target_version > 0", name=op.f("ck_locks_positive_target_version")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_locks_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locks")),
    )
    op.create_index(op.f("ix_locks_project_id"), "locks", ["project_id"], unique=False)
    op.create_index(
        "uq_locks_active_target",
        "locks",
        ["target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "requirements",
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "requirement_type",
            sa.Enum(
                "MUST",
                "SHOULD",
                "PREFERENCE",
                "FORBIDDEN",
                "QUALITY_EXPECTATION",
                "PRESERVE",
                "CHANGE_REQUEST",
                name="requirementtype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "scope_type",
            sa.Enum(
                "PROJECT", "CHAPTER", name="scopetype", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("persistent", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("logical_id", sa.Uuid(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name=op.f("ck_requirements_effective_range"),
        ),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name=op.f("ck_requirements_priority_range")),
        sa.CheckConstraint("version > 0", name=op.f("ck_requirements_positive_version")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_requirements_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["requirements.id"],
            name=op.f("fk_requirements_supersedes_id_requirements"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirements")),
        sa.UniqueConstraint("logical_id", "version", name=op.f("uq_requirements_logical_id")),
    )
    op.create_index(
        op.f("ix_requirements_logical_id"), "requirements", ["logical_id"], unique=False
    )
    op.create_index(
        op.f("ix_requirements_project_id"), "requirements", ["project_id"], unique=False
    )
    op.create_index(
        "uq_requirements_approved",
        "requirements",
        ["logical_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.create_table(
        "chapter_plans",
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("required_outcome", sa.Text(), nullable=False),
        sa.Column("scene_plans", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("character_progression", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plot_progression", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("information_release", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ending_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locked_dependencies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("logical_id", sa.Uuid(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "logical_id = chapter_id", name=op.f("ck_chapter_plans_chapter_logical_id")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_chapter_plans_positive_version")),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_chapter_plans_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_chapter_plans_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["chapter_plans.id"],
            name=op.f("fk_chapter_plans_supersedes_id_chapter_plans"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_plans")),
        sa.UniqueConstraint("chapter_id", "version", name=op.f("uq_chapter_plans_chapter_id")),
        sa.UniqueConstraint("logical_id", "version", name=op.f("uq_chapter_plans_logical_id")),
    )
    op.create_index(
        op.f("ix_chapter_plans_logical_id"), "chapter_plans", ["logical_id"], unique=False
    )
    op.create_index(
        op.f("ix_chapter_plans_project_id"), "chapter_plans", ["project_id"], unique=False
    )
    op.create_index(
        "uq_chapter_plans_approved",
        "chapter_plans",
        ["logical_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.create_table(
        "chapter_versions",
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("logical_id", sa.Uuid(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROPOSED",
                "APPROVED",
                "LOCKED",
                "ACTIVE",
                "STALE",
                "SUPERSEDED",
                "DEPRECATED",
                "CANCELLED",
                "EXECUTED",
                "ARCHIVED",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "authority_level",
            sa.Enum(
                "A0_SYSTEM_RULE",
                "A1_USER_LOCKED",
                "A2_USER_APPROVED",
                "A3_CANON",
                "A4_APPROVED_PLAN",
                "A5_USER_PREFERENCE",
                "A6_DERIVED_MEMORY",
                "A7_AI_INFERENCE",
                name="authority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "logical_id = chapter_id", name=op.f("ck_chapter_versions_chapter_logical_id")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_chapter_versions_positive_version")),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_chapter_versions_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["chapter_versions.id"],
            name=op.f("fk_chapter_versions_parent_version_id_chapter_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_chapter_versions_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["chapter_versions.id"],
            name=op.f("fk_chapter_versions_supersedes_id_chapter_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_versions")),
        sa.UniqueConstraint("chapter_id", "version", name=op.f("uq_chapter_versions_chapter_id")),
        sa.UniqueConstraint("logical_id", "version", name=op.f("uq_chapter_versions_logical_id")),
    )
    op.create_index(
        op.f("ix_chapter_versions_logical_id"), "chapter_versions", ["logical_id"], unique=False
    )
    op.create_index(
        op.f("ix_chapter_versions_project_id"), "chapter_versions", ["project_id"], unique=False
    )
    op.create_index(
        "uq_chapter_versions_approved",
        "chapter_versions",
        ["logical_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )

    for column, table in POINTERS:
        op.create_foreign_key(
            f"fk_chapters_{column}",
            "chapters",
            table,
            ["id", column],
            ["chapter_id", "version"],
            deferrable=True,
            initially="DEFERRED",
        )
    op.execute(GUARD_FUNCTION)
    for table in CORE_TABLES:
        op.execute(
            f"CREATE TRIGGER protect_core_record BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION novel_guard_core_record()"
        )


def downgrade() -> None:
    for table in CORE_TABLES:
        op.execute(f"DROP TRIGGER protect_core_record ON {table}")
    op.execute("DROP FUNCTION novel_guard_core_record()")
    for column, _ in POINTERS:
        op.drop_constraint(f"fk_chapters_{column}", "chapters", type_="foreignkey")
    op.drop_index(
        "uq_chapter_versions_approved",
        table_name="chapter_versions",
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.drop_index(op.f("ix_chapter_versions_project_id"), table_name="chapter_versions")
    op.drop_index(op.f("ix_chapter_versions_logical_id"), table_name="chapter_versions")
    op.drop_table("chapter_versions")
    op.drop_index(
        "uq_chapter_plans_approved",
        table_name="chapter_plans",
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.drop_index(op.f("ix_chapter_plans_project_id"), table_name="chapter_plans")
    op.drop_index(op.f("ix_chapter_plans_logical_id"), table_name="chapter_plans")
    op.drop_table("chapter_plans")
    op.drop_index(
        "uq_requirements_approved",
        table_name="requirements",
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.drop_index(op.f("ix_requirements_project_id"), table_name="requirements")
    op.drop_index(op.f("ix_requirements_logical_id"), table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("uq_locks_active_target", table_name="locks", postgresql_where=sa.text("active"))
    op.drop_index(op.f("ix_locks_project_id"), table_name="locks")
    op.drop_table("locks")
    op.drop_index(
        "uq_decisions_approved",
        table_name="decisions",
        postgresql_where=sa.text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
    )
    op.drop_index(op.f("ix_decisions_project_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_logical_id"), table_name="decisions")
    op.drop_table("decisions")
    op.drop_index(op.f("ix_chapters_project_id"), table_name="chapters")
    op.drop_table("chapters")
    op.drop_index(op.f("ix_audit_records_target_id"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_request_id"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_project_id"), table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_table("projects")


CORE_TABLES = (
    "projects",
    "requirements",
    "decisions",
    "locks",
    "chapters",
    "chapter_plans",
    "chapter_versions",
    "audit_records",
)
POINTERS = (
    ("current_version", "chapter_versions"),
    ("approved_version", "chapter_versions"),
    ("current_plan_version", "chapter_plans"),
    ("approved_plan_version", "chapter_plans"),
)
GUARD_FUNCTION = """
CREATE FUNCTION novel_guard_core_record() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lifecycle text[] := ARRAY['status', 'authority_level', 'locked', 'updated_at',
                              'approved_by', 'approved_at'];
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Core records cannot be hard deleted' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'audit_records' THEN
        RAISE EXCEPTION 'Audit records are append only' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME IN ('requirements', 'decisions', 'chapter_plans', 'chapter_versions') THEN
        IF (NEW.id, NEW.project_id, NEW.logical_id, NEW.version, NEW.supersedes_id,
            NEW.created_at, NEW.created_by) IS DISTINCT FROM
           (OLD.id, OLD.project_id, OLD.logical_id, OLD.version, OLD.supersedes_id,
            OLD.created_at, OLD.created_by) THEN
            RAISE EXCEPTION 'Version identity is immutable' USING ERRCODE = '23514';
        END IF;
        IF TG_TABLE_NAME = 'chapter_versions'
           OR OLD.approved_at IS NOT NULL OR NEW.approved_at IS NOT NULL
           OR OLD.locked OR NEW.locked
           OR OLD.status IN ('APPROVED', 'LOCKED') OR NEW.status IN ('APPROVED', 'LOCKED') THEN
            IF (to_jsonb(NEW) - lifecycle) IS DISTINCT FROM (to_jsonb(OLD) - lifecycle) THEN
                RAISE EXCEPTION 'Version payload is immutable' USING ERRCODE = '23514';
            END IF;
        END IF;
        IF OLD.approved_at IS NOT NULL AND
           (NEW.approved_at, NEW.approved_by) IS DISTINCT FROM
           (OLD.approved_at, OLD.approved_by) THEN
            RAISE EXCEPTION 'Approval evidence is immutable' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$
"""
