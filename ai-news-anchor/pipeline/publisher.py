"""自动发布模块 — 上传视频到 YouTube 和其他平台"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Publisher:
    """视频发布器"""

    def __init__(self, config: dict):
        self.config = config

    async def publish(
        self,
        video_path: str | Path,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """发布视频到所有启用的平台"""
        results = {}

        # YouTube
        yt_config = self.config.get("youtube", {})
        if yt_config.get("enabled", False):
            results["youtube"] = await self._publish_youtube(
                video_path, metadata, yt_config
            )

        # 本地保存
        local_config = self.config.get("local", {})
        if local_config.get("enabled", True):
            results["local"] = await self._save_local(
                video_path, metadata, local_config
            )

        return results

    async def _publish_youtube(
        self,
        video_path: str | Path,
        metadata: dict,
        yt_config: dict,
    ) -> dict:
        """上传视频到 YouTube

        使用 Google API Client 和 OAuth2 认证
        """
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            logger.error(
                "google-api-python-client not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
            return {"error": "Missing YouTube API dependencies"}

        credentials_file = yt_config.get("credentials_file")
        creds = Credentials.from_authorized_user_file(credentials_file)
        youtube = build("youtube", "v3", credentials=creds)

        date_str = datetime.now().strftime("%Y-%m-%d")
        headline = metadata.get("headline", "今日要闻")

        title = yt_config.get("title_template", "AI早报 {date} | {headline}").format(
            date=date_str, headline=headline
        )
        description = yt_config.get("description_template", "AI 新闻播报").format(
            date=date_str, headline=headline
        )

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["AI新闻", "每日播报", "AI主播", "新闻"],
                "categoryId": "25",  # News & Politics
            },
            "status": {
                "privacyStatus": yt_config.get("privacy", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path), mimetype="video/mp4", resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        logger.info(f"Uploading to YouTube: {title}")
        response = request.execute()
        video_id = response["id"]
        url = f"https://youtube.com/watch?v={video_id}"

        logger.info(f"YouTube upload complete: {url}")
        return {"video_id": video_id, "url": url}

    async def _save_local(
        self,
        video_path: str | Path,
        metadata: dict,
        local_config: dict,
    ) -> dict:
        """保存到本地目录"""
        import shutil

        output_dir = Path(local_config.get("output_dir", "./output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = output_dir / f"news_{date_str}.mp4"

        shutil.copy2(str(video_path), str(dest))
        logger.info(f"Saved locally: {dest}")

        return {"path": str(dest)}
