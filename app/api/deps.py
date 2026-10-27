import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db

security = HTTPBearer(auto_error=False)

ADMIN = "admin"
CASHIER = "cashier"


def _unauthorized(detail: str = "Invalid token") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _unauthorized() from None

    subject = payload.get("sub")
    if subject is None or not str(subject).isdigit():
        raise _unauthorized()

    user = db.query(User).filter(User.id == int(subject)).first()

    if not user:
        raise _unauthorized("User not found")

    if not user.is_active:
        raise _unauthorized("User is inactive")

    return user


def require_role(*role_names: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role is None:
            raise HTTPException(status_code=403, detail="User has no role assigned")

        if current_user.role.name not in role_names:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        return current_user

    return role_checker
