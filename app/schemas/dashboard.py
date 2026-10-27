from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_products: int
    low_stock: int
    low_stock_threshold: int
    total_sales: int
    revenue: float
