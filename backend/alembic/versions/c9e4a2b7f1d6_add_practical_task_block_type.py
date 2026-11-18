"""add practical_task lesson block type

Revision ID: c9e4a2b7f1d6
Revises: b7f1c2d3e4a5
Create Date: 2026-10-21 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e4a2b7f1d6"
down_revision: Union[str, Sequence[str], None] = "b7f1c2d3e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add the PRACTICAL_TASK label to the lesson_block_type enum.

    ``ALTER TYPE ... ADD VALUE`` cannot run inside the migration's usual
    transaction, so it executes in an autocommit block.
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'PRACTICAL_TASK'")


def downgrade() -> None:
    """
    No-op.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; removing a label
    requires recreating the type and rewriting every dependent column,
    which risks data loss. Existing practical_task rows must be migrated
    by hand before the label can be dropped. The extra label is harmless
    if left in place.
    """
    pass
