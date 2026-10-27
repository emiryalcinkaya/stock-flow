from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_user, require_role
from app.db.models.product import Product
from app.db.models.stock_movement import MovementReason, StockMovement
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockMovementResponse,
    StockUpdate,
)
from app.services.stock import change_stock, get_product_for_update

router = APIRouter(prefix="/products", tags=["products"])


def _ensure_barcode_free(db: Session, barcode: str, exclude_id: Optional[int] = None) -> None:
    query = db.query(Product).filter(Product.barcode == barcode)
    if exclude_id is not None:
        query = query.filter(Product.id != exclude_id)

    existing = query.first()
    if not existing:
        return

    if existing.is_active:
        raise HTTPException(status_code=400, detail="Barcode already exists")

    raise HTTPException(
        status_code=400,
        detail="Barcode belongs to an archived product. Restore it instead of creating a new one.",
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # Unique barcode race between two requests, or a check constraint.
        db.rollback()
        raise HTTPException(status_code=400, detail="Product violates a data constraint") from None


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    _ensure_barcode_free(db, data.barcode)

    product = Product(
        name=data.name,
        barcode=data.barcode,
        price=data.price,
        stock_quantity=0,
        is_active=True,
    )
    db.add(product)
    db.flush()

    change_stock(db, product, data.stock_quantity, MovementReason.INITIAL, user_id=current_user.id)

    _commit(db)
    db.refresh(product)
    return product


@router.get("/", response_model=List[ProductResponse])
def get_products(
    status: Literal["active", "archived"] = "active",
    search: Optional[str] = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status == "archived" and current_user.role.name != ADMIN:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    query = db.query(Product).filter(Product.is_active.is_(status == "active"))

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.barcode.ilike(pattern)))

    return query.order_by(Product.id).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active.is_(True),
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)

    if data.barcode is not None and data.barcode != product.barcode:
        _ensure_barcode_free(db, data.barcode, exclude_id=product_id)
        product.barcode = data.barcode

    if data.name is not None:
        product.name = data.name

    if data.price is not None:
        product.price = data.price

    if data.stock_quantity is not None:
        change_stock(
            db,
            product,
            data.stock_quantity - product.stock_quantity,
            MovementReason.ADJUSTMENT,
            user_id=current_user.id,
        )

    _commit(db)
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def archive_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)
    product.is_active = False
    db.commit()

    return {"message": "Product archived successfully"}


@router.post("/{product_id}/restore", response_model=ProductResponse)
def restore_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id, active_only=False)

    if product.is_active:
        raise HTTPException(status_code=400, detail="Product is already active")

    product.is_active = True
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/increase-stock", response_model=ProductResponse)
def increase_stock(
    product_id: int,
    data: StockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)
    change_stock(db, product, data.quantity, MovementReason.RESTOCK, user_id=current_user.id)

    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/decrease-stock", response_model=ProductResponse)
def decrease_stock(
    product_id: int,
    data: StockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)
    change_stock(db, product, -data.quantity, MovementReason.STOCK_OUT, user_id=current_user.id)

    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/movements", response_model=List[StockMovementResponse])
def get_stock_movements(
    product_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    if not db.query(Product.id).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Product not found")

    return (
        db.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
