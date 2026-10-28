"""add message blocks

Revision ID: e6a4b8c2d1f3
Revises: c4e7b1a9d3f2
Create Date: 2026-10-26 21:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a4b8c2d1f3"
down_revision: str | Sequence[str] | None = "c4e7b1a9d3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ADR-020: validated practice blocks of a tutor turn, stored as a JSON array. `NULL` is a turn
    # without blocks, which is the normal case, so existing rows stay valid without a backfill.
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("blocks_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_column("blocks_json")
