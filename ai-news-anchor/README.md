# AI News Anchor - 每日自动新闻女主播系统

一个完全自主运行的 AI 新闻女主播系统，每天早上自动产出 ~20 分钟的新闻播报视频。

## 系统架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐
│  新闻采集     │───▶│  脚本生成      │───▶│  语音合成     │───▶│  视频生成      │───▶│  发布分发    │
│  News Fetch  │    │ Script Gen   │    │    TTS       │    │  Video Gen   │    │  Publish   │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └────────────┘
   RSS/API            Claude/GPT        ElevenLabs/        HeyGen/             YouTube/
   NewsAPI            风趣主播风格        Fish Audio         MuseTalk            社交媒体
```

## 技术栈选型

### 1. 新闻采集
- **NewsAPI** / **Google News RSS** / **自定义 RSS 源**
- 多源聚合，去重，按热度排序

### 2. 脚本生成 (LLM)
- **Claude API** (主力) — 风趣、有深度的主播风格
- 自动生成开场白、新闻播报、过渡语、结尾
- 支持中英双语

### 3. 语音合成 (TTS)
- **ElevenLabs** (推荐) — 最自然的女声，支持情感控制
- **Fish Audio** (备选) — 中文效果好，性价比高
- **CosyVoice** (开源备选) — 阿里开源，中文优秀

### 4. 数字人视频生成
- **HeyGen API** (推荐) — 最成熟的数字人平台
- **MuseTalk** (开源备选) — 实时唇形同步
- **Hallo2** (开源备选) — 阿里开源音频驱动肖像动画

### 5. 视频后期合成
- **FFmpeg** + **MoviePy** — 叠加字幕、新闻标题栏、B-roll、转场

### 6. 自动发布
- **YouTube Data API** — 定时上传
- **GitHub Actions** / **Cron** — 调度

## 成本估算 (每日 20 分钟视频)

| 组件 | 方案 | 月成本 (USD) |
|------|------|-------------|
| 新闻 API | NewsAPI Free + RSS | $0 |
| LLM 脚本 | Claude API (~5K tokens/day) | ~$5 |
| TTS | ElevenLabs Scale plan | ~$22-99 |
| 数字人 | HeyGen API (20min/day) | ~$89-299 |
| 云服务器 | GPU (如需本地推理) | ~$0-150 |
| **总计** | | **$116-553/月** |

### 低成本开源方案
| 组件 | 方案 | 月成本 (USD) |
|------|------|-------------|
| TTS | CosyVoice / ChatTTS (自托管) | $0 |
| 数字人 | MuseTalk / Hallo2 (自托管) | $0 |
| GPU 服务器 | RunPod / Vast.ai | ~$50-100 |
| **总计** | | **$55-105/月** |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API keys
cp config/settings.example.yaml config/settings.yaml
# 编辑填入你的 API keys

# 3. 测试运行
python -m pipeline.main --test

# 4. 全量运行
python -m pipeline.main

# 5. 设置定时任务 (每天早上 6:00)
crontab -e
# 0 6 * * * cd /path/to/ai-news-anchor && python -m pipeline.main
```

## 目录结构

```
ai-news-anchor/
├── config/
│   ├── settings.example.yaml   # 配置模板
│   └── settings.yaml           # 实际配置 (gitignored)
├── pipeline/
│   ├── __init__.py
│   ├── main.py                 # 主调度入口
│   ├── news_fetcher.py         # 新闻采集模块
│   ├── script_writer.py        # LLM 脚本生成
│   ├── tts_engine.py           # 语音合成引擎
│   ├── video_generator.py      # 数字人视频生成
│   ├── video_composer.py       # 后期合成
│   └── publisher.py            # 自动发布
├── templates/
│   └── prompt_templates.py     # 主播人设 & 脚本模板
├── assets/                     # 静态资源 (logo, 背景音乐等)
├── output/                     # 输出视频
├── requirements.txt
└── README.md
```
