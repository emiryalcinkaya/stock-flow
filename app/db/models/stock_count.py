from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.product import QUANTITY


class StockCountStatus:
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StockCount(Base):
    """A physical count of one warehouse. Completing it corrects stock to the counted amounts."""

    __tablename__ = "stock_counts"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default=StockCountStatus.OPEN, server_default=StockCountStatus.OPEN)
    note = Column(String(500), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    warehouse = relationship("Warehouse")
    category = relationship("Category")
    created_by = relationship("User", foreign_keys=[created_by_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])
    lines = relationship(
        "StockCountLine",
        back_populates="stock_count",
        cascade="all, delete-orphan",
        order_by="StockCountLine.id",
    )

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None

    @property
    def category_name(self):
        return self.category.name if self.category else None

    @property
    def created_by_name(self):
        return self.created_by.full_name if self.created_by else None

    @property
    def line_count(self):
        return len(self.lines)

    @property
    def counted_count(self):
        return sum(1 for line in self.lines if line.counted_quantity is not None)


class StockCountLine(Base):
    __tablename__ = "stock_count_lines"
    __table_args__ = (
        CheckConstraint("counted_quantity >= 0", name="ck_stock_count_lines_counted_non_negative"),
    )

    id = Column(Integer, primary_key=True)
    stock_count_id = Column(Integer, ForeignKey("stock_counts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    # Quantity in the system when the count started, and when it was completed.
    expected_quantity = Column(QUANTITY, nullable=False)
    counted_quantity = Column(QUANTITY, nullable=True)
    # Filled in on completion: counted - system quantity at that moment.
    difference = Column(QUANTITY, nullable=True)

    stock_count = relationship("StockCount", back_populates="lines")
    product = relationship("Product")

    @property
    def product_name(self):
        return self.product.name if self.product else None

    @property
    def product_barcode(self):
        return self.product.barcode if self.product else None

    @property
    def unit(self):
        return self.product.unit if self.product else None
