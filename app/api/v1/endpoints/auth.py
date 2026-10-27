from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import LoginRateLimiter
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = LoginRateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_lockout_seconds,
)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}:{data.username.lower()}"

    retry_after = login_limiter.retry_after(limiter_key)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.username == data.username).first()

    # Always run a bcrypt check so response time does not reveal valid usernames.
    password_ok = verify_password(
        data.password,
        user.hashed_password if user else DUMMY_PASSWORD_HASH,
    )

    if not user or not password_ok:
        login_limiter.register_failure(limiter_key)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    login_limiter.reset(limiter_key)

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
    }


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role.name if current_user.role else "",
    )
