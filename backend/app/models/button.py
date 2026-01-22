# app/models/button.py
"""
按钮配置数据模型
用于存储可点击按钮的配置信息，支持多语言
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Button(Base):
    """按钮配置表"""
    
    __tablename__ = "buttons"
    
    id = Column(Integer, primary_key=True, index=True)
    button_id = Column(
        String(100), 
        unique=True, 
        nullable=False,
        index=True,
        comment="按钮唯一标识（英文标识），如 confirm, cancel"
    )
    # 多语言名称，JSON 格式: {"zh-CN": "确认", "en": "Confirm", ...}
    name = Column(
        JSON, 
        nullable=False,
        default={},
        comment="按钮多语言名称"
    )
    # 多语言描述
    description = Column(
        JSON,
        default={},
        comment="按钮多语言描述"
    )
    # 多语言响应信息
    response_info = Column(
        JSON,
        default={},
        comment="按钮响应信息（多语言）"
    )
    # 语音关键词，JSON 数组格式: ["确认", "好的", "confirm"]
    voice_keywords = Column(
        JSON,
        default=[],
        comment="语音关键词列表"
    )
    # 是否为系统预设按钮（预设按钮不可删除）
    is_preset = Column(
        Boolean,
        default=False,
        comment="是否为系统预设按钮"
    )
    # 按钮分类：operation(操作), function(功能), navigation(导航), input_trigger(输入触发), selection(选择)
    category = Column(
        String(50),
        default="operation",
        comment="按钮分类"
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
    
    def __repr__(self):
        return f"<Button(id={self.id}, button_id={self.button_id})>"
    
    def get_display_name(self, lang: str = "zh-CN") -> str:
        """获取指定语言的显示名称"""
        if isinstance(self.name, dict):
            return self.name.get(lang, self.name.get("zh-CN", self.button_id))
        return self.button_id
    
    def to_option_dict(self) -> dict:
        """转换为前端选项格式"""
        zh_name = self.get_display_name("zh-CN")
        return {
            "value": self.button_id,
            "label": f"{zh_name} ({self.button_id})",
            "name": self.name,
            "description": self.description,
            "category": self.category
        }
