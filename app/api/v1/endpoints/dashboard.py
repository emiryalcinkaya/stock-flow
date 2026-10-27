from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.product import Product
from app.db.models.sale import Sale, SaleStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    threshold = settings.low_stock_threshold

    total_products = db.query(Product).filter(Product.is_active.is_(True)).count()

    low_stock = db.query(Product).filter(
        Product.is_active.is_(True),
        Product.stock_quantity < threshold,
    ).count()

    completed_sales = db.query(Sale).filter(Sale.status == SaleStatus.COMPLETED)
    total_sales = completed_sales.count()
    total_revenue = (
        db.query(func.coalesce(func.sum(Sale.total_price), 0))
        .filter(Sale.status == SaleStatus.COMPLETED)
        .scalar()
    )

    return DashboardSummary(
        total_products=total_products,
        low_stock=low_stock,
        low_stock_threshold=threshold,
        total_sales=total_sales,
        revenue=float(total_revenue),
    )
