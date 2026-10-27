from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    _strip_name = field_validator("name", mode="before")(_strip)


class CategoryResponse(BaseModel):
    id: int
    name: str
    product_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    _strip_name = field_validator("name", mode="before")(_strip)


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

    _strip_name = field_validator("name", mode="before")(_strip)


class WarehouseResponse(BaseModel):
    id: int
    name: str
    is_default: bool
    is_active: bool
    product_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class UnitResponse(BaseModel):
    code: str
    label: str
    whole: bool
