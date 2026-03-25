"""AI 新闻女主播 — 主调度入口

每日自动运行流程:
1. 采集新闻 → 2. 生成脚本 → 3. 语音合成 → 4. 数字人视频 → 5. 后期合成 → 6. 发布
"""

import argparse
import asyncio
import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.news_fetcher import NewsFetcher
from pipeline.publisher import Publisher
from pipeline.script_writer import ScriptWriter
from pipeline.tts_engine import TTSEngine
from pipeline.video_composer import VideoComposer
from pipeline.video_generator import VideoGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-news-anchor")


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """加载配置文件"""
    path = Path(__file__).resolve().parent.parent / config_path
    if not path.exists():
        logger.error(
            f"Config not found: {path}\n"
            "Please copy config/settings.example.yaml to config/settings.yaml "
            "and fill in your API keys."
        )
        sys.exit(1)

    with open(path) as f:
        return yaml.safe_load(f)


async def run_pipeline(config: dict, test_mode: bool = False) -> None:
    """执行完整的视频生成流水线"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"AI News Anchor Pipeline — {start_time.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)

    with tempfile.TemporaryDirectory(prefix="ai_anchor_") as work_dir:
        work_dir = Path(work_dir)

        # ===== Step 1: 新闻采集 =====
        logger.info("\n📰 Step 1/6: Fetching news...")
        fetcher = NewsFetcher(config["news"])
        news_items = await fetcher.fetch_all()
        news_items = NewsFetcher.filter_recent(news_items, hours=24)
        logger.info(f"  Fetched {len(news_items)} news stories")

        if not news_items:
            logger.error("No news found! Aborting.")
            return

        if test_mode:
            news_items = news_items[:3]
            logger.info(f"  [TEST MODE] Using only {len(news_items)} stories")

        # ===== Step 2: 脚本生成 =====
        logger.info("\n✍️  Step 2/6: Generating script...")
        writer = ScriptWriter(config["llm"])
        script_data = await writer.generate_script(news_items)
        segments = script_data["segments"]
        logger.info(
            f"  Generated {len(segments)} segments, "
            f"~{sum(s['estimated_duration'] for s in segments):.0f}s total"
        )

        # 保存脚本到文件
        script_path = work_dir / "script.txt"
        script_path.write_text(script_data["full_script"], encoding="utf-8")
        logger.info(f"  Script saved to {script_path}")

        # ===== Step 3: TTS 语音合成 =====
        logger.info("\n🎙️  Step 3/6: Synthesizing speech...")
        tts = TTSEngine(config["tts"])
        audio_dir = work_dir / "audio"
        audio_segments = await tts.synthesize_segments(segments, audio_dir)
        total_audio_duration = sum(s["duration_seconds"] for s in audio_segments)
        logger.info(f"  Audio total: {total_audio_duration:.1f}s")

        # ===== Step 4: 数字人视频生成 =====
        logger.info("\n🎬 Step 4/6: Generating avatar video...")
        video_gen = VideoGenerator(config["video"])
        video_dir = work_dir / "video"
        video_segments = await video_gen.generate_segments(
            audio_segments, video_dir
        )
        logger.info(f"  Generated {len(video_segments)} video segments")

        # ===== Step 5: 视频后期合成 =====
        logger.info("\n🎞️  Step 5/6: Composing final video...")
        composer = VideoComposer(config["composition"])
        final_path = work_dir / "final_output.mp4"
        await composer.compose(
            video_segments, script_data["lower_thirds"], final_path
        )
        logger.info(f"  Final video: {final_path}")

        # ===== Step 6: 发布 =====
        logger.info("\n📤 Step 6/6: Publishing...")
        publisher = Publisher(config["publish"])
        headline = (
            news_items[0]["title"] if news_items else "今日要闻"
        )
        results = await publisher.publish(
            final_path, {"headline": headline}
        )
        for platform, result in results.items():
            logger.info(f"  {platform}: {result}")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Pipeline complete! Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="AI News Anchor Pipeline")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: use fewer news stories, shorter output",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as scheduled daemon (daily)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.schedule:
        _run_scheduled(config)
    else:
        asyncio.run(run_pipeline(config, test_mode=args.test))


def _run_scheduled(config: dict) -> None:
    """定时调度模式"""
    import schedule as sched
    import time

    daily_time = config.get("schedule", {}).get("daily_time", "06:00")
    max_retries = config.get("schedule", {}).get("max_retries", 3)

    def job():
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Scheduled run (attempt {attempt}/{max_retries})")
                asyncio.run(run_pipeline(config))
                break
            except Exception as e:
                logger.error(f"Pipeline failed (attempt {attempt}): {e}")
                if attempt == max_retries:
                    logger.error("All retries exhausted!")

    sched.every().day.at(daily_time).do(job)
    logger.info(f"Scheduler started. Will run daily at {daily_time}")

    while True:
        sched.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
