"""Suppliers, purchase details on stock in, product cost price,
stock counts and business currency

Revision ID: 0005_operations
Revises: 0004_company_profile
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_operations"
down_revision = "0004_company_profile"
branch_labels = None
depends_on = None

QUANTITY = sa.Numeric(12, 3)
MONEY = sa.Numeric(10, 2)


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("contact_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_suppliers_id", "suppliers", ["id"])

    op.create_table(
        "stock_counts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_stock_counts_id", "stock_counts", ["id"])
    op.create_index("ix_stock_counts_warehouse_id", "stock_counts", ["warehouse_id"])
    op.create_index("ix_stock_counts_created_at", "stock_counts", ["created_at"])

    op.create_table(
        "stock_count_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_count_id", sa.Integer(),
            sa.ForeignKey("stock_counts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("expected_quantity", QUANTITY, nullable=False),
        sa.Column("counted_quantity", QUANTITY, nullable=True),
        sa.Column("difference", QUANTITY, nullable=True),
        sa.CheckConstraint("counted_quantity >= 0", name="ck_stock_count_lines_counted_non_negative"),
    )
    op.create_index("ix_stock_count_lines_stock_count_id", "stock_count_lines", ["stock_count_id"])

    op.add_column("products", sa.Column("cost_price", MONEY, nullable=True))
    op.create_check_constraint("ck_products_cost_price_non_negative", "products", "cost_price >= 0")

    op.add_column(
        "stock_movements",
        sa.Column("stock_count_id", sa.Integer(), sa.ForeignKey("stock_counts.id"), nullable=True),
    )
    op.add_column(
        "stock_movements",
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
    )
    op.add_column("stock_movements", sa.Column("unit_cost", MONEY, nullable=True))
    op.add_column("stock_movements", sa.Column("document_no", sa.String(100), nullable=True))
    op.create_index("ix_stock_movements_supplier_id", "stock_movements", ["supplier_id"])
    op.create_check_constraint("ck_stock_movements_unit_cost_non_negative", "stock_movements", "unit_cost >= 0")

    op.add_column("company_profile", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))


def downgrade() -> None:
    op.drop_column("company_profile", "currency")

    op.drop_constraint("ck_stock_movements_unit_cost_non_negative", "stock_movements", type_="check")
    op.drop_index("ix_stock_movements_supplier_id", table_name="stock_movements")
    op.drop_column("stock_movements", "document_no")
    op.drop_column("stock_movements", "unit_cost")
    op.drop_column("stock_movements", "supplier_id")
    op.drop_column("stock_movements", "stock_count_id")

    op.drop_constraint("ck_products_cost_price_non_negative", "products", type_="check")
    op.drop_column("products", "cost_price")

    op.drop_table("stock_count_lines")
    op.drop_table("stock_counts")
    op.drop_table("suppliers")
