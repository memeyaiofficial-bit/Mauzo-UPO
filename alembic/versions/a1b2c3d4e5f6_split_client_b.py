"""Move Client B into its own business."""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "3de8a4c2f170"
branch_labels = None
depends_on = None

CLIENT_B_EMAIL = "ivysandra011@gmail.com"   # <-- 1. put Client B's email here (lowercase)
CLIENT_B_SHOP_NAME = "Client B Shop"     # <-- 2. put Client B's shop name here


def upgrade() -> None:
    bind = op.get_bind()

    user = bind.execute(
        sa.text("SELECT id, business_id FROM users WHERE email = :e"),
        {"e": CLIENT_B_EMAIL},
    ).first()
    if user is None:
        return

    others = bind.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE business_id = :b AND id != :u"),
        {"b": user.business_id, "u": user.id},
    ).scalar()
    if not others:
        return

    new_id = bind.execute(
        sa.text("INSERT INTO businesses (name) VALUES (:n) RETURNING id"),
        {"n": CLIENT_B_SHOP_NAME},
    ).scalar()

    bind.execute(
        sa.text("UPDATE users SET business_id = :b WHERE id = :u"),
        {"b": new_id, "u": user.id},
    )


def downgrade() -> None:
    pass