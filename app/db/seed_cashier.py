import os

from sqlalchemy.orm import Session

from app.db.seed_admin import seed_user
from app.db.session import SessionLocal


def seed_cashier(db: Session) -> None:
    seed_user(
        db,
        role_name="cashier",
        username=os.getenv("SEED_CASHIER_USERNAME", "cashier"),
        password=os.getenv("SEED_CASHIER_PASSWORD", "cashier123"),
        full_name="Cashier User",
        email="cashier@stockflow.local",
    )


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_cashier(session)
