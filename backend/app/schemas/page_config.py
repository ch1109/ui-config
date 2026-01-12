# app/schemas/page_config.py
"""
页面配置 Pydantic Schema

变更历史:
- 2026-01: ai_context 字段已废弃，行为规则和页面目标现在合并到 description 中
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re


class MultiLangText(BaseModel):
    """多语言文本"""
    zh_CN: str = Field(..., alias="zh-CN")
    en: str

    model_config = {"populate_by_name": True}


class AIContext(BaseModel):
    """
    AI 上下文配置
    
    @deprecated 此字段已废弃，行为规则和页面目标现在应合并到 description 字段中。
    保留此类仅用于向后兼容旧数据的读取。
    """
    behavior_rules: Optional[str] = Field(None, description="[已废弃] AI 行为规则，请使用 description 字段")
    page_goal: Optional[str] = Field(None, description="[已废弃] 页面目标，请使用 description 字段")


class PageConfigBase(BaseModel):
    """页面配置基础 Schema"""
    page_id: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="页面唯一标识，英文标识"
    )
    name: MultiLangText
    description: MultiLangText = Field(
        ...,
        description="页面描述（可包含行为规则和页面目标）"
    )
    button_list: List[str] = Field(default=[], min_length=1)
    optional_actions: List[str] = Field(default=[])
    # @deprecated - 保留用于向后兼容，新数据不应使用此字段
    ai_context: Optional[AIContext] = Field(
        None, 
        description="[已废弃] AI 上下文，现已合并到 description 字段"
    )
    
    @field_validator('page_id')
    @classmethod
    def validate_page_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\.]+$', v):
            raise ValueError('page_id 只能包含字母、数字、下划线和点')
        return v
    
    @field_validator('button_list')
    @classmethod
    def validate_button_list(cls, v):
        if len(v) < 1:
            raise ValueError('buttonList 至少包含 1 个按钮 ID (REQ-M4-009)')
        return v


class PageConfigCreate(PageConfigBase):
    """创建页面配置请求"""
    screenshot_url: Optional[str] = None
    project_id: Optional[int] = None


class PageConfigUpdate(BaseModel):
    """更新页面配置请求"""
    name: Optional[MultiLangText] = None
    description: Optional[MultiLangText] = None
    button_list: Optional[List[str]] = None
    optional_actions: Optional[List[str]] = None
    # @deprecated - 保留用于向后兼容
    ai_context: Optional[AIContext] = Field(
        None,
        description="[已废弃] AI 上下文，现已合并到 description 字段"
    )
    screenshot_url: Optional[str] = None
    project_id: Optional[int] = None
    
    @field_validator('button_list')
    @classmethod
    def validate_button_list(cls, v):
        if v is not None and len(v) < 1:
            raise ValueError('buttonList 至少包含 1 个按钮 ID')
        return v


class PageConfigResponse(BaseModel):
    """页面配置响应"""
    id: int
    page_id: str
    name: MultiLangText
    description: MultiLangText
    button_list: List[str]
    optional_actions: List[str]
    # @deprecated - 保留用于向后兼容
    ai_context: Optional[AIContext] = Field(
        None,
        description="[已废弃] 此字段将在未来版本移除"
    )
    screenshot_url: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PageConfigListItem(BaseModel):
    """页面配置列表项"""
    id: int
    page_id: str
    name_zh: str
    status: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    screenshot_url: Optional[str] = None
    updated_at: Optional[datetime] = None

