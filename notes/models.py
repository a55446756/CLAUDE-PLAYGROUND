"""Note database model."""

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum, Boolean
from sqlalchemy.dialects.sqlite import JSON
from notes.db import Base


class Category(str, enum.Enum):
    IDEA = "idea"               # 灵感、点子
    TODO = "todo"               # 待办事项
    LEARNING = "learning"       # 学习笔记、知识点
    REFLECTION = "reflection"   # 反思、感悟
    PROJECT = "project"         # 项目相关
    HEALTH = "health"           # 健康、运动
    FINANCE = "finance"         # 财务、理财
    WORK = "work"               # 工作相关
    LIFE = "life"               # 生活琐事
    QUESTION = "question"       # 疑问、待研究
    MISC = "misc"               # 其他


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    title = Column(String(200), nullable=True)
    category = Column(Enum(Category), default=Category.MISC, nullable=False)
    tags = Column(JSON, default=list)
    priority = Column(Enum(Priority), default=Priority.MEDIUM, nullable=False)
    due_date = Column(Date, nullable=True)
    is_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Note #{self.id} [{self.category.value}] {self.title or self.content[:30]}>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category.value,
            "tags": self.tags or [],
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_done": self.is_done,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
