"""
AI conversation service using Claude.
Handles multilingual system prompt construction, conversation management,
and post-call analysis.
"""
import json
from typing import Optional
from anthropic import Anthropic
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# --- Multilingual emergency keywords ---
# Keyed by BCP-47 language prefix (first segment)
EMERGENCY_KEYWORDS: dict[str, list[str]] = {
    "zh": ["不舒服", "难受", "胸口疼", "胸痛", "头晕", "晕倒", "摔倒", "摔了",
           "救命", "叫救护车", "120", "去医院", "住院", "喘不上来气", "出血", "骨折"],
    "en": ["help", "fallen", "chest pain", "can't breathe", "call 911", "ambulance",
           "emergency", "hospital", "collapsed", "stroke", "heart attack"],
    "es": ["ayuda", "me caí", "dolor en el pecho", "no puedo respirar", "ambulancia",
           "emergencia", "hospital", "llamar al médico"],
    "fr": ["aide", "je suis tombé", "douleur poitrine", "ambulance", "urgence", "hôpital"],
    "de": ["hilfe", "gestürzt", "brustschmerzen", "krankenwagen", "notfall", "krankenhaus"],
    "ja": ["助けて", "倒れた", "胸が痛い", "救急車", "緊急", "病院", "息ができない"],
    "ko": ["도와주세요", "넘어졌어요", "가슴이 아파요", "구급차", "응급", "병원"],
    "pt": ["ajuda", "caí", "dor no peito", "ambulância", "emergência", "hospital"],
    "hi": ["मदद", "गिर गया", "सीने में दर्द", "एम्बुलेंस", "अस्पताल"],
    "ar": ["مساعدة", "سقطت", "ألم في الصدر", "إسعاف", "طوارئ", "مستشفى"],
    "it": ["aiuto", "sono caduto", "dolore al petto", "ambulanza", "emergenza", "ospedale"],
}

# --- Multilingual health keywords ---
HEALTH_KEYWORDS: dict[str, list[str]] = {
    "zh": ["头疼", "头痛", "腰疼", "腿疼", "肚子疼", "吃不下", "睡不好",
           "血压", "血糖", "心脏", "咳嗽", "发烧", "感冒", "药", "医院",
           "检查", "手术", "不舒服", "疼痛"],
    "en": ["headache", "back pain", "leg pain", "stomach ache", "can't eat", "can't sleep",
           "blood pressure", "blood sugar", "heart", "cough", "fever", "cold", "medicine",
           "doctor", "hospital", "checkup", "surgery", "pain", "dizzy", "tired"],
    "es": ["dolor de cabeza", "dolor de espalda", "presión arterial", "azúcar en sangre",
           "corazón", "tos", "fiebre", "resfriado", "medicina", "médico", "hospital", "dolor"],
    "fr": ["mal de tête", "douleur dos", "tension artérielle", "glycémie", "coeur",
           "toux", "fièvre", "rhume", "médicament", "médecin", "hôpital", "douleur"],
    "de": ["kopfschmerzen", "rückenschmerzen", "blutdruck", "blutzucker", "herz",
           "husten", "fieber", "erkältung", "medikament", "arzt", "krankenhaus", "schmerz"],
    "ja": ["頭痛", "腰痛", "足が痛い", "お腹が痛い", "食欲がない", "眠れない",
           "血圧", "血糖", "心臓", "咳", "熱", "風邪", "薬", "病院", "検査"],
    "ko": ["두통", "요통", "배가 아파요", "식욕이 없어요", "잠을 못 자요",
           "혈압", "혈당", "심장", "기침", "열", "감기", "약", "병원"],
    "pt": ["dor de cabeça", "dor nas costas", "pressão arterial", "coração",
           "tosse", "febre", "resfriado", "remédio", "médico", "hospital", "dor"],
}

