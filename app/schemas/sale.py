from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.sale import StockOutReason

Reason = Literal[StockOutReason.ALL]  # type: ignore[valid-type]


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, le=1_000_000, max_digits=12, decimal_places=3)


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(min_length=1, max_length=200)
    reason: Reason = StockOutReason.SALE
    # The default warehouse when omitted.
    warehouse_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def empty_note_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SaleItemResponse(BaseModel):
    product_id: int
    product_name: str
    product_barcode: str
    unit: str
    quantity: float
    unit_price: float
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class SaleResponse(BaseModel):
    id: int
    reason: str
    note: Optional[str]
    warehouse_id: int
    warehouse_name: Optional[str]
    total_price: float
    status: str
    cashier_name: Optional[str]
    created_at: datetime
    cancelled_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SaleDetailResponse(SaleResponse):
    items: List[SaleItemResponse]
