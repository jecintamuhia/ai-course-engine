"""add learner enrolments milestones submissions and lecturer activities

Revision ID: 88afec1453ec
Revises: c9e4a2b7f1d6
Create Date: 2026-10-22 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '88afec1453ec'
down_revision: Union[str, Sequence[str], None] = 'c9e4a2b7f1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'learner_enrolments',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('course_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'WITHDRAWN', name='enrolment_status'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_learner_enrolments_course_id_courses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learner_enrolments_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_learner_enrolments')),
        sa.UniqueConstraint('user_id', 'course_id', name='uq_learner_enrolments_user_id'),
    )
    op.create_index(op.f('ix_learner_enrolments_course_id'), 'learner_enrolments', ['course_id'], unique=False)
    op.create_index(op.f('ix_learner_enrolments_status'), 'learner_enrolments', ['status'], unique=False)
    op.create_index(op.f('ix_learner_enrolments_user_id'), 'learner_enrolments', ['user_id'], unique=False)

    op.create_table(
        'learner_milestones',
        sa.Column('enrolment_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['enrolment_id'], ['learner_enrolments.id'], name=op.f('fk_learner_milestones_enrolment_id_learner_enrolments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], name=op.f('fk_learner_milestones_lesson_id_lessons'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_learner_milestones')),
        sa.UniqueConstraint('enrolment_id', 'lesson_id', name='uq_learner_milestones_enrolment_id'),
    )
    op.create_index(op.f('ix_learner_milestones_enrolment_id'), 'learner_milestones', ['enrolment_id'], unique=False)
    op.create_index(op.f('ix_learner_milestones_lesson_id'), 'learner_milestones', ['lesson_id'], unique=False)

    op.create_table(
        'practical_submissions',
        sa.Column('enrolment_id', sa.UUID(), nullable=False),
        sa.Column('block_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('SUBMITTED', 'GRADED', 'NEEDS_REVISION', name='submission_status'), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('graded_by_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('grade >= 0 AND grade <= 100', name='grade_range'),
        sa.ForeignKeyConstraint(['block_id'], ['lesson_content_blocks.id'], name=op.f('fk_practical_submissions_block_id_lesson_content_blocks'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enrolment_id'], ['learner_enrolments.id'], name=op.f('fk_practical_submissions_enrolment_id_learner_enrolments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['graded_by_id'], ['users.id'], name=op.f('fk_practical_submissions_grading_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], name=op.f('fk_practical_submissions_lesson_id_lessons'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_practical_submissions')),
        sa.UniqueConstraint('enrolment_id', 'block_id', name='uq_practical_submissions_enrolment_id'),
    )
    op.create_index(op.f('ix_practical_submissions_block_id'), 'practical_submissions', ['block_id'], unique=False)
    op.create_index(op.f('ix_practical_submissions_enrolment_id'), 'practical_submissions', ['enrolment_id'], unique=False)
    op.create_index(op.f('ix_practical_submissions_lesson_id'), 'practical_submissions', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_practical_submissions_status'), 'practical_submissions', ['status'], unique=False)

    op.create_table(
        'lecturer_activities',
        sa.Column('course_id', sa.UUID(), nullable=False),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('subject_user_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.Enum('ENROLLED', 'WITHDREW', 'LESSON_COMPLETED', 'SUBMISSION_RECEIVED', 'SUBMISSION_GRADED', 'SUBMISSION_RETURNED', name='lecturer_activity_type'), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_lecturer_activities_actor_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_lecturer_activities_course_id_courses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_user_id'], ['users.id'], name=op.f('fk_lecturer_activities_subject_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lecturer_activities')),
    )
    op.create_index(op.f('ix_lecturer_activities_actor_user_id'), 'lecturer_activities', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_lecturer_activities_course_id'), 'lecturer_activities', ['course_id'], unique=False)
    op.create_index(op.f('ix_lecturer_activities_event_type'), 'lecturer_activities', ['event_type'], unique=False)
    op.create_index(op.f('ix_lecturer_activities_subject_user_id'), 'lecturer_activities', ['subject_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lecturer_activities_subject_user_id'), table_name='lecturer_activities')
    op.drop_index(op.f('ix_lecturer_activities_event_type'), table_name='lecturer_activities')
    op.drop_index(op.f('ix_lecturer_activities_course_id'), table_name='lecturer_activities')
    op.drop_index(op.f('ix_lecturer_activities_actor_user_id'), table_name='lecturer_activities')
    op.drop_table('lecturer_activities')
    op.drop_index(op.f('ix_practical_submissions_status'), table_name='practical_submissions')
    op.drop_index(op.f('ix_practical_submissions_lesson_id'), table_name='practical_submissions')
    op.drop_index(op.f('ix_practical_submissions_block_id'), table_name='practical_submissions')
    op.drop_index(op.f('ix_practical_submissions_enrolment_id'), table_name='practical_submissions')
    op.drop_table('practical_submissions')
    op.drop_index(op.f('ix_learner_milestones_lesson_id'), table_name='learner_milestones')
    op.drop_index(op.f('ix_learner_milestones_enrolment_id'), table_name='learner_milestones')
    op.drop_table('learner_milestones')
    op.drop_index(op.f('ix_learner_enrolments_user_id'), table_name='learner_enrolments')
    op.drop_index(op.f('ix_learner_enrolments_status'), table_name='learner_enrolments')
    op.drop_index(op.f('ix_learner_enrolments_course_id'), table_name='learner_enrolments')
    op.drop_table('learner_enrolments')
    op.execute('DROP TYPE IF EXISTS lecturer_activity_type')
    op.execute('DROP TYPE IF EXISTS submission_status')
    op.execute('DROP TYPE IF EXISTS enrolment_status')
