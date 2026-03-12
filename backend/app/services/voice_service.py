"""
Twilio voice service — handles TwiML generation, STT, TTS, and recording.
Language and voice are dynamically selected per elderly profile.
"""
from typing import Optional
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from app.core.config import settings
from app.models.user import SUPPORTED_LANGUAGES

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

# Fallback voice/language when profile language is not supported by Twilio TTS
_FALLBACK_VOICE = "Google.en-US-Wavenet-F"
_FALLBACK_LANGUAGE = "en-US"


def _get_voice_config(language: str) -> tuple[str, str]:
    """
    Return (tts_voice, stt_language) for the given BCP-47 language tag.
    Exact match first, then prefix match, then fallback to English.
    """
    if language in SUPPORTED_LANGUAGES:
        cfg = SUPPORTED_LANGUAGES[language]
        return cfg["tts_voice"], language

    # Try prefix match (e.g., "zh" → first zh-* entry)
    prefix = language.split("-")[0].lower()
    for tag, cfg in SUPPORTED_LANGUAGES.items():
        if tag.startswith(prefix):
            return cfg["tts_voice"], tag

    return _FALLBACK_VOICE, _FALLBACK_LANGUAGE


def _get_stt_hints(language: str) -> str:
    """Return speech-recognition hints for the given language."""
    if language in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[language].get("stt_hints", "")
    prefix = language.split("-")[0].lower()
    for tag, cfg in SUPPORTED_LANGUAGES.items():
        if tag.startswith(prefix):
            return cfg.get("stt_hints", "")
    return ""


def build_gather_twiml(
    action_url: str,
    say_text: Optional[str] = None,
    language: str = "en-US",
    timeout: int = 10,
    speech_timeout: str = "auto",
) -> str:
    """
    Build TwiML that speaks text and then listens for speech input.
    Language is dynamic per elderly profile.
    """
    voice, stt_lang = _get_voice_config(language)
    hints = _get_stt_hints(language)

    response = VoiceResponse()

    gather_kwargs = dict(
        input="speech",
        action=action_url,
        method="POST",
        timeout=timeout,
        speech_timeout=speech_timeout,
        language=stt_lang,
    )
    if hints:
        gather_kwargs["hints"] = hints

    gather = Gather(**gather_kwargs)

    if say_text:
        gather.say(say_text, voice=voice, language=stt_lang)

    response.append(gather)
    response.redirect(action_url + "?no_input=true", method="POST")

    return str(response)


def build_say_twiml(
    text: str,
    language: str = "en-US",
    redirect_url: Optional[str] = None,
) -> str:
    """Build TwiML that just speaks text (no input expected)."""
    voice, stt_lang = _get_voice_config(language)
    response = VoiceResponse()
    response.say(text, voice=voice, language=stt_lang)
    if redirect_url:
        response.redirect(redirect_url, method="POST")
    return str(response)


def build_end_call_twiml(farewell_text: str, language: str = "en-US") -> str:
    """Build TwiML for ending a call with a farewell message."""
    voice, stt_lang = _get_voice_config(language)
    response = VoiceResponse()
    response.say(farewell_text, voice=voice, language=stt_lang)
    response.hangup()
    return str(response)


def start_recording(call_sid: str) -> str:
    """Start recording an active call. Returns recording SID."""
    recording = twilio_client.calls(call_sid).recordings.create(
        recording_channels="dual",
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
