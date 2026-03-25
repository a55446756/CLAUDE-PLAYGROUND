"""数字人视频生成模块 — 支持 HeyGen API 和开源方案"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class VideoGenerator:
    """数字人视频生成器"""

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("provider", "heygen")

    async def generate(
        self, audio_path: str | Path, output_path: str | Path
    ) -> dict[str, Any]:
        """根据音频生成数字人视频

        Args:
            audio_path: 音频文件路径
            output_path: 输出视频路径

        Returns:
            {"path": str, "duration_seconds": float}
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.provider == "heygen":
            return await self._heygen_generate(audio_path, output_path)
        elif self.provider == "musetalk":
            return await self._musetalk_generate(audio_path, output_path)
        elif self.provider == "hallo2":
            return await self._hallo2_generate(audio_path, output_path)
        else:
            raise ValueError(f"Unsupported video provider: {self.provider}")

    async def generate_segments(
        self, audio_segments: list[dict], output_dir: str | Path
    ) -> list[dict]:
        """为每个音频段生成对应的视频"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for seg in audio_segments:
            audio_path = seg["path"]
            tag = seg.get("tag", "segment")
            idx = seg.get("segment_index", 0)
            output_path = output_dir / f"{idx:02d}_{tag}.mp4"

            logger.info(f"Generating video for segment {tag}...")
            result = await self.generate(audio_path, output_path)
            result["tag"] = tag
            result["segment_index"] = idx
            results.append(result)

        return results

    async def _heygen_generate(
        self, audio_path: str | Path, output_path: Path
    ) -> dict:
        """使用 HeyGen API 生成数字人视频"""
        hg_config = self.config.get("heygen", {})
        api_key = self.config["api_key"]
        base_url = "https://api.heygen.com"

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=300) as client:
            # Step 1: 上传音频
            logger.info("Uploading audio to HeyGen...")
            audio_bytes = Path(audio_path).read_bytes()
            upload_resp = await client.post(
                f"{base_url}/v1/asset",
                headers={"X-Api-Key": api_key},
                files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            )
            upload_resp.raise_for_status()
            audio_asset_id = upload_resp.json()["data"]["asset_id"]

            # Step 2: 创建视频任务
            logger.info("Creating video generation task...")
            payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": hg_config.get("avatar_id"),
                            "avatar_style": "normal",
                        },
                        "voice": {
                            "type": "audio",
                            "audio_asset_id": audio_asset_id,
                        },
                        "background": {
                            "type": "color",
                            "value": hg_config.get(
                                "background", "#1a1a2e"
                            ),
                        },
                    }
                ],
                "dimension": {"width": 1920, "height": 1080},
            }

            create_resp = await client.post(
                f"{base_url}/v2/video/generate",
                headers=headers,
                json=payload,
            )
            create_resp.raise_for_status()
            video_id = create_resp.json()["data"]["video_id"]

            # Step 3: 轮询等待完成
            logger.info(f"Waiting for video {video_id}...")
            video_url = await self._poll_heygen_status(
                client, base_url, headers, video_id
            )

            # Step 4: 下载视频
            logger.info("Downloading generated video...")
            video_resp = await client.get(video_url)
            output_path.write_bytes(video_resp.content)

        return {"path": str(output_path), "video_id": video_id}

    async def _poll_heygen_status(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
        video_id: str,
        timeout: int = 600,
    ) -> str:
        """轮询 HeyGen 视频生成状态"""
        start = time.time()
        while time.time() - start < timeout:
            resp = await client.get(
                f"{base_url}/v1/video_status.get",
                headers=headers,
                params={"video_id": video_id},
            )
            data = resp.json()["data"]
            status = data.get("status")

            if status == "completed":
                return data["video_url"]
            elif status == "failed":
                raise RuntimeError(
                    f"HeyGen video generation failed: {data.get('error')}"
                )

            logger.info(f"  Status: {status}, waiting...")
            await asyncio.sleep(15)

        raise TimeoutError(
            f"HeyGen video generation timed out after {timeout}s"
        )

    async def _musetalk_generate(
        self, audio_path: str | Path, output_path: Path
    ) -> dict:
        """使用 MuseTalk (开源) 生成唇形同步视频

        需要本地 GPU 环境和预装 MuseTalk。
        这里提供命令行调用的封装。
        """
        mt_config = self.config.get("musetalk", {})
        ref_image = mt_config.get("reference_image")
        model_path = mt_config.get("model_path", "./models/musetalk")

        import subprocess

        cmd = [
            "python",
            "-m",
            "musetalk.inference",
            "--audio_path",
            str(audio_path),
            "--image_path",
            str(ref_image),
            "--result_dir",
            str(output_path.parent),
            "--output_name",
            output_path.name,
            "--model_dir",
            model_path,
        ]

        logger.info(f"Running MuseTalk: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"MuseTalk failed: {stderr.decode()}")

        return {"path": str(output_path)}

    async def _hallo2_generate(
        self, audio_path: str | Path, output_path: Path
    ) -> dict:
        """使用 Hallo2 (开源) 生成音频驱动人像动画

        需要本地 GPU 环境和预装 Hallo2。
        """
        h2_config = self.config.get("hallo2", {})
        ref_image = h2_config.get("reference_image")

        import subprocess

        cmd = [
            "python",
            "scripts/inference.py",
            "--source_image",
            str(ref_image),
            "--driving_audio",
            str(audio_path),
            "--output",
            str(output_path),
        ]

        logger.info(f"Running Hallo2: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=h2_config.get("model_path", "./models/hallo2"),
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Hallo2 failed: {stderr.decode()}")

        return {"path": str(output_path)}
