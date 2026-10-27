import logging
from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, get_current_user, require_role
from app.db.models.product import Product
from app.db.models.sale import Sale, SaleStatus
from app.db.models.sale_item import SaleItem
from app.db.models.stock_movement import MovementReason
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.sale import SaleCreate, SaleDetailResponse, SaleResponse
from app.services.stock import change_stock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])


def _load_sale(db: Session, sale_id: int) -> Sale:
    sale = (
        db.query(Sale)
        .options(joinedload(Sale.items), joinedload(Sale.user))
        .filter(Sale.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.post("/", response_model=SaleDetailResponse, status_code=201)
def create_sale(
    data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Merge duplicate lines so the stock check sees the real total per product.
    quantities: "OrderedDict[int, int]" = OrderedDict()
    for item in data.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    try:
        # Lock rows in a stable order (by id) to avoid deadlocks between
        # concurrent sales, and so two cashiers can't sell the same last unit.
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

            if product.stock_quantity < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for product {product.name}",
                )

            unit_price = Decimal(product.price)
            line_total = unit_price * quantity
            total_price += line_total
            lines.append((product, quantity, unit_price, line_total))

        sale = Sale(total_price=total_price, status=SaleStatus.COMPLETED, user_id=current_user.id)
        db.add(sale)
        db.flush()

        for product, quantity, unit_price, line_total in lines:
            db.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_barcode=product.barcode,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_total,
                )
            )
            change_stock(
                db,
                product,
                -quantity,
                MovementReason.SALE,
                user_id=current_user.id,
                sale_id=sale.id,
            )

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to create sale")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    return _load_sale(db, sale.id)


@router.get("/", response_model=List[SaleResponse])
def get_sales(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = Query(default=None, pattern="^(completed|cancelled)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Sale).options(joinedload(Sale.user))

    if date_from:
        query = query.filter(Sale.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        next_day = datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc)
        query = query.filter(Sale.created_at < next_day)
    if status:
        query = query.filter(Sale.status == status)

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
            raise HTTPException(status_code=404, detail="Sale not found")

        if sale.status == SaleStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Sale is already cancelled")

        product_ids = sorted({item.product_id for item in sale.items})
        products = {
            product.id: product
            for product in db.query(Product)
            .filter(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
            .all()
        }

        # Stock goes back even if the product was archived in the meantime.
        for item in sale.items:
            change_stock(
                db,
                products[item.product_id],
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
        logger.exception("Failed to cancel sale %s", sale_id)
        raise HTTPException(status_code=500, detail="Internal server error") from None

    return _load_sale(db, sale_id)
