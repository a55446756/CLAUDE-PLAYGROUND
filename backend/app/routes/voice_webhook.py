"""
Twilio voice webhook handlers.
These endpoints receive callbacks from Twilio during a phone call and orchestrate
the AI conversation in real-time.

Call flow:
  1. /voice/inbound   — Twilio calls this when elderly dials the number
  2. /voice/respond   — Called after each speech input, returns AI response
  3. /voice/status    — Called when call ends (for cleanup/analysis)
  4. /voice/recording — Called when recording is ready
"""
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.user import ElderlyProfile, FamilyGroup
from app.models.conversation import CallSession, ConversationTurn
from app.models.family_update import FamilyUpdate
from app.services.ai_service import (
    build_system_prompt, chat_with_elderly, generate_greeting,
    analyze_call, check_emergency_keywords, extract_health_keywords,
)
from app.services.voice_service import (
    build_gather_twiml, build_end_call_twiml, build_say_twiml,
)
from app.services.notification_service import (
    notify_family_call_started, notify_family_call_ended, notify_emergency, notify_low_balance,
)
from app.services.token_service import get_family_balance, deduct_tokens

router = APIRouter(prefix="/voice", tags=["voice"])

# In-memory conversation state (use Redis in production)
# key: call_sid, value: {messages: [...], session_id: int, turn_count: int}
_call_state: dict = {}


def _get_system_prompt_for_family(db: Session, family_group_id: int) -> tuple[str, ElderlyProfile]:
    """Build the AI system prompt from family data."""
    elderly = db.query(ElderlyProfile).filter(
        ElderlyProfile.family_group_id == family_group_id
    ).first()

    if not elderly:
        raise ValueError("Elderly profile not found")

    # Get active family updates (not yet shared, not expired)
    updates_query = db.query(FamilyUpdate).filter(
        FamilyUpdate.family_group_id == family_group_id,
        FamilyUpdate.share_with_elderly == True,
        FamilyUpdate.has_been_shared == False,
    )
    updates = updates_query.order_by(FamilyUpdate.created_at.desc()).limit(5).all()

    from app.models.user import FamilyMember
    updates_data = []
    for u in updates:
        author = db.query(FamilyMember).filter(FamilyMember.id == u.author_id).first()
        updates_data.append({
            "author": author.name if author else "家人",
            "relation": author.relation_to_elderly if author else "家人",
            "content": u.content,
        })

    # Get last session summary
    last_session = db.query(CallSession).filter(
        CallSession.elderly_id == elderly.id
    ).order_by(CallSession.started_at.desc()).first()

    last_summary = last_session.ai_summary if last_session else None

    # Get primary family member info
    from app.models.user import FamilyMember, MemberRole
    admin = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.role == MemberRole.admin,
    ).first()

    relation = admin.relation_to_elderly if admin else "孩子"

    system_prompt = build_system_prompt(
        elderly_name=elderly.name,
        ai_name=elderly.ai_name,
        elder_calls_ai=elderly.elder_calls_ai,
        relation_to_elderly=relation,
        personality_notes=elderly.personality_notes,
        health_notes=elderly.health_notes,
        interests=elderly.interests,
        family_updates=updates_data,
        last_session_summary=last_summary,
    )
    return system_prompt, elderly


