from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.units import UNITS

Unit =Literal[tuple(UNITS)]  # type: ignore[valid-type]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _empty_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    barcode: str = Field(min_length=1, max_length=100)
    category_id: Optional[int] = None
    unit: Unit = "pcs"
    price: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    min_stock: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    # Warehouse for the opening stock; the default warehouse when omitted.
    warehouse_id: Optional[int] = None

    _strip_text = field_validator("name", "barcode", mode="before")(_strip)


class ProductUpdate(BaseModel):
    """Stock is not edited here: use stock in / stock out / transfer so every change is logged.

    category_id, price, cost_price and min_stock can be cleared by sending null.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category_id: Optional[int] = None
    unit: Optional[Unit] = None
    price: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    min_stock: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=3)

    _strip_text = field_validator("name", "barcode", mode="before")(_strip)


class StockUpdate(BaseModel):
    quantity: Decimal = Field(gt=0, le=1_000_000, max_digits=12, decimal_places=3)
    warehouse_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=500)

    _clean_note = field_validator("note", mode="before")(_empty_to_none)


class StockIn(StockUpdate):
    """Stock in can also record where the goods came from and what they cost."""

    supplier_id: Optional[int] = None
    unit_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    document_no: Optional[str] = Field(default=None, max_length=100)

    _clean_document = field_validator("document_no", mode="before")(_empty_to_none)


class StockTransfer(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: Decimal = Field(gt=0, le=1_000_000, max_digits=12, decimal_places=3)
    note: Optional[str] = Field(default=None, max_length=500)

    _clean_note = field_validator("note", mode="before")(_empty_to_none)

    @model_validator(mode="after")
    def check_different_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("Source and destination warehouse must be different")
        return self


class ProductResponse(BaseModel):
    id: int
    name: str
    barcode: str
    category_id: Optional[int]
    category_name: Optional[str]
    unit: str
    price: Optional[float]
    cost_price: Optional[float]
    min_stock: Optional[float]
    stock_quantity: float
    is_low_stock: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StockLevelResponse(BaseModel):
    warehouse_id: int
    warehouse_name: str
    quantity: float

    model_config = ConfigDict(from_attributes=True)


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    warehouse_name: Optional[str]
    change: float
    quantity_after: float
    reason: str
    note: Optional[str]
    sale_id: Optional[int]
    stock_count_id: Optional[int]
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    unit_cost: Optional[float]
    document_no: Optional[str]
    username: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductImport(BaseModel):
    # The CSV file's text; the browser reads the file so no upload handling is needed.
    csv: str = Field(min_length=1, max_length=5_000_000)
    dry_run: bool = True
    # Warehouse for the opening stock of new products; the default warehouse when omitted.
    warehouse_id: Optional[int] = None


class ImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    categories_created: int = 0
    errors: List[Dict] = Field(default_factory=list)
    warnings: List[Dict] = Field(default_factory=list)
    saved: bool = False
