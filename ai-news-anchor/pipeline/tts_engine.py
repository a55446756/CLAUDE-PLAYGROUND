"""TTS 语音合成引擎 — 支持多个 TTS 服务"""

import io
import logging
from pathlib import Path
from typing import Any

import httpx
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class TTSEngine:
    """语音合成引擎，支持 ElevenLabs / Fish Audio / OpenAI TTS"""

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("provider", "elevenlabs")

    async def synthesize(
        self, text: str, output_path: str | Path
    ) -> dict[str, Any]:
        """将文本合成为音频文件

        Returns:
            {"path": str, "duration_seconds": float}
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.provider == "elevenlabs":
            audio_data = await self._elevenlabs_tts(text)
        elif self.provider == "fish_audio":
            audio_data = await self._fish_audio_tts(text)
        elif self.provider == "openai":
            audio_data = await self._openai_tts(text)
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

        # 保存音频
        output_path.write_bytes(audio_data)

        # 获取时长
        audio = AudioSegment.from_file(io.BytesIO(audio_data))
        duration = len(audio) / 1000.0

        logger.info(f"TTS complete: {output_path} ({duration:.1f}s)")
        return {"path": str(output_path), "duration_seconds": duration}

    async def synthesize_segments(
        self, segments: list[dict], output_dir: str | Path
    ) -> list[dict[str, Any]]:
        """分段合成音频，每个段落一个文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for i, segment in enumerate(segments):
            tag = segment.get("tag", f"segment_{i}")
            text = segment["content"]
            output_path = output_dir / f"{i:02d}_{tag}.mp3"

            logger.info(f"Synthesizing segment {tag} ({len(text)} chars)...")
            result = await self.synthesize(text, output_path)
            result["tag"] = tag
            result["segment_index"] = i
            results.append(result)

        return results

    async def _elevenlabs_tts(self, text: str) -> bytes:
        """ElevenLabs TTS API"""
        el_config = self.config.get("elevenlabs", {})
        voice_id = el_config.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
        model_id = el_config.get("model_id", "eleven_multilingual_v2")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.config["api_key"],
            "Content-Type": "application/json",
        }

        # 长文本需要分块处理（ElevenLabs 单次限制 ~5000 字符）
        chunks = self._split_text(text, max_chars=4500)
        audio_parts = []

        async with httpx.AsyncClient(timeout=120) as client:
            for chunk in chunks:
                payload = {
                    "text": chunk,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": el_config.get("stability", 0.5),
                        "similarity_boost": el_config.get(
                            "similarity_boost", 0.75
                        ),
                        "style": el_config.get("style", 0.4),
                    },
                }
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                audio_parts.append(resp.content)

        # 合并音频块
        if len(audio_parts) == 1:
            return audio_parts[0]
        return self._merge_audio_bytes(audio_parts)

    async def _fish_audio_tts(self, text: str) -> bytes:
        """Fish Audio TTS API"""
        fa_config = self.config.get("fish_audio", {})
        url = "https://api.fish.audio/v1/tts"
        headers = {
            "Authorization": f"Bearer {fa_config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "reference_id": fa_config.get("voice_id"),
            "format": "mp3",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content

    async def _openai_tts(self, text: str) -> bytes:
        """OpenAI TTS API"""
        oa_config = self.config.get("openai", {})
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {oa_config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": oa_config.get("model", "tts-1-hd"),
            "input": text,
            "voice": oa_config.get("voice", "nova"),
            "speed": oa_config.get("speed", 1.05),
            "response_format": "mp3",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def _split_text(text: str, max_chars: int = 4500) -> list[str]:
        """将长文本按句子边界分块"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current = ""
        # 按句号、问号、感叹号分句
        sentences = []
        buf = ""
        for char in text:
            buf += char
            if char in "。！？.!?\n":
                sentences.append(buf)
                buf = ""
        if buf:
            sentences.append(buf)

        for sentence in sentences:
            if len(current) + len(sentence) > max_chars and current:
                chunks.append(current)
                current = sentence
            else:
                current += sentence

        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _merge_audio_bytes(audio_parts: list[bytes]) -> bytes:
        """合并多段 MP3 音频"""
        combined = AudioSegment.empty()
        for part in audio_parts:
            segment = AudioSegment.from_mp3(io.BytesIO(part))
            combined += segment

        buffer = io.BytesIO()
        combined.export(buffer, format="mp3")
        return buffer.getvalue()
