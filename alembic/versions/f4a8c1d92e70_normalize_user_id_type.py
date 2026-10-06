"""Normalize legacy string user IDs to the integer IDs used by the ORM."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a8c1d92e70"
down_revision: Union[str, None] = "e83f9c02a71d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INTEGER_MIN = -2147483648
INTEGER_MAX = 2147483647


def _string_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    for item in inspector.get_columns(table):
        if item["name"] == column:
            return isinstance(item["type"], sa.String)
    return False


def _assert_integer_values(bind, table: str, column: str) -> None:
    invalid = bind.execute(
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE {column} IS NOT NULL
              AND ({column} !~ '^[+-]?[0-9]+$'
                   OR CASE
                       WHEN {column} ~ '^[+-]?[0-9]+$'
                       THEN {column}::numeric NOT BETWEEN :min_id AND :max_id
                       ELSE FALSE
                   END)
            """
        ),
        {"min_id": INTEGER_MIN, "max_id": INTEGER_MAX},
    ).scalar_one()
    if invalid:
        raise RuntimeError(
            f"Cannot migrate {table}.{column}: {invalid} value(s) are not "
            "representable as 32-bit integer IDs. No ID values were changed."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _string_column(bind, "users", "id"):
        return

    _assert_integer_values(bind, "users", "id")
    duplicate_ids = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT id::integer
                FROM users
                GROUP BY id::integer
                HAVING COUNT(*) > 1
            ) AS duplicate_user_ids
            """
        )
    ).scalar_one()
    if duplicate_ids:
        raise RuntimeError(
            "Cannot migrate users.id: distinct string IDs would become duplicate "
            "integer IDs. No ID values were changed."
        )

    inspector = sa.inspect(bind)
    references: list[tuple[str, str, str, dict]] = []
    for table in inspector.get_table_names():
        if table == "users":
            continue
        for foreign_key in inspector.get_foreign_keys(table):
            if (
                foreign_key.get("referred_table") == "users"
                and foreign_key.get("referred_columns") == ["id"]
            ):
                local_columns = foreign_key.get("constrained_columns") or []
                if len(local_columns) != 1:
                    raise RuntimeError(
                        f"Cannot safely migrate composite user reference on {table}."
                    )
                references.append(
                    (
                        table,
                        local_columns[0],
                        foreign_key["name"],
                        foreign_key.get("options") or {},
                    )
                )

    for table, column, _constraint_name, _options in references:
        _assert_integer_values(bind, table, column)

    for table, _column, constraint_name, _options in references:
        op.drop_constraint(constraint_name, table, type_="foreignkey")

    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(),
        type_=sa.Integer(),
        postgresql_using="id::integer",
    )
    for table, column, _constraint_name, _options in references:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(),
            type_=sa.Integer(),
            postgresql_using=f"{column}::integer",
        )

    for table, column, constraint_name, options in references:
        op.create_foreign_key(
            constraint_name,
            table,
            "users",
            [column],
            ["id"],
            ondelete=options.get("ondelete"),
            onupdate=options.get("onupdate"),
        )

    bind.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS users_id_seq"))
    bind.execute(
        sa.text(
            """
            SELECT setval(
                'users_id_seq',
                COALESCE((SELECT MAX(id) FROM users), 1),
                EXISTS (SELECT 1 FROM users)
            )
            """
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE users ALTER COLUMN id "
            "SET DEFAULT nextval('users_id_seq')"
        )
    )
    bind.execute(
        sa.text("ALTER SEQUENCE users_id_seq OWNED BY users.id")
    )


def downgrade() -> None:
    raise RuntimeError(
        "User ID type normalization is one-way; converting IDs back to strings "
        "would risk changing identity semantics."
    )
