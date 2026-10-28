from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.product import QUANTITY


class MovementReason:
    INITIAL = "initial"
    RESTOCK = "restock"
    STOCK_OUT = "stock_out"
    ADJUSTMENT = "adjustment"
    COUNT_ADJUSTMENT = "count_adjustment"
    SALE = "sale"
    SALE_CANCELLED = "sale_cancelled"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"

    # Moves between warehouses don't change the overall stock.
    TRANSFERS = (TRANSFER_IN, TRANSFER_OUT)


class StockMovement(Base):
    """Audit log: every change to a product's stock creates one row."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change <> 0", name="ck_stock_movements_change_non_zero"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_movements_unit_cost_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    stock_count_id = Column(Integer, ForeignKey("stock_counts.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    change = Column(QUANTITY, nullable=False)
    # Product total over all warehouses after this movement.
    quantity_after = Column(QUANTITY, nullable=False)
    reason = Column(String(30), nullable=False)
    # Purchase details for stock coming in from a supplier.
    unit_cost = Column(Numeric(10, 2), nullable=True)
    document_no = Column(String(100), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    product = relationship("Product")
    warehouse = relationship("Warehouse")
    user = relationship("User")
    supplier = relationship("Supplier")

    @property
    def username(self):
        return self.user.username if self.user else None

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None

    @property
    def supplier_name(self):
        return self.supplier.name if self.supplier else None
