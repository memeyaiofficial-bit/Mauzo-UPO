"""Provide a default for the legacy users.sms_tokens column."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b6d0f4a91ce"
down_revision: Union[str, None] = "7c2d91a6e4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"]: column for column in inspector.get_columns("users")}
    sms_tokens = columns.get("sms_tokens")
    if sms_tokens is None:
        return

    bind.execute(
        sa.text("UPDATE users SET sms_tokens = 0 WHERE sms_tokens IS NULL")
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "sms_tokens",
            existing_type=sms_tokens["type"],
            existing_nullable=sms_tokens["nullable"],
            nullable=False,
            server_default=sa.text("0"),
        )


def downgrade() -> None:
    raise RuntimeError(
        "The sms_tokens default is retained for compatibility with existing account rows."
    )
