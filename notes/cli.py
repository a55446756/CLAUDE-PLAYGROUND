#!/usr/bin/env python3
"""CLI interface for note management.

Usage:
    python -m notes.cli add "你的笔记内容"
    python -m notes.cli add "紧急：明天要交报告" --title "报告DDL"
    python -m notes.cli list
    python -m notes.cli list --category idea
    python -m notes.cli search "关键词"
    python -m notes.cli done 3
    python -m notes.cli delete 5
    python -m notes.cli stats
    python -m notes.cli show 1
"""

import argparse
import sys
import json
from notes.manager import NoteManager


CATEGORY_EMOJI = {
    "idea": "💡", "todo": "✅", "learning": "📚", "reflection": "🤔",
    "project": "🚀", "health": "💪", "finance": "💰", "work": "💼",
    "life": "🏠", "question": "❓", "misc": "📝",
}

PRIORITY_EMOJI = {
    "low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴",
}


def format_note(note) -> str:
    cat_emoji = CATEGORY_EMOJI.get(note.category.value, "📝")
    pri_emoji = PRIORITY_EMOJI.get(note.priority.value, "🟡")
    done_mark = "✓" if note.is_done else " "
    tags_str = " ".join(f"#{t}" for t in (note.tags or []))
    created = note.created_at.strftime("%Y-%m-%d %H:%M") if note.created_at else ""

    lines = [
        f"[{done_mark}] #{note.id}  {pri_emoji} {cat_emoji} [{note.category.value}]  {created}",
    ]
    if note.title:
        lines.append(f"    📌 {note.title}")
    lines.append(f"    {note.content}")
    if note.due_date:
        lines.append(f"    📅 截止: {note.due_date.isoformat()}")
    if tags_str:
        lines.append(f"    {tags_str}")
    return "\n".join(lines)


def cmd_add(args):
    mgr = NoteManager()
    tags = args.tags.split(",") if args.tags else None
    note = mgr.add(
        content=args.content,
        title=args.title,
        category=args.category,
        tags=tags,
        priority=args.priority,
        due_date=args.due,
    )
    print(f"✅ 笔记已保存 (ID: {note.id})")
    print(format_note(note))


def cmd_list(args):
    mgr = NoteManager()
    notes = mgr.list_notes(
        category=args.category,
        priority=args.priority,
        include_done=args.all,
        limit=args.limit,
    )
    if not notes:
        print("📭 没有找到笔记")
        return
    print(f"📋 共 {len(notes)} 条笔记:\n")
    for note in notes:
        print(format_note(note))
        print()


def cmd_search(args):
    mgr = NoteManager()
    notes = mgr.search(args.keyword, limit=args.limit)
    if not notes:
        print(f"🔍 没有找到包含 \"{args.keyword}\" 的笔记")
        return
    print(f"🔍 找到 {len(notes)} 条相关笔记:\n")
    for note in notes:
        print(format_note(note))
        print()


def cmd_show(args):
    mgr = NoteManager()
    note = mgr.get(args.id)
    if not note:
        print(f"❌ 笔记 #{args.id} 不存在")
        return
    print(format_note(note))


def cmd_done(args):
    mgr = NoteManager()
    note = mgr.done(args.id)
    if not note:
        print(f"❌ 笔记 #{args.id} 不存在")
        return
    print(f"✅ 笔记 #{args.id} 已标记完成")


def cmd_delete(args):
    mgr = NoteManager()
    if mgr.delete(args.id):
        print(f"🗑️ 笔记 #{args.id} 已删除")
    else:
        print(f"❌ 笔记 #{args.id} 不存在")


def cmd_update(args):
    mgr = NoteManager()
    tags = args.tags.split(",") if args.tags else None
    note = mgr.update(
        note_id=args.id,
        content=args.content,
        title=args.title,
        category=args.category,
        tags=tags,
        priority=args.priority,
        due_date=args.due,
    )
    if not note:
        print(f"❌ 笔记 #{args.id} 不存在")
        return
    print(f"✅ 笔记 #{args.id} 已更新")
    print(format_note(note))


def cmd_stats(args):
    mgr = NoteManager()
    s = mgr.stats()
    print("📊 笔记统计:\n")
    print(f"  总数: {s['total']}  |  活跃: {s['active']}  |  已完成: {s['done']}")
    if s["by_category"]:
        print("\n  按分类:")
        for cat, count in sorted(s["by_category"].items(), key=lambda x: -x[1]):
            emoji = CATEGORY_EMOJI.get(cat, "📝")
            print(f"    {emoji} {cat}: {count}")
    if s["by_priority"]:
        print("\n  按优先级:")
        for pri, count in sorted(s["by_priority"].items()):
            emoji = PRIORITY_EMOJI.get(pri, "🟡")
            print(f"    {emoji} {pri}: {count}")


