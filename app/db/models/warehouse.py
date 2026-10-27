from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.product import QUANTITY


class Warehouse(Base):
    """A place where stock is kept. Single-location setups only use the default one."""

    __tablename__ = "warehouses"
    __table_args__ = (
        # At most one default warehouse.
        Index("uq_warehouses_single_default", "is_default", unique=True, postgresql_where=text("is_default")),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StockLevel(Base):
    """Quantity of one product in one warehouse."""

    __tablename__ = "stock_levels"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_stock_levels_quantity_non_negative"),
    )

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), primary_key=True)
    quantity = Column(QUANTITY, nullable=False, default=0, server_default="0")

    product = relationship("Product", back_populates="stock_levels")
    warehouse = relationship("Warehouse")

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None
