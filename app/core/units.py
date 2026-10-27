from decimal import Decimal

# Units a product can be counted in. "Whole" units only accept integer quantities.
UNITS = {
    "pcs": {"label": "Piece", "whole": True},
    "box": {"label": "Box", "whole": True},
    "pack": {"label": "Pack", "whole": True},
    "kg": {"label": "Kilogram", "whole": False},
    "g": {"label": "Gram", "whole": False},
    "l": {"label": "Litre", "whole": False},
    "ml": {"label": "Millilitre", "whole": False},
    "m": {"label": "Metre", "whole": False},
}

DEFAULT_UNIT = "pcs"


def is_whole_unit(unit: str) -> bool:
    return UNITS.get(unit, UNITS[DEFAULT_UNIT])["whole"]


def is_valid_quantity_for_unit(quantity: Decimal, unit: str) -> bool:
    return not is_whole_unit(unit) or quantity == quantity.to_integral_value()