def cmd_export(args):
    mgr = NoteManager()
    notes = mgr.list_notes(include_done=True, limit=9999)
    data = [n.to_dict() for n in notes]
    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"📤 已导出 {len(data)} 条笔记到 {args.output}")
    else:
        print(output)


def cmd_ics(args):
    from notes.ics import generate_ics
    mgr = NoteManager()
    include_done = args.all
    notes = mgr.list_notes(include_done=include_done, limit=9999)
    # Filter: only notes with due_date, or todo/work categories
    cal_notes = [n for n in notes if n.due_date or n.category.value in ("todo", "work")]
    ics_content = generate_ics(cal_notes)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(ics_content)
        print(f"📅 已导出 {len(cal_notes)} 条日历事件到 {args.output}")
    else:
        print(ics_content)


def cmd_serve(args):
    from notes.server import run_server
    run_server(host=args.host, port=args.port)


def main():
    parser = argparse.ArgumentParser(description="📝 笔记管理系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # add
    p_add = subparsers.add_parser("add", help="添加新笔记")
    p_add.add_argument("content", help="笔记内容")
    p_add.add_argument("--title", "-t", help="标题（可选）")
    p_add.add_argument("--category", "-c", help="分类（自动检测）",
                       choices=["idea", "todo", "learning", "reflection", "project",
                                "health", "finance", "work", "life", "question", "misc"])
    p_add.add_argument("--tags", help="标签，逗号分隔")
    p_add.add_argument("--priority", "-p", help="优先级（自动检测）",
                       choices=["low", "medium", "high", "urgent"])
    p_add.add_argument("--due", "-d", help="截止日期 (YYYY-MM-DD)，也可在内容中自然描述")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = subparsers.add_parser("list", help="列出笔记")
    p_list.add_argument("--category", "-c", help="按分类筛选")
    p_list.add_argument("--priority", "-p", help="按优先级筛选")
    p_list.add_argument("--all", "-a", action="store_true", help="包含已完成")
    p_list.add_argument("--limit", "-l", type=int, default=50, help="最大条数")
    p_list.set_defaults(func=cmd_list)

    # search
    p_search = subparsers.add_parser("search", help="搜索笔记")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--limit", "-l", type=int, default=20)
    p_search.set_defaults(func=cmd_search)

    # show
    p_show = subparsers.add_parser("show", help="查看笔记详情")
    p_show.add_argument("id", type=int, help="笔记ID")
    p_show.set_defaults(func=cmd_show)

    # done
    p_done = subparsers.add_parser("done", help="标记为已完成")
    p_done.add_argument("id", type=int, help="笔记ID")
    p_done.set_defaults(func=cmd_done)

    # delete
    p_del = subparsers.add_parser("delete", help="删除笔记")
    p_del.add_argument("id", type=int, help="笔记ID")
    p_del.set_defaults(func=cmd_delete)

    # update
    p_upd = subparsers.add_parser("update", help="更新笔记")
    p_upd.add_argument("id", type=int, help="笔记ID")
    p_upd.add_argument("--content", help="新内容")
    p_upd.add_argument("--title", "-t", help="新标题")
    p_upd.add_argument("--category", "-c", help="新分类")
    p_upd.add_argument("--tags", help="新标签")
    p_upd.add_argument("--priority", "-p", help="新优先级")
    p_upd.add_argument("--due", "-d", help="新截止日期 (YYYY-MM-DD)")
    p_upd.set_defaults(func=cmd_update)

    # stats
    p_stats = subparsers.add_parser("stats", help="查看统计")
    p_stats.set_defaults(func=cmd_stats)

    # export
    p_export = subparsers.add_parser("export", help="导出所有笔记为JSON")
    p_export.add_argument("--output", "-o", help="输出文件路径")
    p_export.set_defaults(func=cmd_export)

    # ics
    p_ics = subparsers.add_parser("ics", help="导出为ICS日历文件")
    p_ics.add_argument("--output", "-o", help="输出文件路径 (默认输出到终端)")
    p_ics.add_argument("--all", "-a", action="store_true", help="包含已完成")
    p_ics.set_defaults(func=cmd_ics)

    # serve
    p_serve = subparsers.add_parser("serve", help="启动HTTP服务器提供日历订阅")
    p_serve.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    p_serve.add_argument("--port", type=int, default=8080, help="端口 (默认: 8080)")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
