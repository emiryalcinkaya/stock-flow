from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.sales import router as sales_router
from app.db.session import get_db

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(sales_router)
api_router.include_router(inventory_router)
api_router.include_router(dashboard_router)


@api_router.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "connected"}
