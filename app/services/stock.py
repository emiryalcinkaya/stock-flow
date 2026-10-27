from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.db.models.stock_movement import StockMovement


def get_product_for_update(db: Session, product_id: int, active_only: bool = True) -> Product:
    """Load a product with a row lock so concurrent stock changes are serialized."""
    query = db.query(Product).filter(Product.id == product_id)
    if active_only:
        query = query.filter(Product.is_active.is_(True))

    product = query.with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def change_stock(
    db: Session,
    product: Product,
    change: int,
    reason: str,
    user_id: Optional[int] = None,
    sale_id: Optional[int] = None,
) -> None:
    """Apply a stock change and write it to the audit log.

    The caller is responsible for locking the product row and committing.
    """
    if change == 0:
        return

    new_quantity = product.stock_quantity + change
    if new_quantity < 0:
        raise HTTPException(status_code=400, detail=f"Not enough stock for product {product.name}")

    product.stock_quantity = new_quantity
    db.add(
        StockMovement(
            product_id=product.id,
            user_id=user_id,
            sale_id=sale_id,
            change=change,
            quantity_after=new_quantity,
            reason=reason,
        )
    )
