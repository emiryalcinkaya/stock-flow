from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.units import is_valid_quantity_for_unit
from app.db.models.product import Product
from app.db.models.stock_movement import StockMovement
from app.db.models.warehouse import StockLevel, Warehouse


def get_product_for_update(db: Session, product_id: int, active_only: bool = True) -> Product:
    """Load a product with a row lock so concurrent stock changes are serialized."""
    query = db.query(Product).filter(Product.id == product_id)
    if active_only:
        query = query.filter(Product.is_active.is_(True))

    product = query.with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def get_warehouse(db: Session, warehouse_id: Optional[int]) -> Warehouse:
    """The requested active warehouse, or the default one when no id is given."""
    query = db.query(Warehouse).filter(Warehouse.is_active.is_(True))
    if warehouse_id is None:
        warehouse = query.filter(Warehouse.is_default.is_(True)).first()
    else:
        warehouse = query.filter(Warehouse.id == warehouse_id).first()

    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


def ensure_quantity_fits_unit(product: Product, quantity: Decimal) -> None:
    if not is_valid_quantity_for_unit(Decimal(quantity), product.unit):
        raise HTTPException(
            status_code=400,
            detail=f"{product.name} is counted in '{product.unit}', so the quantity must be a whole number",
        )


def get_stock_level(db: Session, product: Product, warehouse: Warehouse) -> StockLevel:
    level = db.get(StockLevel, (product.id, warehouse.id))
    if level is None:
        level = StockLevel(product_id=product.id, warehouse_id=warehouse.id, quantity=Decimal("0"))
        db.add(level)
        # Flush so a second lookup in the same transaction finds this row.
        db.flush()
    return level


def change_stock(
    db: Session,
    product: Product,
    warehouse: Warehouse,
    change: Decimal,
    reason: str,
    user_id: Optional[int] = None,
    sale_id: Optional[int] = None,
    note: Optional[str] = None,
) -> None:
    """Apply a stock change in one warehouse and write it to the audit log.

    The caller is responsible for locking the product row and committing.
    Locking the product also serializes changes to its per-warehouse levels.
    """
    change = Decimal(change)
    if change == 0:
        return

    ensure_quantity_fits_unit(product, abs(change))

    level = get_stock_level(db, product, warehouse)
    new_level = Decimal(level.quantity) + change
    if new_level < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough stock for product {product.name} in {warehouse.name}",
        )

    level.quantity = new_level
    product.stock_quantity = Decimal(product.stock_quantity) + change

    db.add(
        StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            user_id=user_id,
            sale_id=sale_id,
            change=change,
            quantity_after=product.stock_quantity,
            reason=reason,
            note=note,
        )
    )
