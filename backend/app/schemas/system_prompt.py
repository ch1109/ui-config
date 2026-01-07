# app/schemas/system_prompt.py
"""
System Prompt Pydantic Schema
对应任务: T1.1.3
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal, List


# 支持的视觉模型列表
SUPPORTED_MODELS = ["glm-4.6v", "qwen2.5-vl-7b"]


class ModelOption(BaseModel):
    """模型选项"""
    id: str
    name: str
    description: str
    provider: str


class SystemPromptBase(BaseModel):
    """System Prompt 基础 Schema"""
    prompt_content: str = Field(
        ..., 
        max_length=10000,
        description="System Prompt 内容，建议不少于 100 字符，最大 10000 字符"
    )


class SystemPromptCreate(SystemPromptBase):
    """创建 System Prompt 请求"""
    selected_model: str = Field(
        default="glm-4.6v",
        description="选择的视觉模型"
    )


class SystemPromptUpdate(BaseModel):
    """更新 System Prompt 请求（Demo 版本为单用户场景，移除并发检测）"""
    prompt_content: Optional[str] = Field(
        None, 
        max_length=10000,
        description="System Prompt 内容"
    )
    selected_model: Optional[str] = Field(
        None,
        description="选择的视觉模型: glm-4.6v 或 qwen2.5-vl-7b"
    )
    
    @field_validator('selected_model')
    @classmethod
    def validate_model(cls, v):
        if v is not None and v not in SUPPORTED_MODELS:
            raise ValueError(f"不支持的模型: {v}，支持的模型: {SUPPORTED_MODELS}")
        return v


class SystemPromptResponse(BaseModel):
    """System Prompt 响应"""
    id: int
    prompt_key: str
    prompt_content: str
    selected_model: str = Field(default="glm-4.6v", description="选择的视觉模型")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True
    char_count: int = Field(description="当前字符数")
    
    model_config = {"from_attributes": True}
    
    @field_validator('char_count', mode='before')
    @classmethod
    def calc_char_count(cls, v, info):
        if v is not None:
            return v
        prompt_content = info.data.get('prompt_content', '')
        return len(prompt_content) if prompt_content else 0


class SystemPromptStats(BaseModel):
    """System Prompt 统计信息 (REQ-M1-005)"""
    current_length: int
    max_length: int = 10000
    recommended_min_length: int = 100
    is_below_recommended: bool = False
    is_valid: bool = True


class AvailableModelsResponse(BaseModel):
    """可用模型列表响应"""
    models: List[ModelOption]
    current_model: str

