from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SaleStatus:
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default=SaleStatus.COMPLETED, server_default=SaleStatus.COMPLETED)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])

    @property
    def cashier_name(self):
        return self.user.full_name if self.user else None
