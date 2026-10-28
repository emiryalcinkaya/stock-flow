from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, get_current_user, require_role
from app.core.config import settings
from app.core.units import UNITS, is_valid_quantity_for_unit
from app.db.models.category import Category
from app.db.models.product import Product
from app.db.models.stock_movement import MovementReason, StockMovement
from app.db.models.supplier import Supplier
from app.db.models.user import User
from app.db.models.warehouse import StockLevel
from app.db.session import get_db
from app.schemas.product import (
    ImportResult,
    ProductCreate,
    ProductImport,
    ProductResponse,
    ProductUpdate,
    StockIn,
    StockLevelResponse,
    StockMovementResponse,
    StockTransfer,
    StockUpdate,
)
from app.services.csv_io import csv_response, format_number, parse_decimal, read_rows
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

CSV_COLUMNS = ["barcode", "name", "category", "unit", "price", "cost_price", "min_stock", "stock_quantity"]
MAX_IMPORT_ROWS = 5000


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


def _filtered_products(
    db: Session,
    status: str,
    search: Optional[str],
    category_id: Optional[int],
    low_stock: bool,
):
    query = db.query(Product).filter(Product.is_active.is_(status == "active"))

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.barcode.ilike(pattern)))
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if low_stock:
        query = query.filter(Product.low_stock_condition())
    return query


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
        cost_price=data.cost_price,
        min_stock=data.min_stock,
        stock_quantity=0,
        is_active=True,
    )
    db.add(product)
    db.flush()

    change_stock(
        db, product, warehouse, data.stock_quantity, MovementReason.INITIAL,
        user_id=current_user.id, unit_cost=data.cost_price,
    )

    _commit(db)
    db.refresh(product)
    return product


