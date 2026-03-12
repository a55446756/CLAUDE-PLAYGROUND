from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_token
from app.core.config import settings
from app.models.user import FamilyMember, FamilyGroup, ElderlyProfile, MemberRole
from app.services.token_service import grant_free_trial

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# --- Schemas ---

class RegisterRequest(BaseModel):
    name: str
    phone: str                              # E.164 format recommended: +12125551234
    password: str
    email: Optional[str] = None

    # Elderly person info
    elderly_name: str
    elderly_phone: str                      # E.164 format
    elderly_language: str = "en-US"        # BCP-47: conversation language for the elder
    elderly_timezone: str = "UTC"          # IANA timezone
    elderly_country: str = "US"            # ISO 3166-1 alpha-2

    family_name: str                        # e.g., "Smith Family"
    relation_to_elderly: str = "family member"  # e.g., "son", "daughter"
    ai_name: str = ""                       # What the AI calls itself (defaults to member name)


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    member_id: int
    name: str
    family_group_id: int


class MeResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str]
    role: str
    family_group_id: int
    token_balance_minutes: float
    relation_to_elderly: str
    preferred_language: str

    class Config:
        from_attributes = True


# --- Dependency ---

def get_current_member(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> FamilyMember:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    member_id = payload.get("sub")
    if not member_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    member = db.query(FamilyMember).filter(FamilyMember.id == int(member_id)).first()
    if not member or not member.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return member


# --- Routes ---

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new family member and create the family group + elderly profile."""
    if db.query(FamilyMember).filter(FamilyMember.phone == req.phone).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    if db.query(ElderlyProfile).filter(ElderlyProfile.phone == req.elderly_phone).first():
        raise HTTPException(status_code=400, detail="Elderly person's phone number is already linked to an account")

    # Create family group
    family_group = FamilyGroup(name=req.family_name)
    db.add(family_group)
    db.flush()

    # Create elderly profile
    ai_name = req.ai_name or req.name
    elderly = ElderlyProfile(
        family_group_id=family_group.id,
        name=req.elderly_name,
        phone=req.elderly_phone,
        language=req.elderly_language,
        timezone=req.elderly_timezone,
        country_code=req.elderly_country,
        ai_name=ai_name,
        elder_calls_ai=ai_name,
    )
    db.add(elderly)

    # Create family member (admin)
    member = FamilyMember(
        family_group_id=family_group.id,
        name=req.name,
        phone=req.phone,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        role=MemberRole.admin,
        relation_to_elderly=req.relation_to_elderly,
        preferred_language=req.elderly_language,  # Default portal language to elderly's language
    )
    db.add(member)
    db.flush()

    grant_free_trial(db, member.id, family_group.id)

    db.commit()
    db.refresh(member)

    access_token = create_access_token({"sub": str(member.id)})
    return TokenResponse(
        access_token=access_token,
        member_id=member.id,
        name=member.name,
        family_group_id=family_group.id,
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.phone == req.phone).first()
    if not member or not verify_password(req.password, member.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect phone number or password")

    if not member.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token({"sub": str(member.id)})
    return TokenResponse(
        access_token=access_token,
        member_id=member.id,
        name=member.name,
        family_group_id=member.family_group_id,
    )


@router.get("/me", response_model=MeResponse)
def get_me(current_member: FamilyMember = Depends(get_current_member)):
    return MeResponse(
        id=current_member.id,
        name=current_member.name,
        phone=current_member.phone,
        email=current_member.email,
        role=current_member.role,
        family_group_id=current_member.family_group_id,
        token_balance_minutes=current_member.token_balance_seconds / 60,
        relation_to_elderly=current_member.relation_to_elderly,
        preferred_language=current_member.preferred_language or "en-US",
    )
