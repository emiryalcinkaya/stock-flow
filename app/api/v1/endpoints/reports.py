from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.product import Product
from app.db.models.sale import Sale, SaleStatus, StockOutReason
from app.db.models.sale_item import SaleItem
from app.db.models.stock_movement import MovementReason, StockMovement
from app.db.models.supplier import Supplier
from app.db.models.user import User
from app.db.models.warehouse import StockLevel, Warehouse
from app.db.session import get_db
from app.services.csv_io import csv_response, format_number

router = APIRouter(prefix="/reports", tags=["reports"])

PURCHASE_REASONS = (MovementReason.INITIAL, MovementReason.RESTOCK)


def _period(date_from: Optional[date], date_to: Optional[date]):
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        # Start of the month, five months back: six full months on screen.
        month = today.month - 5
        year = today.year + (month - 1) // 12
        date_from = date(year, (month - 1) % 12 + 1, 1)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    start = datetime.combine(date_from, time.min, timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc)
    return date_from, date_to, start, end


def _num(value) -> float:
    return float(value or 0)


@router.get("/overview")
def report_overview(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    slow_days: int = Query(default=90, ge=7, le=730),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    date_from, date_to, start, end = _period(date_from, date_to)

    in_period_sales = and_(
        Sale.status == SaleStatus.COMPLETED, Sale.created_at >= start, Sale.created_at < end
    )
    purchase = and_(
        StockMovement.reason.in_(PURCHASE_REASONS),
        StockMovement.created_at >= start,
        StockMovement.created_at < end,
    )
    purchase_value = func.coalesce(func.sum(StockMovement.change * StockMovement.unit_cost), 0)

    # ----- Monthly totals --------------------------------------------------
    month = func.to_char(func.date_trunc("month", Sale.created_at), "YYYY-MM")
    sales_by_month = (
        db.query(
            month.label("month"),
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_price), 0),
            func.coalesce(func.sum(case((Sale.reason == StockOutReason.SALE, Sale.total_price), else_=0)), 0),
        )
        .filter(in_period_sales)
        .group_by("month")
        .all()
    )
    move_month = func.to_char(func.date_trunc("month", StockMovement.created_at), "YYYY-MM")
    purchases_by_month = (
        db.query(move_month.label("month"), func.count(StockMovement.id), purchase_value)
        .filter(purchase, StockMovement.reason == MovementReason.RESTOCK)
        .group_by("month")
        .all()
    )

    months = {}
    cursor = date(date_from.year, date_from.month, 1)
    while cursor <= date_to:
        key = cursor.strftime("%Y-%m")
        months[key] = {
            "month": key, "stock_outs": 0, "stock_out_value": 0.0, "sales_revenue": 0.0,
            "stock_ins": 0, "stock_in_value": 0.0,
        }
        cursor = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
    for key, count, value, revenue in sales_by_month:
        if key in months:
            months[key].update(stock_outs=count, stock_out_value=_num(value), sales_revenue=_num(revenue))
    for key, count, value in purchases_by_month:
        if key in months:
            months[key].update(stock_ins=count, stock_in_value=_num(value))

    # ----- Gross profit (sales of products with a known cost) --------------
    profit_row = (
        db.query(
            func.coalesce(func.sum(SaleItem.total_price), 0),
            func.coalesce(func.sum(SaleItem.quantity * Product.cost_price), 0),
            func.count(SaleItem.id),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Product, Product.id == SaleItem.product_id)
        .filter(in_period_sales, Sale.reason == StockOutReason.SALE, Product.cost_price.isnot(None))
        .one()
    )
    all_sale_lines = (
        db.query(func.count(SaleItem.id))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(in_period_sales, Sale.reason == StockOutReason.SALE)
        .scalar()
    )

    # ----- Most moved products ---------------------------------------------
    top_products = (
        db.query(
            SaleItem.product_id,
            func.max(SaleItem.product_name),
            func.max(SaleItem.unit),
            func.sum(SaleItem.quantity),
            func.sum(SaleItem.total_price),
            func.count(func.distinct(SaleItem.sale_id)),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(in_period_sales)
        .group_by(SaleItem.product_id)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(10)
        .all()
    )

    # ----- Products that haven't left stock for a while --------------------
    slow_since = datetime.now(timezone.utc) - timedelta(days=slow_days)
    last_out = (
        db.query(StockMovement.product_id, func.max(StockMovement.created_at).label("last_out"))
        .filter(StockMovement.change < 0, StockMovement.reason.notin_(MovementReason.TRANSFERS))
        .group_by(StockMovement.product_id)
        .subquery()
    )
    slow_movers = (
        db.query(Product, last_out.c.last_out)
        .outerjoin(last_out, last_out.c.product_id == Product.id)
        .filter(
            Product.is_active.is_(True),
            Product.stock_quantity > 0,
            (last_out.c.last_out.is_(None)) | (last_out.c.last_out < slow_since),
        )
        .order_by(last_out.c.last_out.asc().nulls_first(), Product.name)
        .limit(20)
        .all()
    )

    # ----- Stock value per warehouse ----------------------------------------
    warehouses = (
        db.query(
            Warehouse.id,
            Warehouse.name,
            func.count(case((StockLevel.quantity > 0, 1))),
            func.coalesce(func.sum(StockLevel.quantity * Product.price), 0),
            func.coalesce(func.sum(StockLevel.quantity * Product.cost_price), 0),
        )
        .outerjoin(StockLevel, StockLevel.warehouse_id == Warehouse.id)
        .outerjoin(Product, and_(Product.id == StockLevel.product_id, Product.is_active.is_(True)))
        .filter(Warehouse.is_active.is_(True))
        .group_by(Warehouse.id, Warehouse.name)
        .order_by(Warehouse.is_default.desc(), Warehouse.name)
        .all()
    )

    # ----- Purchases per supplier -------------------------------------------
    suppliers = (
        db.query(Supplier.id, Supplier.name, func.count(StockMovement.id), purchase_value)
        .join(StockMovement, StockMovement.supplier_id == Supplier.id)
        .filter(purchase)
        .group_by(Supplier.id, Supplier.name)
        .order_by(purchase_value.desc())
        .all()
    )

    revenue_with_cost, cost_of_sales, lines_with_cost = profit_row
    return {
        "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        "totals": {
            "stock_ins": sum(m["stock_ins"] for m in months.values()),
            "stock_in_value": sum(m["stock_in_value"] for m in months.values()),
            "stock_outs": sum(m["stock_outs"] for m in months.values()),
            "stock_out_value": sum(m["stock_out_value"] for m in months.values()),
            "sales_revenue": sum(m["sales_revenue"] for m in months.values()),
            "gross_profit": _num(revenue_with_cost) - _num(cost_of_sales),
            # Share of sold lines whose product has a cost price, so the profit is complete.
            "profit_coverage": (lines_with_cost / all_sale_lines) if all_sale_lines else 1.0,
        },
        "monthly": list(months.values()),
        "top_products": [
            {"product_id": pid, "name": name, "unit": unit, "quantity": _num(qty), "value": _num(value),
             "stock_outs": docs}
            for pid, name, unit, qty, value, docs in top_products
        ],
        "slow_movers": [
            {
                "product_id": p.id, "name": p.name, "unit": p.unit,
                "stock_quantity": _num(p.stock_quantity),
                "value": _num(p.stock_quantity * p.price) if p.price is not None else None,
                "last_out_at": last.isoformat() if last else None,
            }
            for p, last in slow_movers
        ],
        "slow_days": slow_days,
        "warehouses": [
            {"warehouse_id": wid, "name": name, "products": count, "value": _num(value),
             "cost_value": _num(cost_value)}
            for wid, name, count, value, cost_value in warehouses
        ],
        "suppliers": [
            {"supplier_id": sid, "name": name, "deliveries": count, "value": _num(value)}
            for sid, name, count, value in suppliers
        ],
    }


