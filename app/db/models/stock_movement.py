from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.product import QUANTITY


class MovementReason:
    INITIAL = "initial"
    RESTOCK = "restock"
    STOCK_OUT = "stock_out"
    ADJUSTMENT = "adjustment"
    SALE = "sale"
    SALE_CANCELLED = "sale_cancelled"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class StockMovement(Base):
    """Audit log: every change to a product's stock creates one row."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change <> 0", name="ck_stock_movements_change_non_zero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    change = Column(QUANTITY, nullable=False)
    # Product total over all warehouses after this movement.
    quantity_after = Column(QUANTITY, nullable=False)
    reason = Column(String(30), nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    product = relationship("Product")
    warehouse = relationship("Warehouse")
    user = relationship("User")

    @property
    def username(self):
        return self.user.username if self.user else None

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None
