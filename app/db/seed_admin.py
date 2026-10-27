import os

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.role import Role
from app.db.models.user import User
from app.db.session import SessionLocal


def seed_user(db: Session, *, role_name: str, username: str, password: str, full_name: str, email: str) -> None:
    role = db.query(Role).filter(Role.name == role_name).first()

    if not role:
        print(f"Role '{role_name}' not found. Run seed_roles first.")
        return

    if db.query(User).filter(User.username == username).first():
        print(f"User '{username}' already exists.")
        return

    db.add(
        User(
            full_name=full_name,
            email=email,
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
            role_id=role.id,
        )
    )
    db.commit()
    print(f"User '{username}' created.")


def seed_admin(db: Session) -> None:
    seed_user(
        db,
        role_name="admin",
        username=os.getenv("SEED_ADMIN_USERNAME", "admin"),
        password=os.getenv("SEED_ADMIN_PASSWORD", "admin123"),
        full_name="System Admin",
        email="admin@stockflow.local",
    )


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_admin(session)
