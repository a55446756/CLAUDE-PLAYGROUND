from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class TransactionType(str, enum.Enum):
    purchase = "purchase"
    free_trial = "free_trial"
    refund = "refund"
    usage = "usage"
    admin_grant = "admin_grant"


class TokenPackage(Base):
    """Available token packages for purchase"""
    __tablename__ = "token_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)         # e.g., "月卡标准版"
    description = Column(Text, default="")
    minutes = Column(Integer, nullable=False)           # How many minutes
    price_cents = Column(Integer, nullable=False)       # Price in cents (CNY)
    currency = Column(String(10), default="CNY")
    is_subscription = Column(Boolean, default=False)
    subscription_interval = Column(String(20), nullable=True)  # "month" | "year"
    is_active = Column(Boolean, default=True)
    stripe_price_id = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Fix missing import
from sqlalchemy import Boolean


class TokenTransaction(Base):
    """Token balance changes"""
    __tablename__ = "token_transactions"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"), nullable=False)
    family_group_id = Column(Integer, ForeignKey("family_groups.id"), nullable=False)

    transaction_type = Column(Enum(TransactionType), nullable=False)
    seconds_delta = Column(Integer, nullable=False)     # Positive = add, Negative = deduct
    balance_after = Column(Integer, nullable=False)     # Balance in seconds after transaction

    description = Column(String(500), default="")
    reference_id = Column(String(200), nullable=True)  # Stripe payment ID or call session ID

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("FamilyMember", back_populates="transactions")
