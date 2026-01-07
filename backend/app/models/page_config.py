# app/models/page_config.py
"""
页面配置数据模型
对应任务: T2.1.1, T2.1.3
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class PageStatus(str, enum.Enum):
    """页面配置状态"""
    DRAFT = "draft"           # 草稿
    CONFIGURED = "configured"  # 已配置
    PENDING = "pending"       # 待确认


class PageConfig(Base):
    """页面配置表"""
    
    __tablename__ = "page_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(
        String(100), 
        unique=True, 
        nullable=False,
        comment="页面唯一标识，英文标识"
    )
    name_zh = Column(
        String(200), 
        nullable=False,
        comment="页面中文名称"
    )
    name_en = Column(
        String(200), 
        nullable=False,
        comment="页面英文名称"
    )
    description_zh = Column(
        Text,
        comment="页面中文描述"
    )
    description_en = Column(
        Text,
        comment="页面英文描述"
    )
    button_list = Column(
        JSON, 
        default=[],
        comment="可点击按钮 ID 列表"
    )
    optional_actions = Column(
        JSON, 
        default=[],
        comment="可选操作列表"
    )
    screenshot_url = Column(
        String(500),
        comment="页面截图 URL"
    )
    ai_context = Column(
        JSON,
        comment="AI 上下文配置 (行为规则、页面目标)"
    )
    status = Column(
        String(20), 
        default=PageStatus.DRAFT.value,
        comment="配置状态"
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
        return f"<PageConfig(id={self.id}, page_id={self.page_id})>"
    
    def to_config_json(self) -> dict:
        """转换为 UI Config JSON 格式"""
        return {
            self.page_id: {
                "name": {
                    "zh-CN": self.name_zh,
                    "en": self.name_en
                },
                "description": {
                    "zh-CN": self.description_zh or "",
                    "en": self.description_en or ""
                },
                "buttonList": self.button_list or [],
                "optionalActions": self.optional_actions or []
            }
        }

