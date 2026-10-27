from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.product import Product
from app.db.models.sale import Sale, SaleStatus, StockOutReason
from app.db.models.user import User
from app.db.models.warehouse import Warehouse
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_products = db.query(Product).filter(Product.is_active.is_(True))

    total_products = active_products.count()
    low_stock = active_products.filter(Product.low_stock_condition()).count()

    # Value of what is on the shelves, for products that have a price.
    stock_value = (
        db.query(func.coalesce(func.sum(Product.stock_quantity * Product.price), 0))
        .filter(Product.is_active.is_(True), Product.price.isnot(None))
        .scalar()
    )

    completed_sales = db.query(Sale).filter(
        Sale.status == SaleStatus.COMPLETED,
        Sale.reason == StockOutReason.SALE,
    )
    total_sales = completed_sales.count()
    total_revenue = (
        db.query(func.coalesce(func.sum(Sale.total_price), 0))
        .filter(Sale.status == SaleStatus.COMPLETED, Sale.reason == StockOutReason.SALE)
        .scalar()
    )

    warehouse_count = db.query(Warehouse).filter(Warehouse.is_active.is_(True)).count()

    return DashboardSummary(
        total_products=total_products,
        low_stock=low_stock,
        low_stock_threshold=settings.low_stock_threshold,
        total_sales=total_sales,
        revenue=float(total_revenue),
        stock_value=float(stock_value),
        warehouse_count=warehouse_count,
    )
