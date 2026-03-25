"""LLM 脚本生成模块 — 将新闻素材转化为主播播报脚本"""

import json
import logging
import re
from datetime import datetime
from typing import Any

import anthropic

from templates.prompt_templates import (
    ANCHOR_PERSONA,
    LOWER_THIRD_PROMPT,
    NEWS_ITEM_TEMPLATE,
    SHOW_SCRIPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class ScriptWriter:
    """使用 LLM 生成主播播报脚本"""

    def __init__(self, config: dict):
        self.config = config
        provider = config.get("provider", "anthropic")

        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=config["api_key"])
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = config.get("max_tokens", 8000)
        self.temperature = config.get("temperature", 0.8)

    async def generate_script(
        self, news_items: list[dict[str, Any]], date: str | None = None
    ) -> dict[str, Any]:
        """生成完整的节目脚本

        Returns:
            {
                "full_script": str,        # 完整脚本文本
                "segments": list[dict],    # 分段列表
                "lower_thirds": list[dict] # 标题栏数据
            }
        """
        if date is None:
            date = datetime.now().strftime("%Y年%m月%d日")

        # 格式化新闻素材
        news_text = self._format_news_items(news_items)

        # 生成主脚本
        prompt = SHOW_SCRIPT_TEMPLATE.format(
            persona=ANCHOR_PERSONA, news_items=news_text, date=date
        )

        logger.info("Generating show script via LLM...")
        full_script = self._call_llm(prompt)

        # 解析分段
        segments = self._parse_segments(full_script)

        # 生成标题栏数据
        lower_thirds = self._generate_lower_thirds(full_script)

        return {
            "full_script": full_script,
            "segments": segments,
            "lower_thirds": lower_thirds,
        }

    def _format_news_items(self, news_items: list[dict]) -> str:
        """将新闻列表格式化为 prompt 素材"""
        formatted = []
        for i, item in enumerate(news_items, 1):
            formatted.append(
                NEWS_ITEM_TEMPLATE.format(
                    title=item.get("title", ""),
                    source=item.get("source", ""),
                    summary=item.get("summary", ""),
                    published_at=item.get("published_at", ""),
                )
            )
        return "\n".join(formatted)

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def _parse_segments(self, script: str) -> list[dict[str, str]]:
        """解析脚本中的分段标记"""
        segments = []
        # 匹配 [TAG] 后面的内容直到下一个 [TAG] 或结尾
        pattern = r"\[(\w+(?:_\d+)?)\]\s*(.*?)(?=\[\w+(?:_\d+)?\]|\Z)"
        matches = re.findall(pattern, script, re.DOTALL)

        for tag, content in matches:
            content = content.strip()
            if content:
                segments.append(
                    {
                        "tag": tag,
                        "content": content,
                        "estimated_duration": self._estimate_duration(content),
                    }
                )

        return segments

    def _generate_lower_thirds(self, script: str) -> list[dict]:
        """通过 LLM 生成新闻标题栏数据"""
        try:
            prompt = LOWER_THIRD_PROMPT.format(script=script)
            response = self._call_llm(prompt)

            # 尝试解析 JSON
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Failed to generate lower thirds: {e}")

        return []

    @staticmethod
    def _estimate_duration(text: str) -> float:
        """估算中文文本的播报时长（秒）
        中文播报速度约 250 字/分钟
        """
        char_count = len(re.sub(r"\s+", "", text))
        return (char_count / 250) * 60
