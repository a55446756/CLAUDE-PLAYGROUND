from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class MemberRole(str, enum.Enum):
    admin = "admin"       # Primary account holder (pays)
    member = "member"     # Can view and add updates


# Supported conversation languages (Twilio TTS / STT codes)
SUPPORTED_LANGUAGES = {
    "zh-CN": {"name": "Chinese (Mandarin)", "tts_voice": "Google.cmn-CN-Wavenet-A", "stt_hints": "你好,再见,不舒服,身体"},
    "zh-TW": {"name": "Chinese (Traditional)", "tts_voice": "Google.cmn-TW-Wavenet-A", "stt_hints": "你好,再見,不舒服,身體"},
    "en-US": {"name": "English (US)", "tts_voice": "Google.en-US-Wavenet-F", "stt_hints": "hello,goodbye,pain,help,hospital"},
    "en-GB": {"name": "English (UK)", "tts_voice": "Google.en-GB-Wavenet-C", "stt_hints": "hello,goodbye,pain,help,hospital"},
    "es-ES": {"name": "Spanish (Spain)", "tts_voice": "Google.es-ES-Wavenet-C", "stt_hints": "hola,adiós,dolor,ayuda,hospital"},
    "es-US": {"name": "Spanish (US)", "tts_voice": "Google.es-US-Wavenet-B", "stt_hints": "hola,adiós,dolor,ayuda,hospital"},
    "fr-FR": {"name": "French", "tts_voice": "Google.fr-FR-Wavenet-C", "stt_hints": "bonjour,au revoir,douleur,aide,hôpital"},
    "de-DE": {"name": "German", "tts_voice": "Google.de-DE-Wavenet-C", "stt_hints": "hallo,tschüss,schmerz,hilfe,krankenhaus"},
    "ja-JP": {"name": "Japanese", "tts_voice": "Google.ja-JP-Wavenet-B", "stt_hints": "こんにちは,さようなら,痛い,助けて,病院"},
    "ko-KR": {"name": "Korean", "tts_voice": "Google.ko-KR-Wavenet-B", "stt_hints": "안녕하세요,안녕히,아파요,도와주세요,병원"},
    "pt-BR": {"name": "Portuguese (Brazil)", "tts_voice": "Google.pt-BR-Wavenet-C", "stt_hints": "olá,tchau,dor,ajuda,hospital"},
    "hi-IN": {"name": "Hindi", "tts_voice": "Google.hi-IN-Wavenet-D", "stt_hints": "नमस्ते,अलविदा,दर्द,मदद,अस्पताल"},
    "ar-XA": {"name": "Arabic", "tts_voice": "Google.ar-XA-Wavenet-B", "stt_hints": "مرحبا,وداعا,ألم,مساعدة,مستشفى"},
    "it-IT": {"name": "Italian", "tts_voice": "Google.it-IT-Wavenet-C", "stt_hints": "ciao,arrivederci,dolore,aiuto,ospedale"},
}


class FamilyGroup(Base):
    """A family group — one elderly person + multiple family members"""
    __tablename__ = "family_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "Smith Family"
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

    name = Column(String(50), nullable=False)               # e.g., "Grandma Rose"
    phone = Column(String(30), unique=True, index=True)     # E.164 format: +12125551234
    country_code = Column(String(5), default="US")          # ISO 3166-1 alpha-2
    timezone = Column(String(50), default="UTC")            # IANA timezone: America/New_York
    language = Column(String(10), default="en-US")          # BCP-47 language tag

    ai_name = Column(String(50), default="")                # What the AI calls itself (family member's name)
    elder_calls_ai = Column(String(50), default="")         # What the elder calls the AI
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
    phone = Column(String(30), unique=True, index=True)     # E.164 format
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.member)

    # What this member calls themselves (for AI context)
    relation_to_elderly = Column(String(50), default="family member")  # e.g., "son", "daughter"
    preferred_language = Column(String(10), default="en-US")           # Portal UI language

    token_balance_seconds = Column(Integer, default=0)  # Remaining call time in seconds
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    family_group = relationship("FamilyGroup", back_populates="members")
    updates = relationship("FamilyUpdate", back_populates="author")
    transactions = relationship("TokenTransaction", back_populates="member")
