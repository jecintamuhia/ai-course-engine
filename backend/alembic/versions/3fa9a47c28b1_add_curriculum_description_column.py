"""add curriculum description column

Revision ID: 3fa9a47c28b1
Revises: d45a2457f166
Create Date: 2026-09-15 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3fa9a47c28b1'
down_revision: str | Sequence[str] | None = 'd45a2457f166'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'curricula',
        sa.Column('description', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('curricula', 'description')