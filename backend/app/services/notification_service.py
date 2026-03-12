"""
Notification service — alerts family members via SMS and in-app notifications.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import FamilyMember, FamilyGroup
from app.models.conversation import CallSession
from app.services.voice_service import send_sms
from app.core.config import settings


def notify_family_call_started(
    db: Session,
    family_group_id: int,
    elderly_name: str,
) -> None:
    """Notify family members when elderly starts a call."""
    members = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.is_active == True,
    ).all()

    for member in members:
        if member.phone:
            try:
                send_sms(
                    to=member.phone,
                    body=f"【亲声伴】{elderly_name}刚刚拨打了陪伴电话，正在聊天中 😊",
                )
            except Exception:
                pass  # Don't fail if SMS fails


def notify_family_call_ended(
    db: Session,
    family_group_id: int,
    elderly_name: str,
    session: CallSession,
) -> None:
    """Notify family members with call summary after call ends."""
    members = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.is_active == True,
    ).all()

    duration_min = session.duration_seconds // 60
    emotion_emoji = _emotion_to_emoji(session.emotion_score)

    summary_short = session.ai_summary[:100] if session.ai_summary else "通话已结束"

    for member in members:
        if member.phone:
            try:
                send_sms(
                    to=member.phone,
                    body=(
                        f"【亲声伴】{elderly_name}的通话已结束\n"
                        f"时长：{duration_min}分钟 情绪：{emotion_emoji}\n"
                        f"{summary_short}\n"
                        f"查看完整记录：{settings.BASE_URL}/calls/{session.id}"
                    ),
                )
            except Exception:
                pass


def notify_emergency(
    db: Session,
    family_group_id: int,
    elderly_name: str,
    reason: str,
) -> None:
    """Send urgent alert to all family members."""
    members = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.is_active == True,
    ).all()

    for member in members:
        if member.phone:
            try:
                send_sms(
                    to=member.phone,
                    body=(
                        f"【亲声伴 紧急提醒⚠️】\n"
                        f"{elderly_name}在通话中提到：{reason}\n"
                        f"请尽快联系确认情况！"
                    ),
                )
            except Exception:
                pass


def notify_low_balance(
    db: Session,
    family_group_id: int,
    remaining_minutes: int,
) -> None:
    """Notify admin when token balance is low."""
    # Find admin member
    admin = db.query(FamilyMember).filter(
        FamilyMember.family_group_id == family_group_id,
        FamilyMember.role == "admin",
        FamilyMember.is_active == True,
    ).first()

    if admin and admin.phone:
        try:
            send_sms(
                to=admin.phone,
                body=(
                    f"【亲声伴】通话时长余额不足\n"
                    f"剩余约{remaining_minutes}分钟，请及时充值\n"
                    f"充值地址：{settings.BASE_URL}/recharge"
                ),
            )
        except Exception:
            pass


def _emotion_to_emoji(score: Optional[float]) -> str:
    if score is None:
        return "😊"
    if score >= 4.5:
        return "😄 很开心"
    elif score >= 3.5:
        return "😊 心情不错"
    elif score >= 2.5:
        return "😐 一般"
    elif score >= 1.5:
        return "😔 有点低落"
    else:
        return "😢 情绪低落"