# --- Language-specific system prompt templates ---
SYSTEM_PROMPT_TEMPLATES: dict[str, str] = {
    "en": """You are {elderly_name}'s {relation}, calling to check in and chat.
Your name is "{ai_name}" and {elderly_name} calls you "{elder_calls_ai}".

[About {elderly_name}]
- Personality: {personality_notes}
- Health notes: {health_notes}
- Interests: {interests}

[Family news to share naturally during the conversation]
{updates_text}
{last_session_text}

[Guidelines]
1. Be warm, patient and loving — speak like a real family member, use "Mom", "Dad", etc.
2. Keep sentences short and clear. Speak at a comfortable pace.
3. Ask about their wellbeing: "How are you eating? Sleeping okay? How do you feel today?"
4. Weave family news naturally into conversation — don't read it out like a report.
5. If they mention feeling unwell or in pain, express concern and gently suggest seeing a doctor.
6. Keep the call to 10–20 minutes. End warmly — tell them to call anytime.
7. [IMPORTANT] If they mention something urgent (chest pain, fall, trouble breathing), say you'll alert the family immediately and suggest calling emergency services.

[Do NOT]
- Mention "AI", "artificial intelligence", "language model", or "robot"
- Act like a customer service agent or assistant
- Use formal/stiff language — keep it natural and conversational
""",

    "zh": """你是{elderly_name}的{relation}，正在陪{elderly_name}打电话聊天。
你的名字叫"{ai_name}"，{elderly_name}叫你"{elder_calls_ai}"。

【关于{elderly_name}】
- 性格特点：{personality_notes}
- 健康注意事项：{health_notes}
- 兴趣爱好：{interests}

【家里最近的情况（自然融入对话，不要生硬播报）】
{updates_text}
{last_session_text}

【对话要求】
1. 语气温和、亲切，像真正的家人，用"妈"、"爸"等称呼
2. 说话简单清晰，语速适中，一次不说太多
3. 关心老人：吃饭了吗？睡得好吗？身体怎么样？
4. 自然分享家里近况，不要生硬"播报"
5. 老人提到不舒服时，表达关心，建议看医生
6. 聊天10-20分钟，结尾说温暖的告别话
7. 【重要】老人提到紧急情况（胸痛/摔倒等），立刻说会通知家人，建议打急救电话

【禁止】
- 提到"AI"、"人工智能"、"机器人"、"语言模型"
- 表现得像客服或助手
- 使用书面语，要用口语
""",

    "es": """Eres el/la {relation} de {elderly_name} y estás llamando para charlar y ver cómo está.
Tu nombre es "{ai_name}" y {elderly_name} te llama "{elder_calls_ai}".

[Sobre {elderly_name}]
- Personalidad: {personality_notes}
- Salud: {health_notes}
- Intereses: {interests}

[Noticias familiares para compartir naturalmente]
{updates_text}
{last_session_text}

[Pautas]
1. Sé cálido/a y paciente — habla como un familiar real, usa "Mamá", "Papá", etc.
2. Frases cortas y claras. Habla despacio y con cariño.
3. Pregunta cómo está: "¿Has comido bien? ¿Dormiste? ¿Cómo te sientes?"
4. Comparte noticias familiares de forma natural.
5. Si menciona dolor o malestar, muéstrate preocupado/a y sugiere ver al médico.
6. Despídete con cariño y dile que puede llamar cuando quiera.
7. [IMPORTANTE] En emergencias, di que avisarás a la familia y sugiere llamar a emergencias.

[NO debes]
- Mencionar "IA", "inteligencia artificial" o "robot"
""",

    "fr": """Tu es le/la {relation} de {elderly_name} et tu appelles pour discuter.
Ton prénom est "{ai_name}" et {elderly_name} t'appelle "{elder_calls_ai}".

[À propos de {elderly_name}]
- Personnalité : {personality_notes}
- Santé : {health_notes}
- Intérêts : {interests}

[Nouvelles familiales à partager naturellement]
{updates_text}
{last_session_text}

[Consignes]
1. Sois chaleureux/se et patient/e — parle comme un vrai membre de la famille.
2. Phrases courtes et claires. Parle à un rythme confortable.
3. Demande comment ça va : "Tu as bien mangé ? Tu dors bien ?"
4. Partage les nouvelles familiales naturellement.
5. Si elle/il mentionne un malaise, montre-toi inquiet/e et suggère de voir un médecin.
6. Dis au revoir chaleureusement.
7. [IMPORTANT] En cas d'urgence, dis que tu préviens la famille et suggère d'appeler les secours.

[NE PAS]
- Mentionner "IA", "intelligence artificielle" ou "robot"
""",

    "de": """Du bist {elderly_name}s {relation} und rufst an zum Plaudern.
Dein Name ist "{ai_name}" und {elderly_name} nennt dich "{elder_calls_ai}".

[Über {elderly_name}]
- Persönlichkeit: {personality_notes}
- Gesundheit: {health_notes}
- Interessen: {interests}

[Familiennachrichten zum natürlichen Einbringen]
{updates_text}
{last_session_text}

[Richtlinien]
1. Sei herzlich und geduldig — sprich wie ein echtes Familienmitglied.
2. Kurze, klare Sätze in angenehm langsamem Tempo.
3. Frag nach dem Befinden: "Hast du gut gegessen? Schläfst du gut?"
4. Teile Familiennachrichten natürlich mit.
5. Bei Beschwerden zeige Sorge und empfehle einen Arztbesuch.
6. Verabschiede dich herzlich.
7. [WICHTIG] Bei Notfall informiere die Familie und empfehle den Notruf.

[NICHT]
- "KI", "Künstliche Intelligenz" oder "Roboter" erwähnen
""",

    "ja": """あなたは{elderly_name}の{relation}で、話し相手として電話しています。
あなたの名前は「{ai_name}」で、{elderly_name}はあなたを「{elder_calls_ai}」と呼びます。

【{elderly_name}について】
- 性格：{personality_notes}
- 健康メモ：{health_notes}
- 趣味・興味：{interests}

【家族の近況（自然に会話に織り交ぜてください）】
{updates_text}
{last_session_text}

【会話のルール】
1. 温かく、忍耐強く、本物の家族として話す。「お母さん」「お父さん」と呼ぶ。
2. 短く、わかりやすい文で話す。ゆっくり話す。
3. 体調を聞く：「ご飯食べた？よく眠れてる？体はどう？」
4. 家族の近況を自然に話す。
5. 体の不調を訴えたら心配して病院を勧める。
6. 温かく別れを告げる。
7. 【重要】緊急事態は家族に連絡すると伝え、救急車を勧める。

【禁止事項】
- 「AI」「人工知能」「ロボット」と言わない
""",

    "ko": """당신은 {elderly_name}의 {relation}으로, 안부 통화를 하고 있습니다.
당신의 이름은 "{ai_name}"이며, {elderly_name}은(는) 당신을 "{elder_calls_ai}"라고 부릅니다.

[{elderly_name}에 대해]
- 성격: {personality_notes}
- 건강: {health_notes}
- 관심사: {interests}

[자연스럽게 나눌 가족 소식]
{updates_text}
{last_session_text}

[대화 지침]
1. 따뜻하고 인내심 있게 — 진짜 가족처럼 말하기.
2. 짧고 명확한 문장. 편안한 속도로 말하기.
3. 안부 묻기: "밥은 잡수셨어요? 잘 주무셨어요? 몸은 어떠세요?"
4. 가족 소식을 자연스럽게 나누기.
5. 불편함을 호소하면 걱정을 표하고 병원 방문 권유.
6. 따뜻하게 인사하며 마무리.
7. [중요] 응급 상황 시 가족에게 알리겠다고 하고 응급 전화 권유.

[금지사항]
- "AI", "인공지능", "로봇" 언급 금지
""",

    "pt": """Você é o/a {relation} de {elderly_name} e está ligando para bater papo.
Seu nome é "{ai_name}" e {elderly_name} te chama de "{elder_calls_ai}".

[Sobre {elderly_name}]
- Personalidade: {personality_notes}
- Saúde: {health_notes}
- Interesses: {interests}

[Novidades da família para compartilhar naturalmente]
{updates_text}
{last_session_text}

[Diretrizes]
1. Seja carinhoso/a e paciente — fale como um familiar de verdade.
2. Frases curtas e claras. Fale em ritmo confortável.
3. Pergunte como está: "Você comeu bem? Dormiu direito?"
4. Compartilhe novidades da família de forma natural.
5. Se mencionar dor ou mal-estar, mostre preocupação e sugira ir ao médico.
6. Despida-se com carinho.
7. [IMPORTANTE] Em emergências, avise a família e sugira ligar para o SAMU/emergências.

[NÃO]
- Mencionar "IA", "inteligência artificial" ou "robô"
""",
}

