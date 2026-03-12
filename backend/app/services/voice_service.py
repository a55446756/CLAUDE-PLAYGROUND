"""
Twilio voice service — handles TwiML generation, STT, TTS, and recording.
This module bridges the phone call with the AI conversation engine.
"""
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from app.core.config import settings

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

# Voice settings for Chinese TTS
TTS_VOICE = "Google.cmn-CN-Wavenet-A"  # Mandarin Chinese female voice
TTS_LANGUAGE = "zh-CN"


def build_gather_twiml(
    action_url: str,
    say_text: Optional[str] = None,
    timeout: int = 10,
    speech_timeout: str = "auto",
) -> str:
    """
    Build TwiML that speaks text and then listens for speech input.
    Used for each conversation turn.
    """
    response = VoiceResponse()

    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        timeout=timeout,
        speech_timeout=speech_timeout,
        language=TTS_LANGUAGE,
        hints="你好,再见,不舒服,吃饭了,身体,最近",  # Speech recognition hints
    )

    if say_text:
        gather.say(say_text, voice=TTS_VOICE, language=TTS_LANGUAGE)

    response.append(gather)

    # Fallback if no speech detected
    response.redirect(action_url + "?no_input=true", method="POST")

    return str(response)


def build_say_twiml(text: str, redirect_url: Optional[str] = None) -> str:
    """Build TwiML that just speaks text (no input expected)."""
    response = VoiceResponse()
    response.say(text, voice=TTS_VOICE, language=TTS_LANGUAGE)
    if redirect_url:
        response.redirect(redirect_url, method="POST")
    return str(response)


def build_end_call_twiml(farewell_text: str) -> str:
    """Build TwiML for ending a call with a farewell message."""
    response = VoiceResponse()
    response.say(farewell_text, voice=TTS_VOICE, language=TTS_LANGUAGE)
    response.hangup()
    return str(response)


def start_recording(call_sid: str) -> str:
    """Start recording an active call. Returns recording SID."""
    recording = twilio_client.calls(call_sid).recordings.create(
        recording_channels="dual",  # Capture both sides
    )
    return recording.sid


def get_recording_url(recording_sid: str) -> str:
    """Get the URL for a completed recording."""
    recording = twilio_client.recordings(recording_sid).fetch()
    return f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"


def send_sms(to: str, body: str) -> None:
    """Send an SMS notification to a family member."""
    twilio_client.messages.create(
        body=body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to,
    )


# Fix missing Optional import
from typing import Optional
