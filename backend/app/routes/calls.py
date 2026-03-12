"""Call history routes — view recordings, summaries, and analytics."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.models.user import FamilyMember
from app.models.conversation import CallSession, ConversationTurn
from app.routes.auth import get_current_member

router = APIRouter(prefix="/calls", tags=["calls"])


# --- Schemas ---

class CallSummaryResponse(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime]
    duration_minutes: float
    emotion_score: Optional[float]
    emotion_description: Optional[str]
    ai_summary: Optional[str]
    health_keywords: list
    topics_discussed: list
    action_items: list
    alert_triggered: bool
    recording_url: Optional[str]

    class Config:
        from_attributes = True


class ConversationTurnResponse(BaseModel):
    turn_number: int
    role: str
    content: str
    created_at: datetime


# --- Routes ---

@router.get("/", response_model=List[CallSummaryResponse])
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """List call history for the family group."""
    offset = (page - 1) * page_size
    sessions = (
        db.query(CallSession)
        .filter(CallSession.family_group_id == current_member.family_group_id)
        .order_by(CallSession.started_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return [
        CallSummaryResponse(
            id=s.id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            duration_minutes=round(s.duration_seconds / 60, 1),
            emotion_score=s.emotion_score,
            emotion_description=_emotion_label(s.emotion_score),
            ai_summary=s.ai_summary,
            health_keywords=s.health_keywords or [],
            topics_discussed=s.topics_discussed or [],
            action_items=s.action_items or [],
            alert_triggered=s.alert_triggered,
            recording_url=s.recording_url,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=CallSummaryResponse)
def get_call_detail(
    session_id: int,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    session = db.query(CallSession).filter(
        CallSession.id == session_id,
        CallSession.family_group_id == current_member.family_group_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="通话记录不存在")

    return CallSummaryResponse(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_minutes=round(session.duration_seconds / 60, 1),
        emotion_score=session.emotion_score,
        emotion_description=_emotion_label(session.emotion_score),
        ai_summary=session.ai_summary,
        health_keywords=session.health_keywords or [],
        topics_discussed=session.topics_discussed or [],
        action_items=session.action_items or [],
        alert_triggered=session.alert_triggered,
        recording_url=session.recording_url,
    )


@router.get("/{session_id}/transcript", response_model=List[ConversationTurnResponse])
def get_transcript(
    session_id: int,
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """Get full conversation transcript for a call."""
    session = db.query(CallSession).filter(
        CallSession.id == session_id,
        CallSession.family_group_id == current_member.family_group_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="通话记录不存在")

    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.session_id == session_id)
        .order_by(ConversationTurn.turn_number)
        .all()
    )
    return [
        ConversationTurnResponse(
            turn_number=t.turn_number,
            role=t.role,
            content=t.content,
            created_at=t.created_at,
        )
        for t in turns
    ]


@router.get("/stats/overview")
def get_stats(
    current_member: FamilyMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """Get call statistics for the dashboard."""
    from sqlalchemy import func
    from datetime import timedelta

    family_group_id = current_member.family_group_id

    total_calls = db.query(func.count(CallSession.id)).filter(
        CallSession.family_group_id == family_group_id
    ).scalar() or 0

    total_duration = db.query(func.sum(CallSession.duration_seconds)).filter(
        CallSession.family_group_id == family_group_id
    ).scalar() or 0

    # Last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_sessions = db.query(CallSession).filter(
        CallSession.family_group_id == family_group_id,
        CallSession.started_at >= thirty_days_ago,
    ).order_by(CallSession.started_at).all()

    avg_emotion = None
    if recent_sessions:
        scores = [s.emotion_score for s in recent_sessions if s.emotion_score]
        if scores:
            avg_emotion = round(sum(scores) / len(scores), 2)

    emotion_trend = [
        {
            "date": s.started_at.strftime("%Y-%m-%d"),
            "score": s.emotion_score,
            "duration_minutes": round(s.duration_seconds / 60, 1),
        }
        for s in recent_sessions
        if s.emotion_score
    ]

    return {
        "total_calls": total_calls,
        "total_hours": round(total_duration / 3600, 1),
        "avg_emotion_score": avg_emotion,
        "emotion_trend": emotion_trend,
        "recent_calls_count": len(recent_sessions),
    }


def _emotion_label(score: Optional[float]) -> str:
    if score is None:
        return "未分析"
    if score >= 4.5:
        return "非常开心"
    elif score >= 3.5:
        return "心情不错"
    elif score >= 2.5:
        return "状态一般"
    elif score >= 1.5:
        return "有点低落"
    else:
        return "情绪低落"
