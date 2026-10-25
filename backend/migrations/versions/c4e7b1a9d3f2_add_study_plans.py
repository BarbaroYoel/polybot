"""add study plans and their schedule

Revision ID: c4e7b1a9d3f2
Revises: b5d2f8a1c3e4
Create Date: 2026-10-25 09:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e7b1a9d3f2"
down_revision: str | Sequence[str] | None = "b5d2f8a1c3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "study_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("goal", sa.String(length=200), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("adjusted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # One plan per language: the API answers 409 before this is ever violated.
        sa.UniqueConstraint("language_id"),
    )

    op.create_table(
        "plan_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plan_sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_plan_sessions_plan_week_position", ["plan_id", "week", "position"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("plan_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_plan_sessions_plan_week_position")
    op.drop_table("plan_sessions")

    op.drop_table("study_plans")
