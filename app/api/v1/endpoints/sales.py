import logging
from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, get_current_user, require_role
from app.db.models.product import Product
from app.db.models.sale import Sale, SaleStatus, StockOutReason
from app.db.models.sale_item import SaleItem
from app.db.models.stock_movement import MovementReason
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.sale import Reason, SaleCreate, SaleDetailResponse, SaleResponse
from app.services.stock import change_stock, get_warehouse

logger = logging.getLogger(__name__)

# Stock outs are stored in the sales table: a sale is one kind of stock out,
# next to consumption, waste, returns to the supplier and so on.
router = APIRouter(prefix="/sales", tags=["stock outs"])


def _movement_reason(reason: str) -> str:
    return MovementReason.SALE if reason == StockOutReason.SALE else reason


def _load_sale(db: Session, sale_id: int) -> Sale:
    sale = (
        db.query(Sale)
        .options(joinedload(Sale.items), joinedload(Sale.user), joinedload(Sale.warehouse))
        .filter(Sale.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Stock out not found")
    return sale


@router.post("/", response_model=SaleDetailResponse, status_code=201)
def create_sale(
    data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Merge duplicate lines so the stock check sees the real total per product.
    quantities: "OrderedDict[int, Decimal]" = OrderedDict()
    for item in data.items:
        quantities[item.product_id] = quantities.get(item.product_id, Decimal("0")) + item.quantity

    try:
        warehouse = get_warehouse(db, data.warehouse_id)

        # Lock rows in a stable order (by id) to avoid deadlocks between
        # concurrent requests, and so two users can't take the same last unit.
        products = {
            product.id: product
            for product in db.query(Product)
            .filter(Product.id.in_(list(quantities)))
            .order_by(Product.id)
            .with_for_update()
            .all()
        }

        total_price = Decimal("0.00")
        lines = []

        for product_id, quantity in quantities.items():
            product = products.get(product_id)

            if not product or not product.is_active:
                raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

            # Products without a price are tracked by quantity only.
            unit_price = Decimal(product.price) if product.price is not None else Decimal("0.00")
            line_total = (unit_price * quantity).quantize(Decimal("0.01"))
            total_price += line_total
            lines.append((product, quantity, unit_price, line_total))

        sale = Sale(
            reason=data.reason,
            note=data.note,
            warehouse_id=warehouse.id,
            total_price=total_price,
            status=SaleStatus.COMPLETED,
            user_id=current_user.id,
        )
        db.add(sale)
        db.flush()

        for product, quantity, unit_price, line_total in lines:
            db.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_barcode=product.barcode,
                    unit=product.unit,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_total,
                )
            )
            # Raises when the warehouse doesn't have enough, or the quantity doesn't fit the unit.
            change_stock(
                db,
                product,
                warehouse,
                -quantity,
                _movement_reason(data.reason),
                user_id=current_user.id,
                sale_id=sale.id,
                note=data.note,
            )

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to create stock out")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    return _load_sale(db, sale.id)


@router.get("/", response_model=List[SaleResponse])
def get_sales(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = Query(default=None, pattern="^(completed|cancelled)$"),
    reason: Optional[Reason] = None,
    warehouse_id: Optional[int] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Sale).options(joinedload(Sale.user), joinedload(Sale.warehouse))

    if date_from:
        query = query.filter(Sale.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        next_day = datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc)
        query = query.filter(Sale.created_at < next_day)
    if status:
        query = query.filter(Sale.status == status)
    if reason:
        query = query.filter(Sale.reason == reason)
    if warehouse_id is not None:
        query = query.filter(Sale.warehouse_id == warehouse_id)

    return query.order_by(Sale.id.desc()).offset(skip).limit(limit).all()


@router.get("/{sale_id}", response_model=SaleDetailResponse)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _load_sale(db, sale_id)


@router.post("/{sale_id}/cancel", response_model=SaleDetailResponse)
def cancel_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    try:
        sale = db.query(Sale).filter(Sale.id == sale_id).with_for_update().first()
        if not sale:
            raise HTTPException(status_code=404, detail="Stock out not found")

        if sale.status == SaleStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Stock out is already cancelled")

        product_ids = sorted({item.product_id for item in sale.items})
        products = {
            product.id: product
            for product in db.query(Product)
            .filter(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
            .all()
        }

        # Stock goes back to the same warehouse, even if the product was archived meanwhile.
        for item in sale.items:
            change_stock(
                db,
                products[item.product_id],
                sale.warehouse,
                item.quantity,
                MovementReason.SALE_CANCELLED,
                user_id=current_user.id,
                sale_id=sale.id,
            )

        sale.status = SaleStatus.CANCELLED
        sale.cancelled_at = datetime.now(timezone.utc)
        sale.cancelled_by_id = current_user.id
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to cancel stock out %s", sale_id)
        raise HTTPException(status_code=500, detail="Internal server error") from None

    return _load_sale(db, sale_id)
