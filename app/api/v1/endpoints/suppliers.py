from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_user, require_role
from app.db.models.supplier import Supplier
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.people import SupplierCreate, SupplierResponse, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Supplier already exists") from None


@router.get("", response_model=List[SupplierResponse])
def get_suppliers(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Supplier)
    if not include_inactive:
        query = query.filter(Supplier.is_active.is_(True))
    return query.order_by(Supplier.name).all()


@router.post("", response_model=SupplierResponse, status_code=201)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    supplier = Supplier(**data.model_dump(), is_active=True)
    db.add(supplier)
    _commit(db)
    db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    for field in data.model_fields_set:
        value = getattr(data, field)
        if field in ("name", "is_active") and value is None:
            continue
        setattr(supplier, field, value)

    _commit(db)
    db.refresh(supplier)
    return supplier
