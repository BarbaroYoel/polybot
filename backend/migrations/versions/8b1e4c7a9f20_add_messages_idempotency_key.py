"""add messages idempotency key

Revision ID: 8b1e4c7a9f20
Revises: d67156c6a83a
Create Date: 2026-10-23 00:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b1e4c7a9f20"
down_revision: str | Sequence[str] | None = "d67156c6a83a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=120), nullable=True))
        # A retried send with the same key must resolve to the same turn (F3 S4). SQLite allows
        # several NULLs in a unique index, so messages without a key keep working as before.
        batch_op.create_index(
            "ix_messages_idempotency_key",
            ["conversation_id", "idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_index("ix_messages_idempotency_key")
        batch_op.drop_column("idempotency_key")
