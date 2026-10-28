"""add exercise kind and options

Revision ID: f7b5c9d3e2a1
Revises: e6a4b8c2d1f3
Create Date: 2026-10-26 22:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7b5c9d3e2a1"
down_revision: str | Sequence[str] | None = "e6a4b8c2d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ADR-021: `choice` joins `writing` as an exercise type. The server default keeps every
    # existing row valid without a backfill: those exercises are all written answers.
    with op.batch_alter_table("lesson_exercises", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=12), nullable=False, server_default="writing")
        )
        batch_op.add_column(sa.Column("options_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("lesson_exercises", schema=None) as batch_op:
        batch_op.drop_column("options_json")
        batch_op.drop_column("kind")
