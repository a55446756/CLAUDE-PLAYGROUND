from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CompanionCall"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = "sqlite:///./companioncall.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  # The number elderly people call (E.164 format)
    TWILIO_TWIML_APP_SID: str = ""

    # Storage for recordings
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    STORAGE_LOCAL_PATH: str = "./recordings"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: str = "companioncall-recordings"
    AWS_REGION: str = "us-east-1"   # Default to global AWS region; override as needed

    # Payments (Stripe — supports global currencies)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Default currency for new token packages (ISO 4217)
    DEFAULT_CURRENCY: str = "USD"

    # Base URL (must be public HTTPS for Twilio webhooks)
    BASE_URL: str = "http://localhost:8000"

    # Free trial for new accounts
    FREE_TRIAL_MINUTES: int = 60

    # Default language for new elderly profiles (BCP-47)
    DEFAULT_LANGUAGE: str = "en-US"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
