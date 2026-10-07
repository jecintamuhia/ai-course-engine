"""add topic canonicalization, quality reports, assessments

Revision ID: c3f1a2b9d0e4
Revises: bb0114030dd1
Create Date: 2026-09-25 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c3f1a2b9d0e4"
down_revision: Union[str, Sequence[str], None] = "bb0114030dd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Topic canonicalization / deduplication identity.
    op.add_column(
        "topics",
        sa.Column("canonical_key", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "topics",
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.add_column(
        "topics",
        sa.Column("duplicate_of_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "topics",
        sa.Column("importance", sa.String(length=20), nullable=True),
    )
    op.create_index(
        op.f("ix_topics_canonical_key"), "topics", ["canonical_key"], unique=False
    )
    op.create_index(
        op.f("ix_topics_duplicate_of_id"), "topics", ["duplicate_of_id"], unique=False
    )
    op.create_foreign_key(
        "fk_topics_duplicate_of_id_topics",
        "topics",
        "topics",
        ["duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Persistent content-QA reports.
    op.create_table(
        "quality_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("curriculum_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("areas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["curriculum_id"],
            ["curricula.id"],
            ondelete="CASCADE",
            name="fk_quality_reports_curriculum_id_curricula",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quality_reports"),
    )
    op.create_index(
        op.f("ix_quality_reports_curriculum_id"),
        "quality_reports",
        ["curriculum_id"],
        unique=False,
    )

    # Assessments.
    assessment_type = postgresql.ENUM(
        "WEEKLY_QUIZ",
        "PRACTICAL_ASSIGNMENT",
        "CODING_TASK",
        "CASE_STUDY",
        "MINI_PROJECT",
        "FINAL",
        name="assessment_type",
        create_type=False,
    )
    assessment_type.create(op.get_bind(), checkfirst=True)

    assessment_status = postgresql.ENUM(
        "DRAFT",
        "GENERATING",
        "AWAITING_REVIEW",
        "APPROVED",
        "REJECTED",
        name="assessment_status",
        create_type=False,
    )
    assessment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assessments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("curriculum_id", sa.UUID(), nullable=False),
        sa.Column("curriculum_unit_id", sa.UUID(), nullable=True),
        sa.Column("week_number", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assessment_type", assessment_type, nullable=False),
        sa.Column(
            "learning_objectives",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alignment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", assessment_status, nullable=False),
        sa.Column(
            "generation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_chunk_markers",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("reviewer_name", sa.String(length=300), nullable=True),
        sa.Column("review_comments", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["curriculum_id"],
            ["curricula.id"],
            ondelete="CASCADE",
            name="fk_assessments_curriculum_id_curricula",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_unit_id"],
            ["curriculum_units.id"],
            ondelete="CASCADE",
            name="fk_assessments_curriculum_unit_id_curriculum_units",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessments"),
    )
    op.create_index(
        op.f("ix_assessments_curriculum_id"),
        "assessments",
        ["curriculum_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessments_curriculum_unit_id"),
        "assessments",
        ["curriculum_unit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessments_status"),
        "assessments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_assessments_status"), table_name="assessments")
    op.drop_index(op.f("ix_assessments_curriculum_unit_id"), table_name="assessments")
    op.drop_index(op.f("ix_assessments_curriculum_id"), table_name="assessments")
    op.drop_table("assessments")
    postgresql.ENUM(name="assessment_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="assessment_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_quality_reports_curriculum_id"), table_name="quality_reports")
    op.drop_table("quality_reports")

    op.drop_constraint(
        "fk_topics_duplicate_of_id_topics", "topics", type_="foreignkey"
    )
    op.drop_index(op.f("ix_topics_duplicate_of_id"), table_name="topics")
    op.drop_index(op.f("ix_topics_canonical_key"), table_name="topics")
    op.drop_column("topics", "importance")
    op.drop_column("topics", "duplicate_of_id")
    op.drop_column("topics", "aliases")
    op.drop_column("topics", "canonical_key")