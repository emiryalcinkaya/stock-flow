from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class MovementReason:
    INITIAL = "initial"
    RESTOCK = "restock"
    STOCK_OUT = "stock_out"
    ADJUSTMENT = "adjustment"
    SALE = "sale"
    SALE_CANCELLED = "sale_cancelled"


class StockMovement(Base):
    """Audit log: every change to a product's stock creates one row."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change <> 0", name="ck_stock_movements_change_non_zero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    change = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    product = relationship("Product")
    user = relationship("User")

    @property
    def username(self):
        return self.user.username if self.user else None