@router.post("/inbound")
async def handle_inbound_call(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
):
    """Entry point when elderly dials the phone number."""
    caller_phone = From

    # Find the elderly profile by their phone number or by the called number
    elderly = db.query(ElderlyProfile).filter(
        ElderlyProfile.phone == caller_phone
    ).first()

    if not elderly:
        # Caller not registered — play a friendly message
        twiml = build_say_twiml(
            "对不起，您的号码暂未注册。请联系您的家人为您开通服务。再见！"
        )
        return Response(content=twiml, media_type="application/xml")

    # Check token balance
    balance = get_family_balance(db, elderly.family_group_id)
    if balance <= 0:
        twiml = build_say_twiml(
            f"您好，{elderly.name}。通话时长已用完，请联系家人充值后再来哦，再见！"
        )
        return Response(content=twiml, media_type="application/xml")

    # Create call session record
    session = CallSession(
        family_group_id=elderly.family_group_id,
        elderly_id=elderly.id,
        twilio_call_sid=CallSid,
        caller_phone=caller_phone,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Build system prompt
    try:
        system_prompt, elderly = _get_system_prompt_for_family(db, elderly.family_group_id)
    except Exception as e:
        twiml = build_say_twiml("系统出现了一点问题，请稍后再拨。")
        return Response(content=twiml, media_type="application/xml")

    # Generate greeting
    greeting = await generate_greeting(system_prompt, elderly.name, elderly.ai_name, elderly.elder_calls_ai)

    # Initialize call state
    _call_state[CallSid] = {
        "messages": [{"role": "assistant", "content": greeting}],
        "session_id": session.id,
        "turn_count": 0,
        "system_prompt": system_prompt,
        "elderly_id": elderly.id,
        "family_group_id": elderly.family_group_id,
    }

    # Save greeting as first turn
    turn = ConversationTurn(
        session_id=session.id,
        turn_number=0,
        role="assistant",
        content=greeting,
    )
    db.add(turn)
    db.commit()

    # Notify family in background
    background_tasks.add_task(
        notify_family_call_started, db, elderly.family_group_id, elderly.name
    )

    action_url = f"{settings.BASE_URL}/voice/respond"
    twiml = build_gather_twiml(action_url=action_url, say_text=greeting)
    return Response(content=twiml, media_type="application/xml")


@router.post("/respond")
async def handle_speech_input(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[str] = Form(None),
):
    """Handle each speech turn from the elderly person."""
    state = _call_state.get(CallSid)
    if not state:
        twiml = build_end_call_twiml("系统出现了问题，再见！")
        return Response(content=twiml, media_type="application/xml")

    session_id = state["session_id"]
    family_group_id = state["family_group_id"]
    system_prompt = state["system_prompt"]
    turn_count = state["turn_count"] + 1

    # Handle no speech / timeout
    user_text = SpeechResult or ""
    if not user_text.strip():
        # Check if elderly has been quiet for a while
        if turn_count > 30:  # ~30 minutes max
            farewell = "时间不早了，您好好休息，有空再聊。记得按时吃饭，爱您！"
            _cleanup_call(db, CallSid, session_id, family_group_id, background_tasks)
            twiml = build_end_call_twiml(farewell)
            return Response(content=twiml, media_type="application/xml")

        # Re-prompt gently
        gentle_prompt = "妈，您在吗？"
        twiml = build_gather_twiml(
            action_url=f"{settings.BASE_URL}/voice/respond",
            say_text=gentle_prompt,
            timeout=8,
        )
        return Response(content=twiml, media_type="application/xml")

    # Check for goodbye intent
    goodbye_words = ["再见", "挂了", "挂电话", "拜拜", "不聊了", "先挂了"]
    if any(word in user_text for word in goodbye_words):
        state["messages"].append({"role": "user", "content": user_text})
        farewell_response = await chat_with_elderly(
            messages=state["messages"],
            system_prompt=system_prompt + "\n用户要挂电话了，请说一句温暖的告别语，不超过30字。",
        )
        _save_turn(db, session_id, turn_count, "user", user_text)
        _save_turn(db, session_id, turn_count + 1, "assistant", farewell_response)
        _cleanup_call(db, CallSid, session_id, family_group_id, background_tasks)
        twiml = build_end_call_twiml(farewell_response)
        return Response(content=twiml, media_type="application/xml")

    # Check for emergency keywords
    is_emergency, emergency_keyword = check_emergency_keywords(user_text)

    # Add user turn to conversation
    state["messages"].append({"role": "user", "content": user_text})

    # Check token balance (deduct 1 minute per turn approximately)
    balance = get_family_balance(db, family_group_id)
    if balance <= 60:  # Less than 1 minute left
        response_text = (
            "我要先去忙一下，通话时间快到了，等家人充值后您再打来，我等您！好好保重，再见！"
        )
        _cleanup_call(db, CallSid, session_id, family_group_id, background_tasks)
        twiml = build_end_call_twiml(response_text)
        return Response(content=twiml, media_type="application/xml")

    # Get AI response
    try:
        ai_response = await chat_with_elderly(
            messages=state["messages"],
            system_prompt=system_prompt,
        )
    except Exception:
        ai_response = "稍等一下，我这边信号有点问题，您刚才说什么了？"

    # If emergency detected, append urgent notice to AI response
    if is_emergency:
        ai_response += " 妈，您先别担心，我马上联系家人过来看您，您先坐下来休息一下！"
        background_tasks.add_task(
            notify_emergency, db, family_group_id,
            "老人", f"通话中提到：{user_text[:50]}"
        )
        # Update session alert flag
        session = db.query(CallSession).filter(CallSession.id == session_id).first()
        if session:
            session.alert_triggered = True
            session.alert_reason = f"检测到关键词：{emergency_keyword}"
            db.commit()

    # Save turns
    _save_turn(db, session_id, turn_count, "user", user_text)
    _save_turn(db, session_id, turn_count + 1, "assistant", ai_response)

    # Update state
    state["messages"].append({"role": "assistant", "content": ai_response})
    state["turn_count"] = turn_count + 1

    # Deduct ~30 seconds per round trip
    deduct_tokens(db, family_group_id, 30, session_id)

    action_url = f"{settings.BASE_URL}/voice/respond"
    twiml = build_gather_twiml(action_url=action_url, say_text=ai_response)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def handle_call_status(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
):
    """Called by Twilio when the call status changes (completed, failed, etc.)."""
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        state = _call_state.get(CallSid)
        if state:
            _cleanup_call(
                db, CallSid, state["session_id"], state["family_group_id"],
                background_tasks, duration=int(CallDuration or 0)
            )

    return Response(content="", status_code=204)


@router.post("/recording")
async def handle_recording(
    db: Session = Depends(get_db),
    CallSid: str = Form(...),
    RecordingSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingStatus: str = Form(...),
):
    """Called by Twilio when a recording is ready."""
    if RecordingStatus == "completed":
        session = db.query(CallSession).filter(
            CallSession.twilio_call_sid == CallSid
        ).first()
        if session:
            session.recording_url = RecordingUrl + ".mp3"
            session.recording_sid = RecordingSid
            db.commit()

    return Response(content="", status_code=204)


# --- Helpers ---

def _save_turn(db: Session, session_id: int, turn_number: int, role: str, content: str):
    turn = ConversationTurn(
        session_id=session_id,
        turn_number=turn_number,
        role=role,
        content=content,
    )
    db.add(turn)
    db.commit()


def _cleanup_call(
    db: Session,
    call_sid: str,
    session_id: int,
    family_group_id: int,
    background_tasks: BackgroundTasks,
    duration: int = 0,
):
    """Mark call as ended and schedule post-call analysis."""
    session = db.query(CallSession).filter(CallSession.id == session_id).first()
    if session and not session.ended_at:
        session.ended_at = datetime.utcnow()
        if duration:
            session.duration_seconds = duration
        db.commit()

        # Schedule background analysis
        background_tasks.add_task(_post_call_analysis, session_id, family_group_id)

    # Clean up in-memory state
    _call_state.pop(call_sid, None)


async def _post_call_analysis(session_id: int, family_group_id: int):
    """Run post-call AI analysis and notify family."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        session = db.query(CallSession).filter(CallSession.id == session_id).first()
        if not session:
            return

        elderly = db.query(ElderlyProfile).filter(
            ElderlyProfile.id == session.elderly_id
        ).first()

        # Build transcript
        turns = db.query(ConversationTurn).filter(
            ConversationTurn.session_id == session_id
        ).order_by(ConversationTurn.turn_number).all()

        transcript_lines = []
        for t in turns:
            speaker = elderly.name if t.role == "user" else elderly.ai_name
            transcript_lines.append(f"{speaker}：{t.content}")
        transcript = "\n".join(transcript_lines)

        session.transcript = transcript

        # AI analysis
        analysis = await analyze_call(transcript, elderly.name)
        session.ai_summary = analysis.get("summary", "")
        session.emotion_score = analysis.get("emotion_score")
        session.health_keywords = analysis.get("health_mentions", [])
        session.topics_discussed = analysis.get("topics_discussed", [])
        session.action_items = analysis.get("action_items", [])

        # Check if analysis found alerts
        if analysis.get("alert_needed") and not session.alert_triggered:
            session.alert_triggered = True
            session.alert_reason = analysis.get("alert_reason", "")
            notify_emergency(db, family_group_id, elderly.name, session.alert_reason)

        db.commit()

        # Mark family updates as shared
        db.query(FamilyUpdate).filter(
            FamilyUpdate.family_group_id == family_group_id,
            FamilyUpdate.has_been_shared == False,
        ).update({
            "has_been_shared": True,
            "shared_at": datetime.utcnow(),
            "shared_in_session_id": session_id,
        })
        db.commit()

        # Notify family with summary
        notify_family_call_ended(db, family_group_id, elderly.name, session)

    finally:
        db.close()
