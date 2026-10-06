"""Add business tenants and backfill existing records to the showcase shop."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e83f9c02a71d"
down_revision: Union[str, None] = "d0c0sm3t1c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = (
    "users",
    "audit_logs",
    "suppliers",
    "products",
    "inventory",
    "customers",
    "sales",
    "sale_items",
    "purchase_orders",
    "po_items",
    "product_alerts",
    "mpesa_transactions",
)
NULLABLE_TENANT_TABLES = {"audit_logs", "mpesa_transactions"}
LEGACY_UNIQUE_FIELDS = {
    "products": "barcode",
    "suppliers": "name",
    "customers": "phone",
    "sales": "receipt_number",
    "purchase_orders": "po_number",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("businesses"):
        op.create_table(
            "businesses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    business_id = bind.execute(
        sa.text("SELECT id FROM businesses ORDER BY id LIMIT 1")
    ).scalar()
    if business_id is None:
        business_id = bind.execute(
            sa.text(
                "INSERT INTO businesses (name) VALUES (:name) RETURNING id"
            ),
            {"name": "Mauzo Showcase"},
        ).scalar()

    for table in TENANT_TABLES:
        if not inspector.has_table(table):
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "business_id" not in columns:
            op.add_column(
                table,
                sa.Column("business_id", sa.Integer(), nullable=True),
            )

        bind.execute(
            sa.text(f"UPDATE {table} SET business_id = :business_id WHERE business_id IS NULL"),
            {"business_id": business_id},
        )

        nullable = table in NULLABLE_TENANT_TABLES
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                f"fk_{table}_business_id_businesses",
                "businesses",
                ["business_id"],
                ["id"],
                ondelete="CASCADE",
            )
            if not nullable:
                batch.alter_column(
                    "business_id",
                    existing_type=sa.Integer(),
                    nullable=False,
                )
        op.create_index(
            f"ix_{table}_business_id",
            table,
            ["business_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    for table, field in LEGACY_UNIQUE_FIELDS.items():
        if not inspector.has_table(table):
            continue

        unique_constraints = [
            constraint
            for constraint in inspector.get_unique_constraints(table)
            if constraint.get("column_names") == [field]
        ]
        unique_indexes = [
            index
            for index in inspector.get_indexes(table)
            if index.get("unique")
            and index.get("column_names") == [field]
        ]
        composite_index_name = f"uq_{table}_business_{field}"
        existing_composite = any(
            index.get("name") == composite_index_name
            for index in inspector.get_indexes(table)
        )

        with op.batch_alter_table(
            table,
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch:
            for constraint in unique_constraints:
                constraint_name = constraint.get("name") or f"uq_{table}_{field}"
                batch.drop_constraint(constraint_name, type_="unique")
            for index in unique_indexes:
                batch.drop_index(index["name"])
            if not existing_composite:
                batch.create_index(
                    composite_index_name,
                    ["business_id", field],
                    unique=True,
                )


def downgrade() -> None:
    raise RuntimeError(
        "Business tenant migration is one-way; removing tenant IDs could merge business data."
    )
