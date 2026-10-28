import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, get_current_user, require_role
from app.core.units import is_valid_quantity_for_unit
from app.db.models.category import Category
from app.db.models.product import Product
from app.db.models.stock_count import StockCount, StockCountLine, StockCountStatus
from app.db.models.stock_movement import MovementReason
from app.db.models.user import User
from app.db.models.warehouse import StockLevel
from app.db.session import get_db
from app.schemas.stock_count import (
    StockCountCreate,
    StockCountDetailResponse,
    StockCountResponse,
    StockCountUpdate,
)
from app.services.stock import change_stock, get_warehouse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock-counts", tags=["stock counts"])


def _load(db: Session, count_id: int, lock: bool = False) -> StockCount:
    query = db.query(StockCount).filter(StockCount.id == count_id)
    if lock:
        query = query.with_for_update()
    else:
        query = query.options(
            joinedload(StockCount.lines).joinedload(StockCountLine.product),
            joinedload(StockCount.warehouse),
            joinedload(StockCount.created_by),
        )
    count = query.first()
    if not count:
        raise HTTPException(status_code=404, detail="Stock count not found")
    return count


def _ensure_open(count: StockCount) -> None:
    if count.status != StockCountStatus.OPEN:
        raise HTTPException(status_code=400, detail="This stock count is already closed")


@router.post("", response_model=StockCountDetailResponse, status_code=201)
def create_stock_count(
    data: StockCountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    warehouse = get_warehouse(db, data.warehouse_id)
    if data.category_id is not None and not db.get(Category, data.category_id):
        raise HTTPException(status_code=404, detail="Category not found")

    already_open = (
        db.query(StockCount.id)
        .filter(StockCount.warehouse_id == warehouse.id, StockCount.status == StockCountStatus.OPEN)
        .first()
    )
    if already_open:
        raise HTTPException(status_code=400, detail="This warehouse already has an open stock count")

    products = db.query(Product).filter(Product.is_active.is_(True))
    if data.category_id is not None:
        products = products.filter(Product.category_id == data.category_id)
    products = products.order_by(Product.name).all()
    if not products:
        raise HTTPException(status_code=400, detail="There are no products to count")

    levels = dict(
        db.query(StockLevel.product_id, StockLevel.quantity)
        .filter(StockLevel.warehouse_id == warehouse.id)
        .all()
    )

    count = StockCount(
        warehouse_id=warehouse.id,
        category_id=data.category_id,
        note=data.note,
        status=StockCountStatus.OPEN,
        created_by_id=current_user.id,
    )
    count.lines = [
        StockCountLine(product_id=p.id, expected_quantity=levels.get(p.id, Decimal("0"))) for p in products
    ]
    db.add(count)
    db.commit()
    return _load(db, count.id)


@router.get("", response_model=List[StockCountResponse])
def get_stock_counts(
    response: Response,
    status: Optional[str] = Query(default=None, pattern="^(open|completed|cancelled)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(StockCount)
    if status:
        query = query.filter(StockCount.status == status)
    response.headers["X-Total-Count"] = str(query.count())

    return (
        query.options(
            joinedload(StockCount.lines),
            joinedload(StockCount.warehouse),
            joinedload(StockCount.created_by),
            joinedload(StockCount.category),
        )
        .order_by(StockCount.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{count_id}", response_model=StockCountDetailResponse)
def get_stock_count(
    count_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _load(db, count_id)


@router.patch("/{count_id}", response_model=StockCountDetailResponse)
def save_counted_quantities(
    count_id: int,
    data: StockCountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any signed-in user can enter counts; only admins start, complete or cancel a count."""
    count = _load(db, count_id, lock=True)
    _ensure_open(count)

    lines = {line.product_id: line for line in count.lines}
    for entry in data.lines:
        line = lines.get(entry.product_id)
        if line is None:
            raise HTTPException(status_code=400, detail=f"Product {entry.product_id} is not part of this count")
        if entry.counted_quantity is not None and not is_valid_quantity_for_unit(
            entry.counted_quantity, line.product.unit
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{line.product.name} is counted in '{line.product.unit}', "
                "so the quantity must be a whole number",
            )
        line.counted_quantity = entry.counted_quantity

    db.commit()
    return _load(db, count_id)


@router.post("/{count_id}/complete", response_model=StockCountDetailResponse)
def complete_stock_count(
    count_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    try:
        count = _load(db, count_id, lock=True)
        _ensure_open(count)

        counted = [line for line in count.lines if line.counted_quantity is not None]
        if not counted:
            raise HTTPException(status_code=400, detail="Enter at least one counted quantity first")

        # Lock in id order, like stock outs, so concurrent changes can't interleave.
        products = {
            p.id: p
            for p in db.query(Product)
            .filter(Product.id.in_([line.product_id for line in counted]))
            .order_by(Product.id)
            .with_for_update()
            .all()
        }
        warehouse = count.warehouse

        for line in counted:
            product = products[line.product_id]
            level = db.get(StockLevel, (product.id, warehouse.id))
            # Compare against the quantity now, not when the count started: stock may
            # have moved in the meantime and those movements are already recorded.
            current = Decimal(level.quantity) if level else Decimal("0")
            difference = Decimal(line.counted_quantity) - current
            line.difference = difference
            if difference != 0:
                change_stock(
                    db, product, warehouse, difference, MovementReason.COUNT_ADJUSTMENT,
                    user_id=current_user.id, stock_count_id=count.id,
                    note=f"Stock count #{count.id}",
                )

        count.status = StockCountStatus.COMPLETED
        count.completed_at = datetime.now(timezone.utc)
        count.completed_by_id = current_user.id
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to complete stock count %s", count_id)
        raise HTTPException(status_code=500, detail="Internal server error") from None

    return _load(db, count_id)


@router.post("/{count_id}/cancel", response_model=StockCountDetailResponse)
def cancel_stock_count(
    count_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    count = _load(db, count_id, lock=True)
    _ensure_open(count)

    count.status = StockCountStatus.CANCELLED
    count.completed_at = datetime.now(timezone.utc)
    count.completed_by_id = current_user.id
    db.commit()
    return _load(db, count_id)
