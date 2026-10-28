import base64
import binascii
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_LOGO_BYTES = 300 * 1024
Currency = Literal["TRY", "USD", "EUR"]
_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp|svg\+xml);base64,([A-Za-z0-9+/=]+)$")


def _empty_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class CompanyUpdate(BaseModel):
    """All fields are optional; send null to clear one."""

    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    # A data URL such as "data:image/png;base64,...".
    logo: Optional[str] = None
    currency: Optional[Currency] = None

    _clean_text = field_validator("name", "description", mode="before")(_empty_to_none)

    @field_validator("logo")
    @classmethod
    def check_logo(cls, value):
        if value is None:
            return value

        match = _DATA_URL.match(value)
        if not match:
            raise ValueError("Logo must be a PNG, JPEG, WebP or SVG image")

        try:
            size = len(base64.b64decode(match.group(2), validate=True))
        except binascii.Error:
            raise ValueError("Logo is not valid base64 data") from None

        if size > MAX_LOGO_BYTES:
            raise ValueError(f"Logo must be smaller than {MAX_LOGO_BYTES // 1024} KB")
        return value


class CompanyResponse(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    currency: str = "USD"

    model_config = ConfigDict(from_attributes=True)
