"""
AI conversation service using Claude.
Handles system prompt construction, conversation management, and post-call analysis.
"""
import json
from typing import Optional
from anthropic import Anthropic
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Emergency keywords that should trigger family alerts
EMERGENCY_KEYWORDS = [
    "不舒服", "难受", "胸口疼", "胸痛", "头晕", "晕倒", "摔倒", "摔了",
    "救命", "叫救护车", "120", "去医院", "进医院", "住院",
    "喘不上来气", "心脏", "脑子", "出血", "骨折",
]

# Health-related keywords to extract
HEALTH_KEYWORDS = [
    "头疼", "头痛", "腰疼", "腿疼", "肚子疼", "吃不下", "睡不好",
    "血压", "血糖", "心脏", "咳嗽", "发烧", "感冒", "药",
    "医院", "检查", "手术", "复查", "不舒服", "难受", "疼痛",
]


def build_system_prompt(
    elderly_name: str,
    ai_name: str,
    elder_calls_ai: str,
    relation_to_elderly: str,
    personality_notes: str,
    health_notes: str,
    interests: str,
    family_updates: list[dict],
    last_session_summary: Optional[str] = None,
) -> str:
    """
    Build a personalized system prompt for the AI companion.
    """
    updates_text = ""
    if family_updates:
        updates_text = "\n".join([
            f"- [{u['author']}({u['relation']})] {u['content']}"
            for u in family_updates
        ])
    else:
        updates_text = "暂时没有新动态。"

    last_session_text = ""
    if last_session_summary:
        last_session_text = f"\n上次通话要点（请不要重复，但可以顺着话题延伸）：\n{last_session_summary}"

    return f"""你是{elderly_name}的{relation_to_elderly}，现在正在陪{elderly_name}打电话聊天。
你的名字叫"{ai_name}"，{elderly_name}叫你"{elder_calls_ai}"。

【老人基本情况】
- 性格特点：{personality_notes or '温和，喜欢聊家常'}
- 健康注意事项：{health_notes or '无特殊情况'}
- 兴趣爱好：{interests or '聊天、聊家里的事'}

【家里最近的情况（你要自然地告诉老人，不要一股脑全说出来，找时机融入对话）】
{updates_text}
{last_session_text}

【对话要求】
1. 语气温和、亲切，像真正的家人一样，适当用"妈"、"爸"等称呼
2. 语速不要太快，说话要简单清晰，一次不要说太多内容
3. 多关心老人的身体状况（吃饭了吗？睡得好吗？最近身体怎么样？）
4. 自然地分享家里的近况，不要生硬地"播报"
5. 如果老人提到不舒服或者身体有问题，要表达关心，建议去看医生，并告知会通知其他家人
6. 聊天时长大约10-20分钟，不要太长也不要太短
7. 结束时说一些温暖的话，告诉老人有空就打电话来
8. 【重要】如果老人说了紧急情况（突然不舒服、摔倒等），立刻说会马上通知家人，并建议打120

【禁止事项】
- 不要提到"AI"、"人工智能"、"机器人"、"语言模型"
- 不要表现得像客服或助手
- 不要一次说太多话
- 不要用书面语，要用口语
"""


def build_greeting(elderly_name: str, ai_name: str, elder_calls_ai: str) -> str:
    """Generate the opening greeting when the call connects."""
    return f"""请你先打招呼，语气要像刚接到老人电话的家人一样。
说类似："妈！是我{ai_name}啊，您今天怎么样？"或者"爸，{ai_name}在呢，最近身体还好吗？"
根据时间段适当调整（早上/下午/晚上）。只说打招呼的话，不超过2句。"""


async def chat_with_elderly(
    messages: list[dict],
    system_prompt: str,
) -> str:
    """
    Send a conversation turn to Claude and get a response.
    """
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=300,  # Keep responses concise for voice
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


async def generate_greeting(system_prompt: str, elderly_name: str, ai_name: str, elder_calls_ai: str) -> str:
    """Generate the opening line when the call connects."""
    greeting_prompt = build_greeting(elderly_name, ai_name, elder_calls_ai)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": greeting_prompt}],
    )
    return response.content[0].text


async def analyze_call(transcript: str, elderly_name: str) -> dict:
    """
    Post-call analysis: generate summary, emotion score, extract health keywords.
    """
    prompt = f"""请分析以下{elderly_name}的通话记录，返回JSON格式的分析结果。

通话记录：
{transcript}

请返回以下JSON格式（只返回JSON，不要其他内容）：
{{
    "summary": "2-4句话的通话摘要，供家人阅读",
    "emotion_score": 3.5,  // 老人情绪评分，1-5分，5分最开心
    "emotion_description": "老人今天情绪的一句话描述",
    "health_mentions": ["提到的身体相关内容列表"],
    "topics_discussed": ["主要聊了哪些话题"],
    "action_items": ["家人需要跟进的事项，如有的话"],
    "alert_needed": false,  // 是否需要紧急提醒家人
    "alert_reason": ""  // 如果需要提醒，原因是什么
}}"""

    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Extract JSON from response
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": "通话分析生成失败",
            "emotion_score": 3.0,
            "emotion_description": "无法分析",
            "health_mentions": [],
            "topics_discussed": [],
            "action_items": [],
            "alert_needed": False,
            "alert_reason": "",
        }


def check_emergency_keywords(text: str) -> tuple[bool, str]:
    """Check if the text contains emergency keywords."""
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in text:
            return True, keyword
    return False, ""


def extract_health_keywords(text: str) -> list[str]:
    """Extract health-related keywords from text."""
    found = []
    for keyword in HEALTH_KEYWORDS:
        if keyword in text and keyword not in found:
            found.append(keyword)
    return found
