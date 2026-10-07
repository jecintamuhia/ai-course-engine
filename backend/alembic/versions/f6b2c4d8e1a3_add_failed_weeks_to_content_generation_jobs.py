"""add failed week tracking to content generation jobs

A bulk run whose LLM calls all fail (for example an exhausted provider
balance) used to increment ``completed_weeks`` and finish as COMPLETED,
so the UI reported a fully generated course while several weeks held no
lessons at all. This adds ``failed_weeks`` so the worker can record a
shortfall and report it instead of claiming success.

Revision ID: f6b2c4d8e1a3
Revises: e5a1f2b3c4d6
Create Date: 2026-09-26 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6b2c4d8e1a3"
down_revision: Union[str, Sequence[str], None] = "e5a1f2b3c4d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "content_generation_jobs",
        sa.Column(
            "failed_weeks",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("content_generation_jobs", "failed_weeks")
