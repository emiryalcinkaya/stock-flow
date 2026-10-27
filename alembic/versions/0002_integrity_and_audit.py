"""Money as NUMERIC, stock constraints, sale snapshots, cancellation and stock audit log

Revision ID: 0002_integrity_and_audit
Revises: 0001_initial
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_integrity_and_audit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(10, 2)


def upgrade() -> None:
    # --- users -------------------------------------------------------------
    op.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    op.alter_column("users", "is_active", nullable=False, server_default=sa.true())

    # --- products ----------------------------------------------------------
    op.execute("UPDATE products SET stock_quantity = 0 WHERE stock_quantity IS NULL")
    op.alter_column("products", "stock_quantity", nullable=False, server_default="0")
    op.alter_column(
        "products", "price",
        type_=MONEY, postgresql_using="round(price::numeric, 2)",
    )
    op.create_check_constraint("ck_products_stock_non_negative", "products", "stock_quantity >= 0")
    op.create_check_constraint("ck_products_price_positive", "products", "price > 0")

    # --- sales -------------------------------------------------------------
    op.alter_column(
        "sales", "total_price",
        type_=MONEY, postgresql_using="round(total_price::numeric, 2)",
    )
    op.add_column(
        "sales",
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
    )
    op.add_column("sales", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("sales", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sales",
        sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_sales_user_id", "sales", ["user_id"])
    op.create_index("ix_sales_created_at", "sales", ["created_at"])

    # --- sale_items --------------------------------------------------------
    op.alter_column("sale_items", "sale_id", nullable=False)
    op.alter_column("sale_items", "product_id", nullable=False)
    op.alter_column(
        "sale_items", "unit_price",
        type_=MONEY, postgresql_using="round(unit_price::numeric, 2)",
    )
    op.alter_column(
        "sale_items", "total_price",
        type_=MONEY, postgresql_using="round(total_price::numeric, 2)",
    )
    op.add_column("sale_items", sa.Column("product_name", sa.String(), nullable=True))
    op.add_column("sale_items", sa.Column("product_barcode", sa.String(), nullable=True))
    # Best effort backfill: historical rows get the product's current name.
    op.execute(
        """
        UPDATE sale_items si
        SET product_name = p.name, product_barcode = p.barcode
        FROM products p
        WHERE p.id = si.product_id
        """
    )
    op.alter_column("sale_items", "product_name", nullable=False)
    op.alter_column("sale_items", "product_barcode", nullable=False)
    op.create_check_constraint("ck_sale_items_quantity_positive", "sale_items", "quantity > 0")
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"])

    # --- stock_movements ---------------------------------------------------
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id"), nullable=True),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("change <> 0", name="ck_stock_movements_change_non_zero"),
    )
    op.create_index("ix_stock_movements_id", "stock_movements", ["id"])
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])

    # Opening balance so the audit log matches current stock levels.
    op.execute(
        """
        INSERT INTO stock_movements (product_id, change, quantity_after, reason)
        SELECT id, stock_quantity, stock_quantity, 'initial'
        FROM products
        WHERE stock_quantity > 0
        """
    )


def downgrade() -> None:
    op.drop_table("stock_movements")

    op.drop_index("ix_sale_items_product_id", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_constraint("ck_sale_items_quantity_positive", "sale_items", type_="check")
    op.drop_column("sale_items", "product_barcode")
    op.drop_column("sale_items", "product_name")
    op.alter_column("sale_items", "total_price", type_=sa.Float())
    op.alter_column("sale_items", "unit_price", type_=sa.Float())
    op.alter_column("sale_items", "product_id", nullable=True)
    op.alter_column("sale_items", "sale_id", nullable=True)

    op.drop_index("ix_sales_created_at", table_name="sales")
    op.drop_index("ix_sales_user_id", table_name="sales")
    op.drop_column("sales", "cancelled_by_id")
    op.drop_column("sales", "cancelled_at")
    op.drop_column("sales", "user_id")
    op.drop_column("sales", "status")
    op.alter_column("sales", "total_price", type_=sa.Float())

    op.drop_constraint("ck_products_price_positive", "products", type_="check")
    op.drop_constraint("ck_products_stock_non_negative", "products", type_="check")
    op.alter_column("products", "price", type_=sa.Float())
    op.alter_column("products", "stock_quantity", nullable=True, server_default=None)

    op.alter_column("users", "is_active", nullable=True, server_default=None)
