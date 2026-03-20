# Claude Code 项目指引

## 笔记管理系统

本项目包含一个基于 SQLite 的笔记管理数据库，位于 `notes/` 目录。

### 当用户想记录笔记时

用户可能会说类似"帮我记一下..."、"我刚想到..."、"记录一下..."这样的话。
请使用以下 CLI 命令帮用户管理笔记：

```bash
# 添加笔记（会自动检测分类和优先级）
python -m notes add "笔记内容"

# 添加带标题的笔记
python -m notes add "详细内容" --title "标题"

# 手动指定分类: idea/todo/learning/reflection/project/health/finance/work/life/question/misc
python -m notes add "内容" --category idea

# 查看所有笔记
python -m notes list

# 按分类查看
python -m notes list --category todo

# 搜索笔记
python -m notes search "关键词"

# 标记完成
python -m notes done <ID>

# 更新笔记
python -m notes update <ID> --content "新内容"

# 删除笔记
python -m notes delete <ID>

# 查看统计
python -m notes stats

# 导出为 JSON
python -m notes export -o backup.json

# 添加带截止日期的笔记（也支持自然语言自动检测：明天、周五、3月25日、下周三等）
python -m notes add "周五之前要交报告" --due 2026-03-27

# 导出为 ICS 日历文件
python -m notes ics -o calendar.ics

# 启动日历订阅 HTTP 服务（Apple Calendar / Google Calendar 可直接订阅）
python -m notes serve --port 8080
# 订阅地址: http://<你的IP>:8080/calendar.ics
```

### 分类说明

| 分类 | 用途 |
|------|------|
| idea | 灵感、点子 |
| todo | 待办事项 |
| learning | 学习笔记、知识点 |
| reflection | 反思、感悟 |
| project | 项目相关 |
| health | 健康、运动 |
| finance | 财务、理财 |
| work | 工作相关 |
| life | 生活琐事 |
| question | 疑问、待研究 |
| misc | 其他 |

### 日历订阅功能

- 笔记中包含截止日期时，会自动生成日历事件
- 支持自然语言日期识别：今天、明天、后天、周五、下周三、3月25日、3天后 等
- `python -m notes ics` 可导出为标准 ICS 文件
- `python -m notes serve` 启动 HTTP 服务器，日历应用可直接订阅
- 高优先级/紧急事项会自动添加提前1小时的提醒

### 使用建议

- 用户只需要用自然语言描述，Claude Code 会自动调用合适的命令
- 系统会自动根据关键词检测分类、优先级和截止日期
- 支持 `#标签` 语法，例如 "学习React的hooks #前端 #React"
- 数据存储在 `notes/notes.db`（SQLite），无需额外配置
