"""Add a database default for legacy users.created_at."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3de8a4c2f170"
down_revision: Union[str, None] = "2b6d0f4a91ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"]: column for column in inspector.get_columns("users")}
    created_at = columns.get("created_at")
    if created_at is None:
        return

    bind.execute(
        sa.text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "created_at",
            existing_type=created_at["type"],
            existing_nullable=created_at["nullable"],
            nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    raise RuntimeError(
        "The users.created_at default is retained for compatibility with account creation."
    )
