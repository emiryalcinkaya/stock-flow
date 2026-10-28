from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_user, require_role
from app.db.models.company import CompanyProfile
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.company import CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/company", tags=["company"])

PROFILE_ID = 1


@router.get("", response_model=CompanyResponse)
def get_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.get(CompanyProfile, PROFILE_ID) or CompanyResponse()


@router.patch("", response_model=CompanyResponse)
def update_company(
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN)),
):
    profile = db.get(CompanyProfile, PROFILE_ID, with_for_update=True)
    if profile is None:
        profile = CompanyProfile(id=PROFILE_ID)
        db.add(profile)

    # Only the fields that were sent are changed; null clears a field.
    for field in data.model_fields_set:
        setattr(profile, field, getattr(data, field))

    db.commit()
    db.refresh(profile)
    return profile
