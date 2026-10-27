from sqlalchemy.orm import Session

from app.db.models.role import Role
from app.db.session import SessionLocal

ROLES = [
    {"name": "admin", "description": "Full system access"},
    {"name": "cashier", "description": "Can process sales"},
]


def seed_roles(db: Session) -> None:
    for role_data in ROLES:
        existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()

        if not existing_role:
            db.add(Role(name=role_data["name"], description=role_data["description"]))
            print(f"Role '{role_data['name']}' created.")

    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_roles(session)
