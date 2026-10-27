from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SaleStatus:
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StockOutReason:
    SALE = "sale"
    CONSUMPTION = "consumption"
    WASTE = "waste"
    RETURN_TO_SUPPLIER = "return_to_supplier"
    OTHER = "other"

    ALL = (SALE, CONSUMPTION, WASTE, RETURN_TO_SUPPLIER, OTHER)


class Sale(Base):
    """A stock-out document. A sale is one kind of stock out; others are
    internal consumption, waste, returns to the supplier and so on."""

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    reason = Column(String(30), nullable=False, default=StockOutReason.SALE, server_default=StockOutReason.SALE)
    note = Column(String(500), nullable=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default=SaleStatus.COMPLETED, server_default=SaleStatus.COMPLETED)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    warehouse = relationship("Warehouse")
    user = relationship("User", foreign_keys=[user_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])

    @property
    def cashier_name(self):
        return self.user.full_name if self.user else None

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None
