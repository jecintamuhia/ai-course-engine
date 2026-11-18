"""add assessment attempts and certificates

Revision ID: f1a2b3c4d5e6
Revises: 9d1e4c7a2b30
Create Date: 2026-11-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '9d1e4c7a2b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create attempt and certificate tables."""
    op.create_table(
        'assessment_attempts',
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('enrolment_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('correct_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('auto_gradable_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('score_percent', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('passed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('score_percent >= 0 AND score_percent <= 100', name='ck_assessment_attempts_score_range'),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_assessment_attempts_assessment_id_assessments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enrolment_id'], ['learner_enrolments.id'], name=op.f('fk_assessment_attempts_enrolment_id_learner_enrolments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_assessment_attempts_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_assessment_attempts')),
        sa.UniqueConstraint('assessment_id', 'enrolment_id', 'attempt_number', name='uq_assessment_attempts_assessment_id'),
    )
    op.create_index(op.f('ix_assessment_attempts_assessment_id'), 'assessment_attempts', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_enrolment_id'), 'assessment_attempts', ['enrolment_id'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_user_id'), 'assessment_attempts', ['user_id'], unique=False)

    op.create_table(
        'certificates',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('course_id', sa.UUID(), nullable=False),
        sa.Column('enrolment_id', sa.UUID(), nullable=False),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('attempt_id', sa.UUID(), nullable=False),
        sa.Column('reference', sa.String(length=40), nullable=False),
        sa.Column('learner_name', sa.String(length=300), nullable=False),
        sa.Column('course_title', sa.String(length=500), nullable=False),
        sa.Column('score_percent', sa.Integer(), nullable=False),
        sa.Column('completed_lessons', sa.Integer(), nullable=False),
        sa.Column('total_lessons', sa.Integer(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('score_percent >= 0 AND score_percent <= 100', name='ck_certificates_score_range'),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_certificates_assessment_id_assessments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attempt_id'], ['assessment_attempts.id'], name=op.f('fk_certificates_attempt_id_assessment_attempts'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_certificates_course_id_courses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enrolment_id'], ['learner_enrolments.id'], name=op.f('fk_certificates_enrolment_id_learner_enrolments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_certificates_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_certificates')),
        sa.UniqueConstraint('reference', name=op.f('uq_certificates_reference')),
        sa.UniqueConstraint('user_id', 'course_id', name='uq_certificates_user_id'),
    )
    op.create_index(op.f('ix_certificates_course_id'), 'certificates', ['course_id'], unique=False)
    op.create_index(op.f('ix_certificates_enrolment_id'), 'certificates', ['enrolment_id'], unique=False)
    op.create_index(op.f('ix_certificates_user_id'), 'certificates', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop attempt and certificate tables."""
    op.drop_index(op.f('ix_certificates_user_id'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_enrolment_id'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_course_id'), table_name='certificates')
    op.drop_table('certificates')
    op.drop_index(op.f('ix_assessment_attempts_user_id'), table_name='assessment_attempts')
    op.drop_index(op.f('ix_assessment_attempts_enrolment_id'), table_name='assessment_attempts')
    op.drop_index(op.f('ix_assessment_attempts_assessment_id'), table_name='assessment_attempts')
    op.drop_table('assessment_attempts')
