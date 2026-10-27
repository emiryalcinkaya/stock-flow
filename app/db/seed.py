"""Seed roles and the demo users.

Usage: python -m app.db.seed
Passwords can be overridden with SEED_ADMIN_PASSWORD / SEED_CASHIER_PASSWORD.
"""

from app.db.seed_admin import seed_admin
from app.db.seed_cashier import seed_cashier
from app.db.seed_roles import seed_roles
from app.db.session import SessionLocal


def seed_all() -> None:
    with SessionLocal() as db:
        seed_roles(db)
        seed_admin(db)
        seed_cashier(db)


if __name__ == "__main__":
    seed_all()
