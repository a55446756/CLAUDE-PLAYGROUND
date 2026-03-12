from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class CallSession(Base):
    """A single phone call session"""
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True)
    family_group_id = Column(Integer, ForeignKey("family_groups.id"), nullable=False)
    elderly_id = Column(Integer, ForeignKey("elderly_profiles.id"), nullable=False)

    twilio_call_sid = Column(String(100), unique=True, index=True)
    caller_phone = Column(String(20))

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)

    recording_url = Column(String(500), nullable=True)
    recording_sid = Column(String(100), nullable=True)
    transcript = Column(Text, nullable=True)  # Full conversation transcript

    # AI-generated analysis
    ai_summary = Column(Text, nullable=True)              # Summary for family
    emotion_score = Column(Float, nullable=True)          # 1-5 scale
    health_keywords = Column(JSON, default=list)          # Extracted health mentions
    topics_discussed = Column(JSON, default=list)         # Main topics
    action_items = Column(JSON, default=list)             # Things family should follow up on

    # Alerts
    alert_triggered = Column(Boolean, default=False)
    alert_reason = Column(String(500), nullable=True)
    alert_notified = Column(Boolean, default=False)

    # Token usage
    tokens_consumed = Column(Integer, default=0)  # AI tokens used

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    family_group = relationship("FamilyGroup", back_populates="call_sessions")
    elderly = relationship("ElderlyProfile", back_populates="call_sessions")
    turns = relationship("ConversationTurn", back_populates="session", order_by="ConversationTurn.turn_number")


class ConversationTurn(Base):
    """A single exchange in a conversation"""
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)

    role = Column(String(20), nullable=False)   # "user" (elderly) or "assistant" (AI)
    content = Column(Text, nullable=False)       # Transcribed or generated text
    audio_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("CallSession", back_populates="turns")
