"""add bulk content generation jobs

Revision ID: e5a1f2b3c4d6
Revises: d1c79ab0a1f2
Create Date: 2026-09-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e5a1f2b3c4d6"
down_revision: Union[str, Sequence[str], None] = "d1c79ab0a1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    state = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        name="content_generation_state",
        create_type=False,
    )
    state.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "content_generation_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("curriculum_id", sa.UUID(), nullable=False),
        sa.Column("status", state, nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("total_weeks", sa.Integer(), nullable=False),
        sa.Column("completed_weeks", sa.Integer(), nullable=False),
        sa.Column("lessons_generated", sa.Integer(), nullable=False),
        sa.Column("skipped_weeks", sa.Integer(), nullable=False),
        sa.Column("rebuild_existing", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["curriculum_id"],
            ["curricula.id"],
            name="fk_content_generation_jobs_curriculum_id_curricula",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_generation_jobs"),
    )
    op.create_index(
        op.f("ix_content_generation_jobs_curriculum_id"),
        "content_generation_jobs",
        ["curriculum_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_generation_jobs_status"),
        "content_generation_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_content_generation_jobs_status"),
        table_name="content_generation_jobs",
    )
    op.drop_index(
        op.f("ix_content_generation_jobs_curriculum_id"),
        table_name="content_generation_jobs",
    )
    op.drop_table("content_generation_jobs")
    postgresql.ENUM(name="content_generation_state").drop(
        op.get_bind(), checkfirst=True
    )
