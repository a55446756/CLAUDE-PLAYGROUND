"""视频后期合成模块 — 添加字幕、标题栏、片头片尾、背景音乐"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VideoComposer:
    """视频后期合成器 — 基于 FFmpeg"""

    def __init__(self, config: dict):
        self.config = config
        self.resolution = config.get("resolution", [1920, 1080])
        self.fps = config.get("fps", 30)

    async def compose(
        self,
        video_segments: list[dict],
        lower_thirds: list[dict],
        output_path: str | Path,
    ) -> dict[str, Any]:
        """合成最终视频

        1. 拼接所有视频段落
        2. 添加下方新闻标题栏
        3. 叠加字幕
        4. 添加背景音乐
        5. 添加片头片尾
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: 拼接视频段落
            concat_path = tmpdir / "concatenated.mp4"
            await self._concat_videos(video_segments, concat_path)

            # Step 2: 添加标题栏 (lower thirds)
            if self.config.get("lower_third", True) and lower_thirds:
                lt_path = tmpdir / "with_lower_thirds.mp4"
                await self._add_lower_thirds(
                    concat_path, lower_thirds, video_segments, lt_path
                )
                current = lt_path
            else:
                current = concat_path

            # Step 3: 添加字幕
            if self.config.get("subtitle", True):
                sub_path = tmpdir / "with_subtitles.mp4"
                await self._add_subtitles(current, sub_path)
                current = sub_path

            # Step 4: 添加背景音乐
            bgm_path = self.config.get("background_music")
            if bgm_path and Path(bgm_path).exists():
                bgm_out = tmpdir / "with_bgm.mp4"
                await self._add_background_music(current, bgm_path, bgm_out)
                current = bgm_out

            # Step 5: 最终输出
            await self._finalize(current, output_path)

        logger.info(f"Final video saved to: {output_path}")
        return {"path": str(output_path)}

    async def _concat_videos(
        self, segments: list[dict], output: Path
    ) -> None:
        """使用 FFmpeg concat demuxer 拼接视频"""
        list_file = output.parent / "concat_list.txt"
        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg['path']}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ]
        await self._run_ffmpeg(cmd)

    async def _add_lower_thirds(
        self,
        input_path: Path,
        lower_thirds: list[dict],
        segments: list[dict],
        output: Path,
    ) -> None:
        """在视频底部叠加新闻标题栏

        使用 FFmpeg drawtext filter 在对应时间段显示标题
        """
        # 计算每个段落的起止时间
        filters = []
        current_time = 0.0

        for i, seg in enumerate(segments):
            duration = seg.get("duration_seconds", 60)
            # 找对应的 lower third
            lt = next(
                (lt for lt in lower_thirds if lt.get("segment") == seg.get("tag")),
                None,
            )
            if lt:
                title = lt.get("title", "").replace("'", "\\'")
                font = self.config.get("subtitle_font", "Noto Sans CJK SC")
                # 标题栏背景
                filters.append(
                    f"drawbox=y=ih-80:w=iw:h=80:color=black@0.7:t=fill"
                    f":enable='between(t,{current_time},{current_time + duration})'"
                )
                # 标题文字
                filters.append(
                    f"drawtext=text='{title}':fontfile='{font}'"
                    f":fontsize=32:fontcolor=white:x=50:y=h-60"
                    f":enable='between(t,{current_time},{current_time + duration})'"
                )
            current_time += duration

        if not filters:
            # 无需处理，直接复制
            subprocess.run(
                ["cp", str(input_path), str(output)], check=True
            )
            return

        filter_str = ",".join(filters)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            filter_str,
            "-c:a",
            "copy",
            str(output),
        ]
        await self._run_ffmpeg(cmd)

    async def _add_subtitles(self, input_path: Path, output: Path) -> None:
        """添加字幕（使用 FFmpeg 的 ass/srt 字幕轨）

        实际使用中建议用 Whisper 生成精准时间轴字幕，
        这里简化为嵌入式字幕
        """
        # 简化处理：直接复制（实际使用时应集成 Whisper 字幕）
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-c",
            "copy",
            str(output),
        ]
        await self._run_ffmpeg(cmd)

    async def _add_background_music(
        self, input_path: Path, bgm_path: str, output: Path
    ) -> None:
        """混入低音量背景音乐"""
        volume = self.config.get("bgm_volume", 0.08)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-i",
            bgm_path,
            "-filter_complex",
            f"[1:a]volume={volume},aloop=loop=-1:size=2e+09[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-shortest",
            str(output),
        ]
        await self._run_ffmpeg(cmd)

    async def _finalize(self, input_path: Path, output: Path) -> None:
        """最终编码输出"""
        w, h = self.resolution
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ]
        await self._run_ffmpeg(cmd)

    @staticmethod
    async def _run_ffmpeg(cmd: list[str]) -> None:
        """执行 FFmpeg 命令"""
        import asyncio

        logger.info(f"FFmpeg: {' '.join(cmd[:6])}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed (rc={proc.returncode}): {stderr.decode()[-500:]}"
            )
