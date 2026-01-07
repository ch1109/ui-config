# app/schemas/project.py
"""
项目 Pydantic Schema
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectBase(BaseModel):
    """项目基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(None, max_length=500, description="项目描述")
    color: Optional[str] = Field("#6366f1", max_length=20, description="项目颜色")
    icon: Optional[str] = Field("folder", max_length=50, description="项目图标")


class ProjectCreate(ProjectBase):
    """创建项目请求"""
    pass


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, max_length=20)
    icon: Optional[str] = Field(None, max_length=50)


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: int
    page_count: int = Field(0, description="项目下的页面数量")
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    """项目列表项"""
    id: int
    name: str
    description: Optional[str] = None
    color: str
    icon: str
    page_count: int = 0
    created_at: datetime