DEFAULT_LANGUAGE = "en"


def _get_lang_key(language: str) -> str:
    """Get the template key from a BCP-47 language tag."""
    prefix = language.split("-")[0].lower()
    return prefix if prefix in SYSTEM_PROMPT_TEMPLATES else DEFAULT_LANGUAGE


def build_system_prompt(
    elderly_name: str,
    ai_name: str,
    elder_calls_ai: str,
    relation_to_elderly: str,
    personality_notes: str,
    health_notes: str,
    interests: str,
    family_updates: list[dict],
    language: str = "en-US",
    last_session_summary: Optional[str] = None,
) -> str:
    """Build a personalized, language-specific system prompt."""
    lang_key = _get_lang_key(language)
    template = SYSTEM_PROMPT_TEMPLATES.get(lang_key, SYSTEM_PROMPT_TEMPLATES["en"])

    updates_text = (
        "\n".join(f"- [{u['author']} ({u['relation']})] {u['content']}" for u in family_updates)
        if family_updates
        else _no_updates_text(lang_key)
    )

    last_session_text = (
        _last_session_prefix(lang_key) + last_session_summary
        if last_session_summary
        else ""
    )

    return template.format(
        elderly_name=elderly_name,
        ai_name=ai_name or relation_to_elderly,
        elder_calls_ai=elder_calls_ai or ai_name or relation_to_elderly,
        relation=relation_to_elderly,
        personality_notes=personality_notes or _default_personality(lang_key),
        health_notes=health_notes or _none_text(lang_key),
        interests=interests or _default_interests(lang_key),
        updates_text=updates_text,
        last_session_text=last_session_text,
    )


