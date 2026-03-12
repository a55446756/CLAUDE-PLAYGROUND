from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class FamilyUpdate(Base):
    """Life updates that family members share for the AI to relay to the elderly"""
    __tablename__ = "family_updates"

    id = Column(Integer, primary_key=True, index=True)
    family_group_id = Column(Integer, ForeignKey("family_groups.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("family_members.id"), nullable=False)

    content = Column(Text, nullable=False)    # The update text
    category = Column(String(50), default="general")  # "health", "work", "family", "travel", "general"

    # Whether the AI has already told the elderly about this
    has_been_shared = Column(Boolean, default=False)
    shared_at = Column(DateTime(timezone=True), nullable=True)
    shared_in_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=True)

    # Visibility: show to elderly or keep as context only
    share_with_elderly = Column(Boolean, default=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-expire old updates
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    family_group = relationship("FamilyGroup", back_populates="updates")
    author = relationship("FamilyMember", back_populates="updates")
