"""add dependencies table

Revision ID: b2e9c4f0a7d3
Revises: 796ac4bae740
Create Date: 2026-09-14 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2e9c4f0a7d3'
down_revision: str | Sequence[str] | None = '796ac4bae740'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('dependencies',
    sa.Column('topic_id', sa.UUID(), nullable=False),
    sa.Column('depends_on_topic_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], name=op.f('fk_dependencies_topic_id_topics'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['depends_on_topic_id'], ['topics.id'], name=op.f('fk_dependencies_depends_on_topic_id_topics'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dependencies')),
    sa.UniqueConstraint('topic_id', 'depends_on_topic_id', name='uq_dependencies_topic_depends_on')
    )
    op.create_index(op.f('ix_dependencies_topic_id'), 'dependencies', ['topic_id'], unique=False)
    op.create_index(op.f('ix_dependencies_depends_on_topic_id'), 'dependencies', ['depends_on_topic_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_dependencies_depends_on_topic_id'), table_name='dependencies')
    op.drop_index(op.f('ix_dependencies_topic_id'), table_name='dependencies')
    op.drop_table('dependencies')
    # ### end Alembic commands ###