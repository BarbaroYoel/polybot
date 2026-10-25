"""add lessons and attempts

Revision ID: b5d2f8a1c3e4
Revises: a1c9f3e5d7b2
Create Date: 2026-10-24 10:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d2f8a1c3e4"
down_revision: str | Sequence[str] | None = "a1c9f3e5d7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lesson_units",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_units", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_units_language_position", ["language_id", "position"], unique=False
        )

    op.create_table(
        "lessons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=2), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["lesson_units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.create_index("ix_lessons_language", ["language_id"], unique=False)
        batch_op.create_index("ix_lessons_unit_position", ["unit_id", "position"], unique=False)

    op.create_table(
        "lesson_exercises",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_exercises", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_exercises_lesson_position", ["lesson_id", "position"], unique=False
        )

    op.create_table(
        "lesson_exercise_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exercise_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["lesson_exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_exercise_answers", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_exercise_answers_exercise_position",
            ["exercise_id", "position"],
            unique=False,
        )

    op.create_table(
        "lesson_vocabulary",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("term", sa.String(length=120), nullable=False),
        sa.Column("translation", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_vocabulary", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_vocabulary_lesson_position", ["lesson_id", "position"], unique=False
        )

    op.create_table(
        "lesson_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_attempts", schema=None) as batch_op:
        batch_op.create_index(
            "ix_lesson_attempts_language_lesson", ["language_id", "lesson_id"], unique=False
        )

    op.create_table(
        "lesson_attempt_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("exercise_id", sa.String(length=36), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["lesson_exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lesson_attempt_answers", schema=None) as batch_op:
        batch_op.create_index("ix_lesson_attempt_answers_attempt", ["attempt_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("lesson_attempt_answers", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_attempt_answers_attempt")
    op.drop_table("lesson_attempt_answers")

    with op.batch_alter_table("lesson_vocabulary", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_vocabulary_lesson_position")
    op.drop_table("lesson_vocabulary")

    with op.batch_alter_table("lesson_attempts", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_attempts_language_lesson")
    op.drop_table("lesson_attempts")

    with op.batch_alter_table("lesson_exercise_answers", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_exercise_answers_exercise_position")
    op.drop_table("lesson_exercise_answers")

    with op.batch_alter_table("lesson_exercises", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_exercises_lesson_position")
    op.drop_table("lesson_exercises")

    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.drop_index("ix_lessons_unit_position")
        batch_op.drop_index("ix_lessons_language")
    op.drop_table("lessons")

    with op.batch_alter_table("lesson_units", schema=None) as batch_op:
        batch_op.drop_index("ix_lesson_units_language_position")
    op.drop_table("lesson_units")
