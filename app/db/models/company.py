from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class CompanyProfile(Base):
    """The business using this installation. A single row (id = 1)."""

    __tablename__ = "company_profile"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=True)
    description = Column(String(300), nullable=True)
    # Small image stored as a data URL, so no file storage is needed.
    logo = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
