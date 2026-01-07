# app/schemas/system_prompt.py
"""
System Prompt Pydantic Schema
对应任务: T1.1.3
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional


class SystemPromptBase(BaseModel):
    """System Prompt 基础 Schema"""
    prompt_content: str = Field(
        ..., 
        max_length=10000,
        description="System Prompt 内容，建议不少于 100 字符，最大 10000 字符"
    )


class SystemPromptCreate(SystemPromptBase):
    """创建 System Prompt 请求"""
    pass


class SystemPromptUpdate(SystemPromptBase):
    """更新 System Prompt 请求（Demo 版本为单用户场景，移除并发检测）"""
    pass


class SystemPromptResponse(BaseModel):
    """System Prompt 响应"""
    id: int
    prompt_key: str
    prompt_content: str
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