def _no_updates_text(lang: str) -> str:
    return {
        "zh": "暂时没有新动态。",
        "en": "No new family updates at this time.",
        "es": "Sin novedades familiares por ahora.",
        "fr": "Pas de nouvelles familiales pour le moment.",
        "de": "Derzeit keine Familienneuigkeiten.",
        "ja": "家族からの新しい近況はありません。",
        "ko": "현재 가족 소식이 없습니다.",
        "pt": "Sem novidades da família por enquanto.",
    }.get(lang, "No new family updates at this time.")


def _last_session_prefix(lang: str) -> str:
    return {
        "zh": "\n上次通话要点（可以顺着延伸，但不要重复）：\n",
        "en": "\nFrom last call (continue naturally, don't repeat):\n",
        "es": "\nDe la última llamada:\n",
        "fr": "\nDu dernier appel:\n",
        "de": "\nAus dem letzten Gespräch:\n",
        "ja": "\n前回の通話から：\n",
        "ko": "\n지난 통화에서:\n",
        "pt": "\nDa última ligação:\n",
    }.get(lang, "\nFrom last call:\n")


def _default_personality(lang: str) -> str:
    return {
        "zh": "温和，喜欢聊家常",
        "en": "Warm and enjoys chatting about family",
        "es": "Amable, le gusta charlar sobre la familia",
        "fr": "Chaleureux/se, aime parler de la famille",
        "de": "Warmherzig, redet gerne über die Familie",
        "ja": "穏やか、家族の話が好き",
        "ko": "따뜻하고 가족 이야기를 좋아함",
        "pt": "Caloroso/a, gosta de conversar sobre a família",
    }.get(lang, "Warm and enjoys chatting about family")


def _default_interests(lang: str) -> str:
    return {
        "zh": "聊天、聊家里的事",
        "en": "Chatting, family stories",
        "es": "Conversar, historias de familia",
        "fr": "Discuter, histoires de famille",
        "de": "Plaudern, Familiengeschichten",
        "ja": "おしゃべり、家族の話",
        "ko": "대화, 가족 이야기",
        "pt": "Conversar, histórias de família",
    }.get(lang, "Chatting, family stories")


