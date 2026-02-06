"""initial schema

Revision ID: 202602060001
Revises:
Create Date: 2026-02-06 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "202602060001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    order_status = sa.Enum("pending", "processing", "completed", "canceled", name="order_status")
    order_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "canceled",
                name="order_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_orders_id", "orders", ["id"], unique=False)
    op.create_index("ix_orders_title", "orders", ["title"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_index("ix_orders_user_status", "orders", ["user_id", "status"], unique=False)
    op.create_index("ix_orders_created_at", "orders", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_user_status", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_title", table_name="orders")
    op.drop_index("ix_orders_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    order_status = sa.Enum("pending", "processing", "completed", "canceled", name="order_status")
    order_status.drop(op.get_bind(), checkfirst=True)
