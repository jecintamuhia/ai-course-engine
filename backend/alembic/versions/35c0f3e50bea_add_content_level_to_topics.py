"""add content_level to topics

Revision ID: 35c0f3e50bea
Revises: f6b2c4d8e1a3
Create Date: 2026-10-02 21:51:39.884361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35c0f3e50bea'
down_revision: Union[str, Sequence[str], None] = 'f6b2c4d8e1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    content_level_enum = sa.Enum(
        "basic", "intermediate", "advanced",
        name="content_level",
        create_type=True,
    )
    content_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "topics",
        sa.Column("content_level", content_level_enum, nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("topics", "content_level")
    content_level_enum = sa.Enum(
        "basic", "intermediate", "advanced",
        name="content_level",
        create_type=True,
    )
    content_level_enum.drop(op.get_bind(), checkfirst=True)
