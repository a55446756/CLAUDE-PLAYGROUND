"""
Token billing service — tracks and deducts call time.
"""
from sqlalchemy.orm import Session
from app.models.user import FamilyMember
from app.models.token import TokenTransaction, TransactionType
from app.core.config import settings


LOW_BALANCE_THRESHOLD_SECONDS = 10 * 60  # 10 minutes warning


def get_family_balance(db: Session, family_group_id: int) -> int:
    """Get total balance in seconds for a family group (sum of all members)."""
    from sqlalchemy import func
    result = db.query(func.sum(FamilyMember.token_balance_seconds)).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.is_active == True,
    ).scalar()
    return result or 0


def get_admin_member(db: Session, family_group_id: int) -> FamilyMember:
    """Get the admin member of a family group."""
    return db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.role == "admin",
    ).first()


def add_tokens(
    db: Session,
    member_id: int,
    family_group_id: int,
    seconds: int,
    transaction_type: TransactionType,
    description: str,
    reference_id: str = None,
) -> TokenTransaction:
    """Add tokens to a member's balance."""
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        raise ValueError(f"Member {member_id} not found")

    member.token_balance_seconds += seconds
    balance_after = member.token_balance_seconds

    transaction = TokenTransaction(
        member_id=member_id,
        family_group_id=family_group_id,
        transaction_type=transaction_type,
        seconds_delta=seconds,
        balance_after=balance_after,
        description=description,
        reference_id=reference_id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def deduct_tokens(
    db: Session,
    family_group_id: int,
    seconds: int,
    session_id: int,
) -> tuple[bool, bool]:
    """
    Deduct call time from the family group's admin balance.
    Returns (success, is_low_balance).
    """
    admin = get_admin_member(db, family_group_id)
    if not admin:
        return False, False

    if admin.token_balance_seconds < seconds:
        return False, False

    admin.token_balance_seconds -= seconds
    balance_after = admin.token_balance_seconds

    transaction = TokenTransaction(
        member_id=admin.id,
        family_group_id=family_group_id,
        transaction_type=TransactionType.usage,
        seconds_delta=-seconds,
        balance_after=balance_after,
        description=f"通话消耗 {seconds//60}分{seconds%60}秒",
        reference_id=str(session_id),
    )
    db.add(transaction)
    db.commit()

    is_low = balance_after < LOW_BALANCE_THRESHOLD_SECONDS
    return True, is_low


def grant_free_trial(db: Session, member_id: int, family_group_id: int) -> None:
    """Grant free trial tokens to a new family group admin."""
    add_tokens(
        db=db,
        member_id=member_id,
        family_group_id=family_group_id,
        seconds=settings.FREE_TRIAL_MINUTES * 60,
        transaction_type=TransactionType.free_trial,
        description=f"新用户赠送{settings.FREE_TRIAL_MINUTES}分钟体验时长",
    )
