"""Normalize legacy user roles to the labels used by the current ORM."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c2d91a6e4f0"
down_revision: Union[str, None] = "1ac7e5f09b32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_LABELS = ("ADMIN", "MANAGER", "CASHIER")
ROLE_MAPPING = {
    "admin": "ADMIN",
    "manager": "MANAGER",
    "pharmacist": "MANAGER",
    "cashier": "CASHIER",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"]: column["type"] for column in inspector.get_columns("users")}
    role_type = columns.get("role")
    if role_type is None:
        return

    enum = next(
        (
            item for item in inspector.get_enums()
            if item["name"] == getattr(role_type, "name", None)
        ),
        None,
    )

    if enum:
        enum_name = bind.dialect.identifier_preparer.quote(enum["name"])
        with op.get_context().autocommit_block():
            for label in ROLE_LABELS:
                if label not in enum["labels"]:
                    bind.execute(
                        sa.text(f"ALTER TYPE {enum_name} ADD VALUE '{label}'")
                    )

    roles = {
        row[0]
        for row in bind.execute(sa.text("SELECT DISTINCT role::text FROM users"))
        if row[0] is not None
    }
    unknown_roles = sorted(
        role for role in roles if role.lower() not in ROLE_MAPPING
    )
    if unknown_roles:
        raise RuntimeError(
            "Cannot normalize users.role: unsupported legacy role value(s): "
            + ", ".join(unknown_roles)
        )

    case_parts = " ".join(
        f"WHEN '{legacy}' THEN '{normalized}'"
        for legacy, normalized in ROLE_MAPPING.items()
    )
    if enum:
        role_type_name = bind.dialect.identifier_preparer.quote(enum["name"])
        cast = f"::{role_type_name}"
    else:
        cast = ""

    bind.execute(
        sa.text(
            "UPDATE users SET role = "
            f"(CASE lower(role::text) {case_parts} END){cast} "
            "WHERE role::text <> "
            f"(CASE lower(role::text) {case_parts} END)"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "User role normalization is one-way; reverting could reintroduce invalid ORM labels."
    )
