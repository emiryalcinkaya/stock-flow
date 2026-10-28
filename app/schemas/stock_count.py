from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _empty_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class StockCountCreate(BaseModel):
    # The default warehouse when omitted.
    warehouse_id: Optional[int] = None
    # Count only one category instead of every product.
    category_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=500)

    _clean_note = field_validator("note", mode="before")(_empty_to_none)


class CountedLine(BaseModel):
    product_id: int
    # null clears a previously entered count.
    counted_quantity: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=3)


class StockCountUpdate(BaseModel):
    lines: List[CountedLine] = Field(default_factory=list, max_length=5000)


class StockCountLineResponse(BaseModel):
    product_id: int
    product_name: Optional[str]
    product_barcode: Optional[str]
    unit: Optional[str]
    expected_quantity: float
    counted_quantity: Optional[float]
    difference: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class StockCountResponse(BaseModel):
    id: int
    warehouse_id: int
    warehouse_name: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str]
    status: str
    note: Optional[str]
    created_by_name: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    line_count: int
    counted_count: int

    model_config = ConfigDict(from_attributes=True)


class StockCountDetailResponse(StockCountResponse):
    lines: List[StockCountLineResponse]
