"""Note manager — add, search, list, categorize notes."""

import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from notes.db import SessionLocal, init_db
from notes.models import Note, Category, Priority

# 关键词到分类的映射（中英文）
CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.TODO: [
        "要做", "待办", "记得", "别忘", "提醒", "deadline", "todo", "需要",
        "买", "还", "交", "预约", "报名",
    ],
    Category.IDEA: [
        "灵感", "想法", "点子", "如果", "也许可以", "idea", "突然想到",
        "有个想法", "创意", "可以试试",
    ],
    Category.LEARNING: [
        "学到", "知识", "原来", "笔记", "学习", "教程", "learn", "原理",
        "概念", "技术", "框架", "算法", "读书",
    ],
    Category.REFLECTION: [
        "反思", "感悟", "感觉", "心得", "总结", "回顾", "思考",
        "意识到", "明白了", "体会",
    ],
    Category.PROJECT: [
        "项目", "开发", "功能", "bug", "feature", "deploy", "上线",
        "版本", "迭代", "需求", "设计", "架构",
    ],
    Category.HEALTH: [
        "健身", "运动", "跑步", "饮食", "睡眠", "体重", "健康",
        "锻炼", "医院", "吃药", "身体",
    ],
    Category.FINANCE: [
        "钱", "工资", "投资", "理财", "股票", "基金", "花了", "省",
        "预算", "账单", "报销", "收入", "支出",
    ],
    Category.WORK: [
        "工作", "会议", "老板", "同事", "加班", "汇报", "项目",
        "面试", "升职", "绩效", "方案", "客户",
    ],
    Category.LIFE: [
        "生活", "吃饭", "旅行", "朋友", "家人", "周末", "电影",
        "音乐", "逛街", "搬家", "装修",
    ],
    Category.QUESTION: [
        "为什么", "怎么", "如何", "什么是", "?", "？", "不懂",
        "研究", "调查", "了解一下",
    ],
}


def auto_categorize(text: str) -> Category:
    """Automatically categorize a note based on keyword matching."""
    text_lower = text.lower()
    scores: dict[Category, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return Category.MISC


def auto_extract_tags(text: str) -> list[str]:
    """Extract hashtag-style tags from text."""
    tags = re.findall(r"#(\w+)", text)
    return list(set(tags))


def auto_detect_priority(text: str) -> Priority:
    """Detect priority from text cues."""
    text_lower = text.lower()
    urgent_words = ["紧急", "马上", "立刻", "urgent", "asap", "今天必须", "ddl"]
    high_words = ["重要", "尽快", "优先", "important", "high priority"]
    low_words = ["随便", "有空再", "不急", "low priority", "sometime"]
    if any(w in text_lower for w in urgent_words):
        return Priority.URGENT
    if any(w in text_lower for w in high_words):
        return Priority.HIGH
    if any(w in text_lower for w in low_words):
        return Priority.LOW
    return Priority.MEDIUM


class NoteManager:
    def __init__(self):
        init_db()

    def _get_session(self) -> Session:
        return SessionLocal()

    def add(
        self,
        content: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        priority: Optional[str] = None,
    ) -> Note:
        """Add a new note with auto-categorization."""
        session = self._get_session()
        try:
            detected_category = Category(category) if category else auto_categorize(content)
            detected_priority = Priority(priority) if priority else auto_detect_priority(content)
            extracted_tags = auto_extract_tags(content)
            all_tags = list(set((tags or []) + extracted_tags))

            note = Note(
                content=content,
                title=title,
                category=detected_category,
                tags=all_tags,
                priority=detected_priority,
            )
            session.add(note)
            session.commit()
            session.refresh(note)
            return note
        finally:
            session.close()

    def list_notes(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        priority: Optional[str] = None,
        include_done: bool = False,
        limit: int = 50,
    ) -> list[Note]:
        """List notes with optional filters."""
        session = self._get_session()
        try:
            query = session.query(Note)
            if not include_done:
                query = query.filter(Note.is_done == False)  # noqa: E712
            if category:
                query = query.filter(Note.category == Category(category))
            if priority:
                query = query.filter(Note.priority == Priority(priority))
            if tag:
                query = query.filter(Note.tags.contains(tag))
            return query.order_by(Note.created_at.desc()).limit(limit).all()
        finally:
            session.close()

    def search(self, keyword: str, limit: int = 20) -> list[Note]:
        """Full-text search in content and title."""
        session = self._get_session()
        try:
            pattern = f"%{keyword}%"
            return (
                session.query(Note)
                .filter((Note.content.like(pattern)) | (Note.title.like(pattern)))
                .order_by(Note.created_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def get(self, note_id: int) -> Optional[Note]:
        """Get a note by ID."""
        session = self._get_session()
        try:
            return session.query(Note).filter(Note.id == note_id).first()
        finally:
            session.close()

    def update(
        self,
        note_id: int,
        content: Optional[str] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        priority: Optional[str] = None,
        is_done: Optional[bool] = None,
    ) -> Optional[Note]:
        """Update an existing note."""
        session = self._get_session()
        try:
            note = session.query(Note).filter(Note.id == note_id).first()
            if not note:
                return None
            if content is not None:
                note.content = content
            if title is not None:
                note.title = title
            if category is not None:
                note.category = Category(category)
            if tags is not None:
                note.tags = tags
            if priority is not None:
                note.priority = Priority(priority)
            if is_done is not None:
                note.is_done = is_done
            note.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(note)
            return note
        finally:
            session.close()

    def done(self, note_id: int) -> Optional[Note]:
        """Mark a note as done."""
        return self.update(note_id, is_done=True)

    def delete(self, note_id: int) -> bool:
        """Delete a note."""
        session = self._get_session()
        try:
            note = session.query(Note).filter(Note.id == note_id).first()
            if not note:
                return False
            session.delete(note)
            session.commit()
            return True
        finally:
            session.close()

    def stats(self) -> dict:
        """Get statistics about all notes."""
        session = self._get_session()
        try:
            total = session.query(Note).count()
            done = session.query(Note).filter(Note.is_done == True).count()  # noqa: E712
            active = total - done
            by_category = {}
            for cat in Category:
                count = session.query(Note).filter(
                    Note.category == cat, Note.is_done == False  # noqa: E712
                ).count()
                if count > 0:
                    by_category[cat.value] = count
            by_priority = {}
            for pri in Priority:
                count = session.query(Note).filter(
                    Note.priority == pri, Note.is_done == False  # noqa: E712
                ).count()
                if count > 0:
                    by_priority[pri.value] = count
            return {
                "total": total,
                "active": active,
                "done": done,
                "by_category": by_category,
                "by_priority": by_priority,
            }
        finally:
            session.close()
