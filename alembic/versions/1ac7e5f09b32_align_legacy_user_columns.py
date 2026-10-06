"""Align the legacy users table with the current User ORM model."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1ac7e5f09b32"
down_revision: Union[str, None] = "f4a8c1d92e70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "name" in columns and "full_name" not in columns:
        op.alter_column(
            "users",
            "name",
            new_column_name="full_name",
            existing_type=sa.String(length=120),
            existing_nullable=False,
        )
        columns.remove("name")
        columns.add("full_name")

    missing_columns = {
        "updated_at": sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        "business_name": sa.Column(
            "business_name",
            sa.String(length=200),
            nullable=True,
        ),
        "last_login": sa.Column(
            "last_login",
            sa.DateTime(),
            nullable=True,
        ),
    }
    for name, column in missing_columns.items():
        if name not in columns:
            op.add_column("users", column)


def downgrade() -> None:
    raise RuntimeError(
        "Legacy user-column alignment is one-way to preserve existing account data."
    )
