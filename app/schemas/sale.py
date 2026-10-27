from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10_000)


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(min_length=1, max_length=200)


class SaleItemResponse(BaseModel):
    product_id: int
    product_name: str
    product_barcode: str
    quantity: int
    unit_price: float
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class SaleResponse(BaseModel):
    id: int
    total_price: float
    status: str
    cashier_name: Optional[str]
    created_at: datetime
    cancelled_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SaleDetailResponse(SaleResponse):
    items: List[SaleItemResponse]
