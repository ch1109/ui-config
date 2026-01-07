# app/models/parse_session.py
"""
解析会话数据模型
对应任务: T2.1.2, T2.1.4
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


class SessionStatus(str, enum.Enum):
    """解析会话状态"""
    PENDING = "pending"         # 等待解析
    PARSING = "parsing"         # 解析中
    CLARIFYING = "clarifying"   # 澄清中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败


class ParseSession(Base):
    """解析会话表"""
    
    __tablename__ = "parse_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        String(36), 
        unique=True, 
        default=lambda: str(uuid.uuid4()),
        comment="会话唯一标识 UUID"
    )
    page_config_id = Column(
        Integer, 
        ForeignKey("page_configs.id"),
        nullable=True,
        comment="关联的页面配置 ID（保存后关联）"
    )
    image_path = Column(
        String(500), 
        nullable=False,
        comment="上传图片路径"
    )
    status = Column(
        String(20), 
        default=SessionStatus.PENDING.value,
        comment="会话状态"
    )
    confidence = Column(
        Numeric(5, 2), 
        default=0,
        comment="当前置信度 (0-100)"
    )
    parse_result = Column(
        JSON,
        comment="解析结果（最终配置快照）"
    )
    current_questions = Column(
        JSON, 
        default=[],
        comment="当前待回答的澄清问题"
    )
    clarify_history = Column(
        JSON, 
        default=[],
        comment="澄清对话历史 (REQ-M3-014: 唯一事实来源)"
    )
    clarify_round = Column(
        Integer,
        default=0,
        comment="当前澄清轮次"
    )
    error_message = Column(
        Text,
        comment="错误信息"
    )
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        comment="创建时间"
    )
    completed_at = Column(
        DateTime(timezone=True),
        comment="完成时间"
    )
    
    def __repr__(self):
        return f"<ParseSession(id={self.id}, session_id={self.session_id}, status={self.status})>"

