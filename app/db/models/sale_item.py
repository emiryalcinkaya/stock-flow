from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.models.product import QUANTITY


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # Snapshot of the product at the moment of the stock out, so later edits
    # to the product never change history.
    product_name = Column(String, nullable=False)
    product_barcode = Column(String, nullable=False)
    unit = Column(String(10), nullable=False, default="pcs", server_default="pcs")

    quantity = Column(QUANTITY, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")
