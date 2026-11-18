"""add student and teacher roles

Revision ID: b7f1c2d3e4a5
Revises: 3a9b8379c5a5
Create Date: 2026-10-12 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f1c2d3e4a5"
down_revision: Union[str, Sequence[str], None] = "3a9b8379c5a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add the STUDENT and TEACHER labels to the user_role enum.

    ``ALTER TYPE ... ADD VALUE`` cannot run inside the migration's usual
    transaction, so it executes in an autocommit block.
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'STUDENT'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'TEACHER'")


def downgrade() -> None:
    """
    No-op.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; removing a label
    requires recreating the type and rewriting every dependent column,
    which risks data loss. The extra labels are harmless if left in
    place.
    """
    pass
