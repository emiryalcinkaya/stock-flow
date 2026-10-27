from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_user, require_role
from app.core.units import UNITS
from app.db.models.category import Category
from app.db.models.product import Product
from app.db.models.user import User
from app.db.models.warehouse import StockLevel, Warehouse
from app.db.session import get_db
from app.schemas.inventory import (
    CategoryCreate,
    CategoryResponse,
    UnitResponse,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)

router = APIRouter(tags=["inventory settings"])


def _commit_unique(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=detail) from None


# ----- Units -----------------------------------------------------------------


@router.get("/units", response_model=List[UnitResponse])
def get_units(current_user: User = Depends(get_current_user)):
    return [UnitResponse(code=code, label=info["label"], whole=info["whole"]) for code, info in UNITS.items()]


# ----- Categories ------------------------------------------------------------


def _category_response(category: Category, product_count: int) -> CategoryResponse:
    return CategoryResponse(id=category.id, name=category.name, product_count=product_count)


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Category, func.count(Product.id))
        .outerjoin(Product, (Product.category_id == Category.id) & Product.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.name)
        .all()
    )
    return [_category_response(category, count) for category, count in rows]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    category = Category(name=data.name)
    db.add(category)
    _commit_unique(db, "Category already exists")
    db.refresh(category)
    return _category_response(category, 0)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def rename_category(
    category_id: int,
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.name = data.name
    _commit_unique(db, "Category already exists")
    count = db.query(Product).filter(Product.category_id == category_id, Product.is_active.is_(True)).count()
    return _category_response(category, count)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Products keep existing, they just become uncategorized.
    db.query(Product).filter(Product.category_id == category_id).update({Product.category_id: None})
    db.delete(category)
    db.commit()
    return {"message": "Category deleted"}


# ----- Warehouses ------------------------------------------------------------


def _warehouse_response(db: Session, warehouse: Warehouse) -> WarehouseResponse:
    product_count = (
        db.query(StockLevel)
        .filter(StockLevel.warehouse_id == warehouse.id, StockLevel.quantity > 0)
        .count()
    )
    return WarehouseResponse(
        id=warehouse.id,
        name=warehouse.name,
        is_default=warehouse.is_default,
        is_active=warehouse.is_active,
        product_count=product_count,
    )


@router.get("/warehouses", response_model=List[WarehouseResponse])
def get_warehouses(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Warehouse)
    if not include_inactive:
        query = query.filter(Warehouse.is_active.is_(True))

    warehouses = query.order_by(Warehouse.is_default.desc(), Warehouse.name).all()
    return [_warehouse_response(db, warehouse) for warehouse in warehouses]


@router.get("/warehouses/{warehouse_id}/stock", response_model=Dict[int, float])
def get_warehouse_stock(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quantity per product id in one warehouse (products with stock only)."""
    if not db.get(Warehouse, warehouse_id):
        raise HTTPException(status_code=404, detail="Warehouse not found")

    rows = (
        db.query(StockLevel.product_id, StockLevel.quantity)
        .filter(StockLevel.warehouse_id == warehouse_id, StockLevel.quantity > 0)
        .all()
    )
    return {product_id: float(quantity) for product_id, quantity in rows}


@router.post("/warehouses", response_model=WarehouseResponse, status_code=201)
def create_warehouse(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    warehouse = Warehouse(name=data.name, is_default=False, is_active=True)
    db.add(warehouse)
    _commit_unique(db, "Warehouse already exists")
    db.refresh(warehouse)
    return _warehouse_response(db, warehouse)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    data: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).with_for_update().first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if data.name is not None:
        warehouse.name = data.name

    if data.is_active is False and warehouse.is_active:
        if warehouse.is_default:
            raise HTTPException(status_code=400, detail="The default warehouse can't be deactivated")
        has_stock = (
            db.query(StockLevel)
            .filter(StockLevel.warehouse_id == warehouse.id, StockLevel.quantity > 0)
            .first()
        )
        if has_stock:
            raise HTTPException(
                status_code=400,
                detail="Warehouse still has stock. Transfer it to another warehouse first.",
            )
        warehouse.is_active = False
    elif data.is_active is True:
        warehouse.is_active = True

    if data.is_default is True and not warehouse.is_default:
        if not warehouse.is_active:
            raise HTTPException(status_code=400, detail="An inactive warehouse can't be the default")
        db.query(Warehouse).filter(Warehouse.is_default.is_(True)).update({Warehouse.is_default: False})
        db.flush()
        warehouse.is_default = True

    _commit_unique(db, "Warehouse already exists")
    db.refresh(warehouse)
    return _warehouse_response(db, warehouse)
