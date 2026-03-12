from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class MemberRole(str, enum.Enum):
    admin = "admin"       # Primary account holder (pays)
    member = "member"     # Can view and add updates


class FamilyGroup(Base):
    """A family group — one elderly person + multiple family members"""
    __tablename__ = "family_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "张家"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    elderly = relationship("ElderlyProfile", back_populates="family_group", uselist=False)
    members = relationship("FamilyMember", back_populates="family_group")
    updates = relationship("FamilyUpdate", back_populates="family_group")
    call_sessions = relationship("CallSession", back_populates="family_group")


class ElderlyProfile(Base):
    """Profile for the elderly person (they don't have an account)"""
    __tablename__ = "elderly_profiles"

    id = Column(Integer, primary_key=True, index=True)
    family_group_id = Column(Integer, ForeignKey("family_groups.id"), nullable=False)

    name = Column(String(50), nullable=False)               # e.g., "张奶奶"
    phone = Column(String(20), unique=True, index=True)     # Their phone number
    ai_name = Column(String(50), default="小明")             # What the AI calls itself
    elder_calls_ai = Column(String(50), default="孩子")      # What the elder calls the AI
    personality_notes = Column(Text, default="")            # Caregiver notes about personality
    health_notes = Column(Text, default="")                 # Known health conditions
    interests = Column(Text, default="")                    # Hobbies, topics they like
    photo_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    family_group = relationship("FamilyGroup", back_populates="elderly")
    call_sessions = relationship("CallSession", back_populates="elderly")


class FamilyMember(Base):
    """Family member who manages the account"""
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    family_group_id = Column(Integer, ForeignKey("family_groups.id"), nullable=False)

    name = Column(String(50), nullable=False)
    phone = Column(String(20), unique=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.member)

    # What this member calls themselves (for AI context)
    relation_to_elderly = Column(String(50), default="孩子")  # e.g., "大儿子", "女儿"

    token_balance_seconds = Column(Integer, default=0)  # Remaining call time in seconds
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    family_group = relationship("FamilyGroup", back_populates="members")
    updates = relationship("FamilyUpdate", back_populates="author")
    transactions = relationship("TokenTransaction", back_populates="member")
