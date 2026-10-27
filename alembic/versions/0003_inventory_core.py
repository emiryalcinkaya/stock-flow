"""General-purpose inventory: units, decimal quantities, categories,
per-product minimum stock, warehouses and stock-out reasons

Existing stock is moved into a default warehouse called "Main Warehouse".

Revision ID: 0003_inventory_core
Revises: 0002_integrity_and_audit
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_inventory_core"
down_revision = "0002_integrity_and_audit"
branch_labels = None
depends_on = None

QUANTITY = sa.Numeric(12, 3)


def upgrade() -> None:
    # --- categories --------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_categories_id", "categories", ["id"])

    # --- warehouses --------------------------------------------------------
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_warehouses_id", "warehouses", ["id"])
    op.create_index(
        "uq_warehouses_single_default", "warehouses", ["is_default"],
        unique=True, postgresql_where=sa.text("is_default"),
    )
    op.execute("INSERT INTO warehouses (name, is_default) VALUES ('Main Warehouse', TRUE)")
    default_warehouse = "(SELECT id FROM warehouses WHERE is_default)"

    # --- products ----------------------------------------------------------
    op.add_column(
        "products",
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.add_column("products", sa.Column("unit", sa.String(10), nullable=False, server_default="pcs"))
    op.add_column("products", sa.Column("min_stock", QUANTITY, nullable=True))
    op.create_check_constraint("ck_products_min_stock_non_negative", "products", "min_stock >= 0")
    op.alter_column("products", "price", nullable=True)
    op.alter_column("products", "stock_quantity", type_=QUANTITY, server_default="0")

    # --- stock_levels ------------------------------------------------------
    op.create_table(
        "stock_levels",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), primary_key=True),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="0"),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_levels_quantity_non_negative"),
    )
    op.execute(
        f"""
        INSERT INTO stock_levels (product_id, warehouse_id, quantity)
        SELECT id, {default_warehouse}, stock_quantity FROM products
        """
    )

    # --- stock_movements ---------------------------------------------------
    op.alter_column("stock_movements", "change", type_=QUANTITY)
    op.alter_column("stock_movements", "quantity_after", type_=QUANTITY)
    op.add_column(
        "stock_movements",
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
    )
    op.execute(f"UPDATE stock_movements SET warehouse_id = {default_warehouse}")
    op.alter_column("stock_movements", "warehouse_id", nullable=False)
    op.create_index("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"])
    op.add_column("stock_movements", sa.Column("note", sa.String(500), nullable=True))

    # --- sales (stock-out documents) ---------------------------------------
    op.add_column("sales", sa.Column("reason", sa.String(30), nullable=False, server_default="sale"))
    op.add_column("sales", sa.Column("note", sa.String(500), nullable=True))
    op.add_column("sales", sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True))
    op.execute(f"UPDATE sales SET warehouse_id = {default_warehouse}")
    op.alter_column("sales", "warehouse_id", nullable=False)
    op.create_index("ix_sales_warehouse_id", "sales", ["warehouse_id"])

    # --- sale_items --------------------------------------------------------
    op.alter_column("sale_items", "quantity", type_=QUANTITY)
    op.add_column("sale_items", sa.Column("unit", sa.String(10), nullable=False, server_default="pcs"))


def downgrade() -> None:
    op.drop_column("sale_items", "unit")
    op.alter_column("sale_items", "quantity", type_=sa.Integer(), postgresql_using="round(quantity)::integer")

    op.drop_index("ix_sales_warehouse_id", table_name="sales")
    op.drop_column("sales", "warehouse_id")
    op.drop_column("sales", "note")
    op.drop_column("sales", "reason")

    op.drop_column("stock_movements", "note")
    op.drop_index("ix_stock_movements_warehouse_id", table_name="stock_movements")
    op.drop_column("stock_movements", "warehouse_id")
    op.alter_column(
        "stock_movements", "quantity_after",
        type_=sa.Integer(), postgresql_using="round(quantity_after)::integer",
    )
    op.alter_column("stock_movements", "change", type_=sa.Integer(), postgresql_using="round(change)::integer")

    op.drop_table("stock_levels")

    op.alter_column(
        "products", "stock_quantity",
        type_=sa.Integer(), postgresql_using="round(stock_quantity)::integer", server_default="0",
    )
    op.execute("UPDATE products SET price = 0.01 WHERE price IS NULL")
    op.alter_column("products", "price", nullable=False)
    op.drop_constraint("ck_products_min_stock_non_negative", "products", type_="check")
    op.drop_column("products", "min_stock")
    op.drop_column("products", "unit")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_column("products", "category_id")

    op.drop_table("warehouses")
    op.drop_table("categories")
