"""add structured knowledge units to concepts

Revision ID: 3a9b8379c5a5
Revises: 35c0f3e50bea
Create Date: 2026-10-03 11:39:20.615667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a9b8379c5a5'
down_revision: Union[str, Sequence[str], None] = '35c0f3e50bea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from sqlalchemy.dialects import postgresql

    op.add_column("concepts", sa.Column("definition", sa.Text(), nullable=True))
    op.add_column(
        "concepts",
        sa.Column(
            "terminology",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "procedures",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "formulas",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "worked_examples",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "exercises",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "misconceptions",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "provenance",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("concepts", "provenance")
    op.drop_column("concepts", "misconceptions")
    op.drop_column("concepts", "exercises")
    op.drop_column("concepts", "worked_examples")
    op.drop_column("concepts", "formulas")
    op.drop_column("concepts", "procedures")
    op.drop_column("concepts", "terminology")
    op.drop_column("concepts", "definition")
