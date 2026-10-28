from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, get_current_user, require_role
from app.core.config import settings
from app.core.units import is_valid_quantity_for_unit
from app.db.models.category import Category
from app.db.models.product import Product
from app.db.models.stock_movement import MovementReason, StockMovement
from app.db.models.user import User
from app.db.models.warehouse import StockLevel
from app.db.session import get_db
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockLevelResponse,
    StockMovementResponse,
    StockTransfer,
    StockUpdate,
)
from app.services.stock import change_stock, get_product_for_update, get_warehouse

router = APIRouter(prefix="/products", tags=["products"])

ProductSort = Literal[
    "id", "newest", "name", "stock_asc", "stock_desc", "price_asc", "price_desc", "low_stock_first"
]

_SORT_ORDER = {
    "id": lambda: [],
    "newest": lambda: [Product.id.desc()],
    "name": lambda: [func.lower(Product.name)],
    "stock_asc": lambda: [Product.stock_quantity],
    "stock_desc": lambda: [Product.stock_quantity.desc()],
    # Products without a price go last in both directions.
    "price_asc": lambda: [Product.price.asc().nulls_last()],
    "price_desc": lambda: [Product.price.desc().nulls_last()],
    # Furthest below its own minimum comes first.
    "low_stock_first": lambda: [
        Product.stock_quantity - func.coalesce(Product.min_stock, settings.low_stock_threshold)
    ],
}


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


def _ensure_category_exists(db: Session, category_id: Optional[int]) -> None:
    if category_id is not None and not db.get(Category, category_id):
        raise HTTPException(status_code=404, detail="Category not found")


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
    _ensure_category_exists(db, data.category_id)
    warehouse = get_warehouse(db, data.warehouse_id)

    product = Product(
        name=data.name,
        barcode=data.barcode,
        category_id=data.category_id,
        unit=data.unit,
        price=data.price,
        min_stock=data.min_stock,
        stock_quantity=0,
        is_active=True,
    )
    db.add(product)
    db.flush()

    change_stock(db, product, warehouse, data.stock_quantity, MovementReason.INITIAL, user_id=current_user.id)

    _commit(db)
    db.refresh(product)
    return product


@router.get("/", response_model=List[ProductResponse])
def get_products(
    status: Literal["active", "archived"] = "active",
    search: Optional[str] = Query(default=None, max_length=100),
    category_id: Optional[int] = None,
    low_stock: bool = False,
    sort: ProductSort = "id",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status == "archived" and current_user.role.name != ADMIN:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    query = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.is_active.is_(status == "active"))
    )

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.barcode.ilike(pattern)))
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if low_stock:
        query = query.filter(Product.low_stock_condition())

    # Product.id breaks ties so the order is stable across pages.
    return query.order_by(*_SORT_ORDER[sort](), Product.id).offset(skip).limit(limit).all()


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
    sent = data.model_fields_set

    if data.barcode is not None and data.barcode != product.barcode:
        _ensure_barcode_free(db, data.barcode, exclude_id=product_id)
        product.barcode = data.barcode

    if data.name is not None:
        product.name = data.name

    if data.unit is not None and data.unit != product.unit:
        if not is_valid_quantity_for_unit(product.stock_quantity, data.unit):
            raise HTTPException(
                status_code=400,
                detail=f"Current stock ({product.stock_quantity.normalize()}) is not a whole number "
                f"and can't be counted in '{data.unit}'",
            )
        product.unit = data.unit

    # These three can be cleared by sending null explicitly.
    if "category_id" in sent:
        _ensure_category_exists(db, data.category_id)
        product.category_id = data.category_id
    if "price" in sent:
        product.price = data.price
    if "min_stock" in sent:
        product.min_stock = data.min_stock

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
    warehouse = get_warehouse(db, data.warehouse_id)
    change_stock(
        db, product, warehouse, data.quantity, MovementReason.RESTOCK,
        user_id=current_user.id, note=data.note,
    )

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
    warehouse = get_warehouse(db, data.warehouse_id)
    change_stock(
        db, product, warehouse, -data.quantity, MovementReason.STOCK_OUT,
        user_id=current_user.id, note=data.note,
    )

    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/transfer", response_model=ProductResponse)
def transfer_stock(
    product_id: int,
    data: StockTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)
    source = get_warehouse(db, data.from_warehouse_id)
    destination = get_warehouse(db, data.to_warehouse_id)

    change_stock(
        db, product, source, -data.quantity, MovementReason.TRANSFER_OUT,
        user_id=current_user.id, note=data.note,
    )
    change_stock(
        db, product, destination, data.quantity, MovementReason.TRANSFER_IN,
        user_id=current_user.id, note=data.note,
    )

    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/stock-levels", response_model=List[StockLevelResponse])
def get_stock_levels(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Product.id).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Product not found")

    return (
        db.query(StockLevel)
        .options(joinedload(StockLevel.warehouse))
        .filter(StockLevel.product_id == product_id)
        .order_by(StockLevel.warehouse_id)
        .all()
    )


@router.get("/{product_id}/movements", response_model=List[StockMovementResponse])
def get_stock_movements(
    product_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Product.id).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Product not found")

    return (
        db.query(StockMovement)
        .options(joinedload(StockMovement.user), joinedload(StockMovement.warehouse))
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