@router.get("/", response_model=List[ProductResponse])
def get_products(
    response: Response,
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

    query = _filtered_products(db, status, search, category_id, low_stock)
    # Lets the UI show "1–50 of 230" and page through the results.
    response.headers["X-Total-Count"] = str(query.count())

    # Product.id breaks ties so the order is stable across pages.
    return (
        query.options(joinedload(Product.category))
        .order_by(*_SORT_ORDER[sort](), Product.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/export.csv")
def export_products(
    delimiter: Literal["comma", "semicolon"] = "comma",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All active products, in the same format the import accepts."""
    decimal_comma = delimiter == "semicolon"
    products = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.is_active.is_(True))
        .order_by(Product.id)
        .all()
    )
    rows = (
        [
            p.barcode,
            p.name,
            p.category_name,
            p.unit,
            format_number(p.price, decimal_comma),
            format_number(p.cost_price, decimal_comma),
            format_number(p.min_stock, decimal_comma),
            format_number(p.stock_quantity, decimal_comma),
        ]
        for p in products
    )
    return csv_response("products.csv", CSV_COLUMNS, rows, ";" if decimal_comma else ",")


@router.post("/import", response_model=ImportResult)
def import_products(
    data: ProductImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    """Create or update products from CSV text.

    New barcodes are created (with stock_quantity as opening stock); existing
    barcodes are updated. Stock of existing products is never changed here:
    that would hide real differences, use a stock count instead.
    Nothing is saved if any row has an error, and nothing is saved on a dry run.
    """
    try:
        rows = read_rows(data.csv)
    except Exception:
        raise HTTPException(status_code=400, detail="The file could not be read as CSV") from None

    if not rows:
        raise HTTPException(status_code=400, detail="The file has no data rows")
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_IMPORT_ROWS} rows can be imported at once")

    missing = {"barcode", "name"} - set(rows[0])
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(sorted(missing))}")

    warehouse = get_warehouse(db, data.warehouse_id)
    categories = {c.name.lower(): c for c in db.query(Category).all()}
    existing = {p.barcode: p for p in db.query(Product).all()}

    result = ImportResult()
    seen_barcodes = set()

    for number, row in enumerate(rows, start=2):  # row 1 is the header
        barcode, name = row.get("barcode", ""), row.get("name", "")
        try:
            if not barcode or not name:
                raise ValueError("barcode and name are required")
            if len(barcode) > 100 or len(name) > 100:
                raise ValueError("barcode and name can be at most 100 characters")
            if barcode in seen_barcodes:
                raise ValueError(f"barcode {barcode} appears more than once")
            seen_barcodes.add(barcode)

            unit = (row.get("unit") or "pcs").lower()
            if unit not in UNITS:
                raise ValueError(f"unknown unit '{unit}'")

            price = parse_decimal(row.get("price", ""))
            cost_price = parse_decimal(row.get("cost_price", ""))
            min_stock = parse_decimal(row.get("min_stock", ""))
            stock = parse_decimal(row.get("stock_quantity", ""))
            if stock is None:
                stock = Decimal("0")
            if price is not None and price <= 0:
                raise ValueError("price must be greater than 0")
            for label, value in (("cost_price", cost_price), ("min_stock", min_stock), ("stock_quantity", stock)):
                if value is not None and value < 0:
                    raise ValueError(f"{label} can't be negative")
            if not is_valid_quantity_for_unit(stock, unit):
                raise ValueError(f"stock must be a whole number for unit '{unit}'")
        except ValueError as error:
            result.errors.append({"row": number, "message": str(error)})
            continue

        category_name = row.get("category", "")
        category = None
        if category_name:
            category = categories.get(category_name.lower())
            if category is None:
                category = Category(name=category_name[:100])
                categories[category_name.lower()] = category
                db.add(category)
                result.categories_created += 1

        product = existing.get(barcode)
        if product is not None and not product.is_active:
            result.errors.append({"row": number, "message": f"barcode {barcode} belongs to an archived product"})
            continue

        if product is None:
            product = Product(
                name=name, barcode=barcode, category=category, unit=unit,
                price=price, cost_price=cost_price, min_stock=min_stock,
                stock_quantity=0, is_active=True,
            )
            db.add(product)
            db.flush()
            change_stock(
                db, product, warehouse, stock, MovementReason.INITIAL,
                user_id=current_user.id, unit_cost=cost_price, note="CSV import",
            )
            result.created += 1
            continue

        if unit != product.unit and not is_valid_quantity_for_unit(product.stock_quantity, unit):
            result.errors.append({"row": number, "message": f"current stock can't be counted in '{unit}'"})
            continue

        product.name, product.unit = name, unit
        product.price, product.cost_price, product.min_stock = price, cost_price, min_stock
        if category is not None:
            product.category = category
        if stock and stock != product.stock_quantity:
            result.warnings.append(
                {"row": number, "message": f"stock of {barcode} was not changed; use a stock count for that"}
            )
        result.updated += 1

    if result.errors or data.dry_run:
        db.rollback()
        result.saved = False
        return result

    _commit(db)
    result.saved = True
    return result


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

    # These can be cleared by sending null explicitly.
    if "category_id" in sent:
        _ensure_category_exists(db, data.category_id)
        product.category_id = data.category_id
    if "price" in sent:
        product.price = data.price
    if "cost_price" in sent:
        product.cost_price = data.cost_price
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
    data: StockIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    product = get_product_for_update(db, product_id)
    warehouse = get_warehouse(db, data.warehouse_id)

    if data.supplier_id is not None:
        supplier = db.get(Supplier, data.supplier_id)
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail="Supplier not found")

    change_stock(
        db, product, warehouse, data.quantity, MovementReason.RESTOCK,
        user_id=current_user.id, note=data.note,
        supplier_id=data.supplier_id, unit_cost=data.unit_cost, document_no=data.document_no,
    )
    # The latest purchase price becomes the product's cost.
    if data.unit_cost is not None:
        product.cost_price = data.unit_cost

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
        .options(
            joinedload(StockMovement.user),
            joinedload(StockMovement.warehouse),
            joinedload(StockMovement.supplier),
        )
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
