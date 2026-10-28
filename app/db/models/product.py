from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.config import settings
from app.db.base import Base

QUANTITY = Numeric(12, 3)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("min_stock >= 0", name="ck_products_min_stock_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_products_cost_price_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    barcode = Column(String, unique=True, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    unit = Column(String(10), nullable=False, default="pcs", server_default="pcs")
    # Price is optional: without it the product is tracked by quantity only.
    price = Column(Numeric(10, 2), nullable=True)
    # Purchase cost; updated by the latest stock in that came with a unit cost.
    cost_price = Column(Numeric(10, 2), nullable=True)
    # Per-product warning level; falls back to the global low_stock_threshold when empty.
    min_stock = Column(QUANTITY, nullable=True)
    # Total over all warehouses. Kept in sync with stock_levels by app.services.stock.
    stock_quantity = Column(QUANTITY, nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category")
    stock_levels = relationship("StockLevel", back_populates="product")

    @property
    def category_name(self):
        return self.category.name if self.category else None

    @property
    def low_stock_level(self):
        return self.min_stock if self.min_stock is not None else settings.low_stock_threshold

    @property
    def is_low_stock(self) -> bool:
        return self.stock_quantity < self.low_stock_level

    @classmethod
    def low_stock_condition(cls):
        """SQL version of is_low_stock, for filtering and counting."""
        return cls.stock_quantity < func.coalesce(cls.min_stock, settings.low_stock_threshold)
