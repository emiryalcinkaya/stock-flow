from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ADMIN, require_role
from app.core.security import hash_password
from app.db.models.role import Role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.people import PasswordReset, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        role=user.role.name if user.role else "",
        is_active=user.is_active,
    )


def _role(db: Session, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{name}' does not exist")
    return role


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .join(Role)
        .filter(Role.name == ADMIN, User.is_active.is_(True))
        .count()
    )


def _ensure_unique(db: Session, username: str = None, email: str = None, exclude_id: int = None) -> None:
    conditions = []
    if username:
        conditions.append(func.lower(User.username) == username.lower())
    if email:
        conditions.append(func.lower(User.email) == email.lower())
    if not conditions:
        return

    query = db.query(User).filter(or_(*conditions))
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    clash = query.first()
    if clash:
        same_username = username and clash.username.lower() == username.lower()
        raise HTTPException(
            status_code=400,
            detail="Username already exists" if same_username else "Email already exists",
        )


@router.get("", response_model=List[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    users = db.query(User).options(joinedload(User.role)).order_by(User.id).all()
    return [to_response(user) for user in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    _ensure_unique(db, username=data.username, email=data.email)

    user = User(
        full_name=data.full_name,
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role_id=_role(db, data.role).id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email is not None and data.email != user.email:
        _ensure_unique(db, email=data.email, exclude_id=user.id)
        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    losing_admin = user.role.name == ADMIN and (
        (data.role is not None and data.role != ADMIN) or data.is_active is False
    )
    if losing_admin:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="You can't remove your own admin access")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="At least one active admin is required")

    if data.role is not None:
        user.role_id = _role(db, data.role).id
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)
    return to_response(user)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated"}