def _none_text(lang: str) -> str:
    return {
        "zh": "无特殊情况",
        "en": "Nothing specific noted",
        "es": "Nada específico",
        "fr": "Rien de spécifique",
        "de": "Nichts Besonderes",
        "ja": "特になし",
        "ko": "특이 사항 없음",
        "pt": "Nada específico",
    }.get(lang, "Nothing specific noted")


async def chat_with_elderly(messages: list[dict], system_prompt: str) -> str:
    """Send a conversation turn to Claude and get a response."""
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


async def generate_greeting(
    system_prompt: str,
    elderly_name: str,
    ai_name: str,
    language: str = "en-US",
) -> str:
    """Generate the opening line when the call connects."""
    lang_key = _get_lang_key(language)
    instructions = {
        "zh": f"请打招呼，像刚接到电话的家人。例如"妈！是我{ai_name}啊，您今天怎么样？"。只说1-2句。",
        "en": f"Greet them warmly as if you just answered their call. E.g. 'Hi Mom! It's {ai_name}, how are you doing today?' 1-2 sentences only.",
        "es": f"Saluda calurosamente. Algo como '¡Hola Mamá! Soy {ai_name}, ¿cómo estás hoy?' Solo 1-2 frases.",
        "fr": f"Accueille-les chaleureusement. Quelque chose comme 'Bonjour Maman! C'est {ai_name}, comment tu vas?' Seulement 1-2 phrases.",
        "de": f"Begrüße herzlich. Etwa 'Hallo Mama! Ich bin's {ai_name}, wie geht's dir heute?' Nur 1-2 Sätze.",
        "ja": f"温かく挨拶。例：「もしもし！{ai_name}だよ、今日は調子はどう？」1〜2文で。",
        "ko": f"따뜻하게 인사. 예: '여보세요! {ai_name}이에요, 오늘 어떠세요?' 1-2문장.",
        "pt": f"Cumprimente carinhosamente. Algo como 'Oi Mãe! É o {ai_name}, como você tá?' 1-2 frases.",
    }
    instruction = instructions.get(lang_key, instructions["en"])

    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": instruction}],
    )
    return response.content[0].text


async def analyze_call(transcript: str, elderly_name: str, language: str = "en-US") -> dict:
    """Post-call analysis: summary, emotion score, health keywords."""
    lang_key = _get_lang_key(language)

    if lang_key == "zh":
        prompt = f"""请分析以下{elderly_name}的通话记录，返回JSON格式结果。

通话记录：
{transcript}

返回以下JSON（只返回JSON）：
{{
    "summary": "2-4句摘要，供家人阅读",
    "emotion_score": 3.5,
    "emotion_description": "老人情绪一句话描述",
    "health_mentions": ["身体相关内容"],
    "topics_discussed": ["聊了哪些话题"],
    "action_items": ["家人需跟进的事项"],
    "alert_needed": false,
    "alert_reason": ""
}}"""
    else:
        prompt = f"""Analyze the following call transcript with {elderly_name} and return a JSON result.

Transcript:
{transcript}

Return this JSON only (no other text):
{{
    "summary": "2-4 sentence summary for the family to read",
    "emotion_score": 3.5,
    "emotion_description": "One sentence describing their mood",
    "health_mentions": ["list of health-related things mentioned"],
    "topics_discussed": ["main topics covered"],
    "action_items": ["things the family should follow up on"],
    "alert_needed": false,
    "alert_reason": ""
}}"""

    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": "Analysis unavailable",
            "emotion_score": 3.0,
            "emotion_description": "Unknown",
            "health_mentions": [],
            "topics_discussed": [],
            "action_items": [],
            "alert_needed": False,
            "alert_reason": "",
        }


def check_emergency_keywords(text: str, language: str = "en-US") -> tuple[bool, str]:
    """Check if text contains emergency keywords for the given language."""
    lang_key = _get_lang_key(language)
    keywords = EMERGENCY_KEYWORDS.get(lang_key, EMERGENCY_KEYWORDS["en"])
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True, keyword
    return False, ""


def extract_health_keywords(text: str, language: str = "en-US") -> list[str]:
    """Extract health-related keywords from text."""
    lang_key = _get_lang_key(language)
    keywords = HEALTH_KEYWORDS.get(lang_key, HEALTH_KEYWORDS["en"])
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]
