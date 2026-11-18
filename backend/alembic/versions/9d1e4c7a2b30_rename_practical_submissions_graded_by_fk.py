"""rename practical submissions graded by foreign key

Revision ID: 9d1e4c7a2b30
Revises: 88afec1453ec
Create Date: 2026-10-22 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9d1e4c7a2b30'
down_revision: Union[str, Sequence[str], None] = '88afec1453ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREVIOUS_NAME = 'fk_practical_submissions_grading_user_id_users'
CURRENT_NAME = 'fk_practical_submissions_graded_by_id_users'


def upgrade() -> None:
    """Rename the graded-by foreign key to match the project naming convention."""
    op.execute(
        f'ALTER TABLE practical_submissions RENAME CONSTRAINT {PREVIOUS_NAME} TO {CURRENT_NAME}'
    )


def downgrade() -> None:
    """Restore the previous foreign key name."""
    op.execute(
        f'ALTER TABLE practical_submissions RENAME CONSTRAINT {CURRENT_NAME} TO {PREVIOUS_NAME}'
    )
