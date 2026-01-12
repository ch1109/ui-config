# app/models/page_config.py
"""
页面配置数据模型
对应任务: T2.1.1, T2.1.3

变更历史:
- 2026-01: ai_context 字段已废弃，行为规则和页面目标现在合并到 description_zh/description_en 中
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    project_id = Column(
        Integer, 
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属项目 ID"
    )
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
        comment="页面中文描述（包含行为规则和页面目标）"
    )
    description_en = Column(
        Text,
        comment="页面英文描述（包含行为规则和页面目标）"
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
    # @deprecated - 此字段已废弃，保留用于向后兼容
    ai_context = Column(
        JSON,
        comment="[已废弃] AI 上下文配置，现已合并到 description 字段"
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
    
    # 关联项目
    project = relationship("Project", back_populates="pages")
    
    def __repr__(self):
        return f"<PageConfig(id={self.id}, page_id={self.page_id})>"
    
    def get_full_description_zh(self) -> str:
        """
        获取完整的中文描述（兼容旧数据）
        如果 ai_context 中有数据，自动合并到描述中
        """
        base_desc = self.description_zh or ""
        
        # 检查旧的 ai_context 数据并合并
        if self.ai_context:
            parts = [base_desc] if base_desc else []
            behavior_rules = self.ai_context.get("behavior_rules", "")
            page_goal = self.ai_context.get("page_goal", "")
            
            if behavior_rules:
                parts.append(f"\n\n## 行为规则\n{behavior_rules}")
            if page_goal:
                parts.append(f"\n\n## 页面目标\n{page_goal}")
            
            return "".join(parts).strip()
        
        return base_desc
    
    def get_full_description_en(self) -> str:
        """
        获取完整的英文描述（兼容旧数据）
        """
        return self.description_en or ""
    
    def to_config_json(self) -> dict:
        """转换为 UI Config JSON 格式"""
        return {
            self.page_id: {
                "name": {
                    "zh-CN": self.name_zh,
                    "en": self.name_en
                },
                "description": {
                    "zh-CN": self.get_full_description_zh(),
                    "en": self.get_full_description_en()
                },
                "buttonList": self.button_list or [],
                "optionalActions": self.optional_actions or []
            }
        }

