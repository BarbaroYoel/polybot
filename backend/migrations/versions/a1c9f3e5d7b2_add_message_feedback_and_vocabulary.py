"""add message feedback and vocabulary

Revision ID: a1c9f3e5d7b2
Revises: 8b1e4c7a9f20
Create Date: 2026-10-23 12:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c9f3e5d7b2"
down_revision: str | Sequence[str] | None = "8b1e4c7a9f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_table(
        "message_corrections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("original", sa.Text(), nullable=False),
        sa.Column("corrected", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["feedback_id"], ["message_feedback.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("message_corrections", schema=None) as batch_op:
        batch_op.create_index(
            "ix_message_corrections_feedback_position",
            ["feedback_id", "position"],
            unique=True,
        )

    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feedback_id"], ["message_feedback.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("vocabulary_items", schema=None) as batch_op:
        batch_op.create_index(
            "ix_vocabulary_items_feedback_position",
            ["feedback_id", "position"],
            unique=True,
        )
        batch_op.create_index("ix_vocabulary_items_language", ["language_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("vocabulary_items", schema=None) as batch_op:
        batch_op.drop_index("ix_vocabulary_items_language")
        batch_op.drop_index("ix_vocabulary_items_feedback_position")
    op.drop_table("vocabulary_items")

    with op.batch_alter_table("message_corrections", schema=None) as batch_op:
        batch_op.drop_index("ix_message_corrections_feedback_position")
    op.drop_table("message_corrections")

    op.drop_table("message_feedback")
