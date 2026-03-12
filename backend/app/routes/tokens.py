"""Token/billing routes — view balance, purchase packages, manage subscriptions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.models.user import FamilyMember
from app.models.token import TokenPackage, TokenTransaction
from app.routes.auth import get_current_member
from app.services.token_service import get_family_balance, add_tokens
from app.models.token import TransactionType

router = APIRouter(prefix="/tokens", tags=["tokens"])


class PackageResponse(BaseModel):
    id: int
    name: str
    description: str
    minutes: int
    price_cents: int
    currency: str
    is_subscription: bool
    subscription_interval: str | None

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
    """List available token packages."""
    packages = db.query(TokenPackage).filter(TokenPackage.is_active == True).all()

    # Seed default packages if empty
    if not packages:
        default_packages = [
            TokenPackage(name="体验版", description="新用户专享，免费体验", minutes=60, price_cents=0, currency="CNY"),
            TokenPackage(name="月卡基础版", description="适合偶尔通话", minutes=300, price_cents=3900, currency="CNY", is_subscription=True, subscription_interval="month"),
            TokenPackage(name="月卡标准版", description="适合每日通话", minutes=800, price_cents=8900, currency="CNY", is_subscription=True, subscription_interval="month"),
            TokenPackage(name="年卡家庭版", description="不限时长，最划算", minutes=99999, price_cents=79900, currency="CNY", is_subscription=True, subscription_interval="year"),
        ]
        for p in default_packages:
            db.add(p)
        db.commit()
        packages = default_packages

    return packages


@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """Get transaction history for the current member."""
    transactions = (
        db.query(TokenTransaction)
        .filter(TokenTransaction.member_id == current_member.id)
        .order_by(TokenTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return transactions


@router.post("/mock-recharge")
def mock_recharge(
    minutes: int,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """
    DEV ONLY: Add tokens without payment (for testing).
    Remove this endpoint in production.
    """
    transaction = add_tokens(
        db=db,
        member_id=current_member.id,
        family_group_id=current_member.family_group_id,
        seconds=minutes * 60,
        transaction_type=TransactionType.admin_grant,
        description=f"测试充值 {minutes} 分钟",
    )
    return {
        "ok": True,
        "added_minutes": minutes,
        "new_balance_minutes": transaction.balance_after / 60,
    }