@router.get("/movements.csv")
def export_movements(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    delimiter: Literal["comma", "semicolon"] = "comma",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every stock movement in the period, oldest first."""
    _, _, start, end = _period(date_from, date_to)
    decimal_comma = delimiter == "semicolon"

    movements = (
        db.query(StockMovement)
        .filter(StockMovement.created_at >= start, StockMovement.created_at < end)
        .order_by(StockMovement.id)
        .all()
    )
    header = [
        "date", "barcode", "product", "unit", "warehouse", "type", "change", "total_after",
        "unit_cost", "supplier", "document_no", "user", "note",
    ]
    rows = (
        [
            m.created_at.isoformat(timespec="seconds"),
            m.product.barcode, m.product.name, m.product.unit, m.warehouse_name, m.reason,
            format_number(m.change, decimal_comma), format_number(m.quantity_after, decimal_comma),
            format_number(m.unit_cost, decimal_comma), m.supplier_name, m.document_no, m.username, m.note,
        ]
        for m in movements
    )
    return csv_response("stock-movements.csv", header, rows, ";" if decimal_comma else ",")


@router.get("/stock-outs.csv")
def export_stock_outs(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    delimiter: Literal["comma", "semicolon"] = "comma",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One row per stock-out line in the period."""
    _, _, start, end = _period(date_from, date_to)
    decimal_comma = delimiter == "semicolon"

    items = (
        db.query(SaleItem, Sale)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.created_at >= start, Sale.created_at < end)
        .order_by(Sale.id, SaleItem.id)
        .all()
    )
    header = [
        "stock_out_id", "date", "reason", "status", "warehouse", "user", "barcode", "product", "unit",
        "quantity", "unit_price", "line_total", "note",
    ]
    rows = (
        [
            sale.id, sale.created_at.isoformat(timespec="seconds"), sale.reason, sale.status,
            sale.warehouse_name, sale.cashier_name, item.product_barcode, item.product_name, item.unit,
            format_number(item.quantity, decimal_comma), format_number(item.unit_price, decimal_comma),
            format_number(item.total_price, decimal_comma), sale.note,
        ]
        for item, sale in items
    )
    return csv_response("stock-outs.csv", header, rows, ";" if decimal_comma else ",")
