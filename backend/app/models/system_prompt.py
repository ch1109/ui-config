# app/models/system_prompt.py
"""
System Prompt 数据模型
对应任务: T1.1.1, T1.1.2
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SystemPrompt(Base):
    """System Prompt 配置表"""
    
    __tablename__ = "system_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_key = Column(
        String(50), 
        unique=True, 
        nullable=False, 
        default="global_ui_config",
        comment="配置键名，全局唯一"
    )
    prompt_content = Column(
        Text, 
        nullable=False,
        comment="System Prompt 内容"
    )
    selected_model = Column(
        String(50),
        nullable=False,
        default="glm-4.6v",
        comment="选择的视觉模型: glm-4.6v 或 qwen2.5-vl-7b"
    )
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        onupdate=func.now(),
        comment="更新时间"
    )
    created_by = Column(
        String(100), 
        nullable=True,
        comment="创建者"
    )
    is_active = Column(
        Boolean, 
        default=True,
        comment="是否激活"
    )
    
    def __repr__(self):
        return f"<SystemPrompt(id={self.id}, key={self.prompt_key}, model={self.selected_model})>"

