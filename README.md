# 亲声伴 (QinShengBan) — 老人AI陪伴系统

> 让AI成为孩子的声音，让老人随时感受到陪伴

老人只需拨打一个电话号码，AI就会用温暖的声音接听，聊家常、分享子女近况、关心身体健康。子女通过网页门户管理老人设置、录入家庭动态、查看通话记录和AI分析摘要。

---

## 功能概览

### 老人端（零门槛）
- 拨打专属电话号码
- AI以子女身份接听，温暖陪伴
- 自然聊天，AI分享子女的最新动态
- 紧急关键词自动通知家人

### 子女端（网页门户）
- 绑定老人手机号，设置AI个性化称呼
- 录入家庭动态，AI会在通话中自然转述
- 查看每次通话录音和AI生成的摘要
- 情绪趋势图表，实时了解老人状态
- Token充值管理，灵活控制服务时长

---

## 技术栈

| 层级 | 技术 |
|------|------|
| AI 对话 | Claude (claude-sonnet-4-6) |
| 语音通话 | Twilio Voice |
| 后端 API | Python FastAPI |
| 前端门户 | Next.js 14 + Tailwind CSS |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| 录音存储 | 本地文件系统 / AWS S3 |

---

## 快速开始

### 1. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入：
# - ANTHROPIC_API_KEY
# - TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER
# - BASE_URL (Twilio webhook 需要公网地址)
```

### 2. 启动服务

```bash
docker-compose up --build
```

- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/api/docs
- 前端门户：http://localhost:3000

### 3. 配置 Twilio Webhook

在 Twilio 控制台，将电话号码的 Voice URL 设置为：
```
https://your-domain.com/voice/inbound
```

### 4. 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env  # 填入真实配置
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

---

## 项目结构

```
qinshengban/
├── docs/
│   └── product-design.md      # 产品设计文档
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── core/               # 配置、数据库、安全
│   │   ├── models/             # 数据模型
│   │   │   ├── user.py         # 用户/家庭/老人
│   │   │   ├── conversation.py # 通话会话
│   │   │   ├── family_update.py# 家庭动态
│   │   │   └── token.py        # Token/计费
│   │   ├── routes/
│   │   │   ├── auth.py         # 登录/注册
│   │   │   ├── family.py       # 家庭管理
│   │   │   ├── calls.py        # 通话记录
│   │   │   ├── tokens.py       # 充值管理
│   │   │   └── voice_webhook.py# Twilio 语音回调
│   │   └── services/
│   │       ├── ai_service.py   # Claude AI 集成
│   │       ├── voice_service.py# Twilio 语音集成
│   │       ├── notification_service.py # 通知服务
│   │       └── token_service.py# 计费服务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/app/
│       ├── auth/               # 登录/注册页面
│       ├── dashboard/          # 主控制台
│       ├── family/             # 家庭动态管理
│       ├── calls/              # 通话记录查看
│       ├── settings/           # 老人信息设置
│       └── tokens/             # Token充值
├── docker-compose.yml
└── README.md
```

---

## API 文档

启动服务后访问 http://localhost:8000/api/docs 查看完整 Swagger 文档。

### 核心 Endpoints

```
POST /api/auth/register       # 注册并创建家庭组
POST /api/auth/login          # 登录
GET  /api/auth/me             # 获取当前用户信息

GET  /api/family/elderly      # 获取老人档案
PUT  /api/family/elderly      # 更新老人档案
POST /api/family/updates      # 添加家庭动态
GET  /api/family/updates      # 获取家庭动态列表

GET  /api/calls/              # 通话记录列表
GET  /api/calls/{id}          # 通话详情
GET  /api/calls/{id}/transcript  # 完整对话文本
GET  /api/calls/stats/overview   # 统计数据

GET  /api/tokens/balance      # 查看余额
GET  /api/tokens/packages     # 套餐列表
POST /api/tokens/mock-recharge# 测试充值

POST /voice/inbound           # Twilio 入站电话
POST /voice/respond           # AI 对话回复
POST /voice/status            # 通话状态回调
POST /voice/recording         # 录音完成回调
```

---

## 注意事项

- `TWILIO_PHONE_NUMBER` 是老人拨打的电话号码（需在 Twilio 购买）
- `BASE_URL` 必须是 Twilio 可访问的公网地址（本地测试可用 ngrok）
- 本项目使用 SQLite 作为开发数据库，生产环境请切换到 PostgreSQL
- 录音文件默认存储在本地 `./recordings` 目录，生产环境建议使用 S3

---

## 路线图

- [ ] 微信小程序版（子女端）
- [ ] 多语言支持（粤语、闽南语等方言）
- [ ] 语音克隆（用子女真实声音）
- [ ] 智能提醒（老人超过N天未来电自动通知）
- [ ] 健康数据联动（血压/血糖设备接入）
