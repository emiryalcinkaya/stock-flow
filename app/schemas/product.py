from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    barcode: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(ge=0)

    _strip_text = field_validator("name", "barcode", mode="before")(_strip)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock_quantity: Optional[int] = Field(default=None, ge=0)

    _strip_text = field_validator("name", "barcode", mode="before")(_strip)


class StockUpdate(BaseModel):
    quantity: int = Field(gt=0, le=1_000_000)


class ProductResponse(BaseModel):
    id: int
    name: str
    barcode: str
    price: float
    stock_quantity: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    change: int
    quantity_after: int
    reason: str
    sale_id: Optional[int]
    username: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
