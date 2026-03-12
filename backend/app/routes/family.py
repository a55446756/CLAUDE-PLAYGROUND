"""Family management routes — manage elderly profile, family members, and updates."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.user import FamilyMember, FamilyGroup, ElderlyProfile, MemberRole
from app.models.family_update import FamilyUpdate
from app.routes.auth import get_current_member

router = APIRouter(prefix="/family", tags=["family"])


# --- Schemas ---

class ElderlyProfileUpdate(BaseModel):
    name: Optional[str] = None
    ai_name: Optional[str] = None
    elder_calls_ai: Optional[str] = None
    personality_notes: Optional[str] = None
    health_notes: Optional[str] = None
    interests: Optional[str] = None
    language: Optional[str] = None      # BCP-47 language tag
    timezone: Optional[str] = None      # IANA timezone
    country_code: Optional[str] = None  # ISO 3166-1 alpha-2


class ElderlyProfileResponse(BaseModel):
    id: int
    name: str
    phone: str
    ai_name: str
    elder_calls_ai: str
    personality_notes: str
    health_notes: str
    interests: str
    language: str
    timezone: str
    country_code: str

    class Config:
        from_attributes = True


class FamilyUpdateCreate(BaseModel):
    content: str
    category: str = "general"
    share_with_elderly: bool = True
    expires_days: Optional[int] = 30  # Auto-expire after N days


class FamilyUpdateResponse(BaseModel):
    id: int
    author_name: str
    relation_to_elderly: str
    content: str
    category: str
    share_with_elderly: bool
    has_been_shared: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    name: str
    phone: str
    relation_to_elderly: str = "family member"


# --- Routes ---

@router.get("/elderly", response_model=ElderlyProfileResponse)
def get_elderly_profile(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    elderly = db.query(ElderlyProfile).filter(
        ElderlyProfile.family_group_id == current_member.family_group_id
    ).first()
    if not elderly:
        raise HTTPException(status_code=404, detail="Elderly profile not found")
    return elderly


@router.put("/elderly", response_model=ElderlyProfileResponse)
def update_elderly_profile(
    data: ElderlyProfileUpdate,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    elderly = db.query(ElderlyProfile).filter(
        ElderlyProfile.family_group_id == current_member.family_group_id
    ).first()
    if not elderly:
        raise HTTPException(status_code=404, detail="Elderly profile not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(elderly, field, value)

    db.commit()
    db.refresh(elderly)
    return elderly


@router.get("/members")
def get_family_members(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    members = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == current_member.family_group_id
    ).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "phone": m.phone,
            "role": m.role,
            "relation_to_elderly": m.relation_to_elderly,
            "token_balance_minutes": m.token_balance_seconds / 60,
            "is_active": m.is_active,
        }
        for m in members
    ]


@router.post("/updates", response_model=FamilyUpdateResponse)
def create_family_update(
    data: FamilyUpdateCreate,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """Add a family life update for the AI to share with the elderly."""
    expires_at = None
    if data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_days)

    update = FamilyUpdate(
        family_group_id=current_member.family_group_id,
        author_id=current_member.id,
        content=data.content,
        category=data.category,
        share_with_elderly=data.share_with_elderly,
        expires_at=expires_at,
    )
    db.add(update)
    db.commit()
    db.refresh(update)

    return FamilyUpdateResponse(
        id=update.id,
        author_name=current_member.name,
        relation_to_elderly=current_member.relation_to_elderly,
        content=update.content,
        category=update.category,
        share_with_elderly=update.share_with_elderly,
        has_been_shared=update.has_been_shared,
        created_at=update.created_at,
    )


@router.get("/updates", response_model=List[FamilyUpdateResponse])
def get_family_updates(
    include_shared: bool = False,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """Get all family updates for this group."""
    query = db.query(FamilyUpdate).filter(
        FamilyUpdate.family_group_id == current_member.family_group_id
    )
    if not include_shared:
        query = query.filter(FamilyUpdate.has_been_shared == False)

    updates = query.order_by(FamilyUpdate.created_at.desc()).all()

    result = []
    for u in updates:
        author = db.query(FamilyMember).filter(FamilyMember.id == u.author_id).first()
        result.append(FamilyUpdateResponse(
            id=u.id,
            author_name=author.name if author else "Unknown",
            relation_to_elderly=author.relation_to_elderly if author else "family member",
            content=u.content,
            category=u.category,
            share_with_elderly=u.share_with_elderly,
            has_been_shared=u.has_been_shared,
            created_at=u.created_at,
        ))
    return result


@router.delete("/updates/{update_id}")
def delete_family_update(
    update_id: int,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    update = db.query(FamilyUpdate).filter(
        FamilyUpdate.id == update_id,
        FamilyUpdate.family_group_id == current_member.family_group_id,
    ).first()
    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    db.delete(update)
    db.commit()
    return {"ok": True}
