"""新闻采集模块 — 从多个源获取并聚合新闻"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)


class NewsFetcher:
    """多源新闻聚合器"""

    def __init__(self, config: dict):
        self.config = config
        self.seen_hashes: set[str] = set()

    async def fetch_all(self) -> list[dict[str, Any]]:
        """从所有配置的源获取新闻"""
        all_stories = []

        for source in self.config.get("sources", []):
            try:
                if source["type"] == "newsapi":
                    stories = await self._fetch_newsapi(source)
                elif source["type"] == "rss":
                    stories = await self._fetch_rss(source)
                else:
                    logger.warning(f"Unknown source type: {source['type']}")
                    continue
                all_stories.extend(stories)
            except Exception as e:
                logger.error(f"Failed to fetch from {source['type']}: {e}")

        # 去重
        unique = self._deduplicate(all_stories)

        # 按时间排序，取 top N
        unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        max_stories = self.config.get("max_stories", 8)
        return unique[:max_stories]

    async def _fetch_newsapi(self, source: dict) -> list[dict]:
        """从 NewsAPI 获取新闻"""
        api_key = source["api_key"]
        params = {
            "apiKey": api_key,
            "country": source.get("country", "us"),
            "category": source.get("category", "general"),
            "pageSize": source.get("page_size", 20),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://newsapi.org/v2/top-headlines", params=params
            )
            resp.raise_for_status()
            data = resp.json()

        stories = []
        for article in data.get("articles", []):
            stories.append(
                {
                    "title": article.get("title", ""),
                    "summary": article.get("description", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                    "image_url": article.get("urlToImage", ""),
                }
            )
        return stories

    async def _fetch_rss(self, source: dict) -> list[dict]:
        """从 RSS 源获取新闻"""
        stories = []
        for url in source.get("urls", []):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    feed = feedparser.parse(resp.text)

                for entry in feed.entries[:10]:
                    pub_date = ""
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = datetime(
                            *entry.published_parsed[:6]
                        ).isoformat()

                    stories.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "source": feed.feed.get("title", url),
                            "url": entry.get("link", ""),
                            "published_at": pub_date,
                            "image_url": "",
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to fetch RSS {url}: {e}")

        return stories

    def _deduplicate(self, stories: list[dict]) -> list[dict]:
        """基于标题 hash 去重"""
        unique = []
        for story in stories:
            title_hash = hashlib.md5(
                story["title"].encode("utf-8")
            ).hexdigest()
            if title_hash not in self.seen_hashes:
                self.seen_hashes.add(title_hash)
                unique.append(story)
        return unique

    @staticmethod
    def filter_recent(stories: list[dict], hours: int = 24) -> list[dict]:
        """只保留最近 N 小时内的新闻"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = []
        for story in stories:
            try:
                pub = datetime.fromisoformat(
                    story["published_at"].replace("Z", "+00:00")
                )
                if pub.replace(tzinfo=None) > cutoff:
                    filtered.append(story)
            except (ValueError, KeyError):
                filtered.append(story)  # 无法解析时间的也保留
        return filtered
