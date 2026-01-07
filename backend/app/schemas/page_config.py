# app/schemas/page_config.py
"""
页面配置 Pydantic Schema
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
    """AI 上下文配置"""
    behavior_rules: Optional[str] = Field(None, description="AI 行为规则")
    page_goal: Optional[str] = Field(None, description="页面目标")


class PageConfigBase(BaseModel):
    """页面配置基础 Schema"""
    page_id: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="页面唯一标识，英文标识"
    )
    name: MultiLangText
    description: MultiLangText
    button_list: List[str] = Field(default=[], min_length=1)
    optional_actions: List[str] = Field(default=[])
    ai_context: Optional[AIContext] = None
    
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
    ai_context: Optional[AIContext] = None
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
    ai_context: Optional[AIContext] = None
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

