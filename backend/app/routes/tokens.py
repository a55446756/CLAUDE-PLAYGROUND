"""Token/billing routes — view balance, purchase packages, manage subscriptions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.models.user import FamilyMember
from app.models.token import TokenPackage, TokenTransaction
from app.routes.auth import get_current_member
from app.services.token_service import get_family_balance, add_tokens
from app.models.token import TransactionType

router = APIRouter(prefix="/tokens", tags=["tokens"])

# Default packages seeded on first request (currency = server default, overrideable)
_DEFAULT_PACKAGES = [
    dict(name="Free Trial",      description="New user gift, no credit card required",
         minutes=60,    price_cents=0,     is_subscription=False),
    dict(name="Starter",         description="Great for occasional calls",
         minutes=300,   price_cents=599,   is_subscription=True, subscription_interval="month"),
    dict(name="Family",          description="Perfect for daily check-ins",
         minutes=800,   price_cents=1299,  is_subscription=True, subscription_interval="month"),
    dict(name="Family Annual",   description="Best value — unlimited peace of mind",
         minutes=99999, price_cents=9900,  is_subscription=True, subscription_interval="year"),
]


class PackageResponse(BaseModel):
    id: int
    name: str
    description: str
    minutes: int
    price_cents: int
    currency: str
    is_subscription: bool
    subscription_interval: Optional[str]

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    transaction_type: str
    seconds_delta: int
    balance_after: int
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    balance_seconds: int
    balance_minutes: float
    balance_hours: float


@router.get("/balance", response_model=BalanceResponse)
def get_balance(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    balance = get_family_balance(db, current_member.family_group_id)
    return BalanceResponse(
        balance_seconds=balance,
        balance_minutes=round(balance / 60, 1),
        balance_hours=round(balance / 3600, 2),
    )


@router.get("/packages", response_model=List[PackageResponse])
def list_packages(db: Session = Depends(get_db)):
    """List available token packages in the server's default currency."""
    packages = db.query(TokenPackage).filter(TokenPackage.is_active == True).all()

    if not packages:
        currency = settings.DEFAULT_CURRENCY
        for p in _DEFAULT_PACKAGES:
            pkg = TokenPackage(
                currency=currency,
                is_subscription=False,
                subscription_interval=None,
                **p,
            )
            db.add(pkg)
        db.commit()
        packages = db.query(TokenPackage).filter(TokenPackage.is_active == True).all()

    return packages


@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    return (
        db.query(TokenTransaction)
        .filter(TokenTransaction.member_id == current_member.id)
        .order_by(TokenTransaction.created_at.desc())
        .limit(50)
        .all()
    )


@router.post("/mock-recharge")
def mock_recharge(
    minutes: int,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """DEV ONLY: Add tokens without payment (for testing)."""
    transaction = add_tokens(
        db=db,
        member_id=current_member.id,
        family_group_id=current_member.family_group_id,
        seconds=minutes * 60,
        transaction_type=TransactionType.admin_grant,
        description=f"Dev top-up: {minutes} minutes",
    )
    return {
        "ok": True,
        "added_minutes": minutes,
        "new_balance_minutes": transaction.balance_after / 60,
    }
