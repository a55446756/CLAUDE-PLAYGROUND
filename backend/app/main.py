"""
亲声伴 (QinShengBan) — Backend API
FastAPI application entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import Base, engine
from app.routes import auth, family, calls, voice_webhook, tokens

# Create all tables
Base.metadata.create_all(bind=engine)

# Create recordings directory
os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="老人AI陪伴系统 — 让AI成为孩子的声音",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", settings.BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(family.router, prefix="/api")
app.include_router(calls.router, prefix="/api")
app.include_router(tokens.router, prefix="/api")
app.include_router(voice_webhook.router)  # No /api prefix — Twilio webhooks

# Health check
@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
def root():
    return {
        "message": "亲声伴 API",
        "docs": "/api/docs",
        "health": "/health",
    }
