"""Seed roles, the default warehouse and the demo users.

Usage: python -m app.db.seed
Passwords can be overridden with SEED_ADMIN_PASSWORD / SEED_CASHIER_PASSWORD.
"""

from sqlalchemy.orm import Session

from app.db.models.warehouse import Warehouse
from app.db.seed_admin import seed_admin
from app.db.seed_cashier import seed_cashier
from app.db.seed_roles import seed_roles
from app.db.session import SessionLocal


def seed_default_warehouse(db: Session) -> None:
    if db.query(Warehouse).filter(Warehouse.is_default.is_(True)).first():
        return

    db.add(Warehouse(name="Main Warehouse", is_default=True, is_active=True))
    db.commit()
    print("Default warehouse created.")


def seed_all() -> None:
    with SessionLocal() as db:
        seed_roles(db)
        seed_default_warehouse(db)
        seed_admin(db)
        seed_cashier(db)


if __name__ == "__main__":
    seed_all()
