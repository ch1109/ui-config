# app/api/v1/system_prompt.py
"""
System Prompt 配置管理 API
对应模块: M1
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.system_prompt import (
    SystemPromptUpdate, 
    SystemPromptResponse,
    SystemPromptStats
)
from app.services.system_prompt_service import SystemPromptService
from app.core.exceptions import ContentTooLongError, SaveFailedError
from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT

router = APIRouter(prefix="/api/v1/system-prompt", tags=["System Prompt"])


@router.get("", response_model=SystemPromptResponse)
async def get_system_prompt(db: AsyncSession = Depends(get_db)):
    """
    获取当前 System Prompt
    
    - 若数据库中存在配置，返回该配置
    - 若不存在，返回默认模板
    
    对应需求: REQ-M1-004
    """
    service = SystemPromptService(db)
    prompt = await service.get_current_prompt()
    
    return SystemPromptResponse(
        id=prompt.id,
        prompt_key=prompt.prompt_key,
        prompt_content=prompt.prompt_content,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        is_active=prompt.is_active,
        char_count=len(prompt.prompt_content)
    )


@router.put("", response_model=SystemPromptResponse)
async def update_system_prompt(
    prompt_data: SystemPromptUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新 System Prompt
    
    - 验证内容最大长度 (<=10000 字符)
    - 持久化存储至数据库
    - 返回更新后的配置
    
    对应需求: REQ-M1-006, REQ-M1-008
    
    注: Demo 版本为单用户场景，不做并发冲突检测
    """
    service = SystemPromptService(db)
    
    # 长度验证 (REQ-M1-008)
    content_length = len(prompt_data.prompt_content)
    if content_length > 10000:
        raise ContentTooLongError(
            max_length=10000,
            current_length=content_length
        )
    
    try:
        updated_prompt = await service.update_prompt(prompt_data.prompt_content)
        return SystemPromptResponse(
            id=updated_prompt.id,
            prompt_key=updated_prompt.prompt_key,
            prompt_content=updated_prompt.prompt_content,
            created_at=updated_prompt.created_at,
            updated_at=updated_prompt.updated_at,
            is_active=updated_prompt.is_active,
            char_count=len(updated_prompt.prompt_content)
        )
    except Exception as e:
        # 对应 REQ-M1-009: 数据库连接失败处理
        raise SaveFailedError()


@router.post("/reset", response_model=SystemPromptResponse)
async def reset_system_prompt(db: AsyncSession = Depends(get_db)):
    """
    恢复默认 System Prompt
    
    对应需求: REQ-M1-007
    """
    service = SystemPromptService(db)
    reset_prompt = await service.reset_to_default()
    
    return SystemPromptResponse(
        id=reset_prompt.id,
        prompt_key=reset_prompt.prompt_key,
        prompt_content=reset_prompt.prompt_content,
        created_at=reset_prompt.created_at,
        updated_at=reset_prompt.updated_at,
        is_active=reset_prompt.is_active,
        char_count=len(reset_prompt.prompt_content)
    )


@router.get("/default", response_model=SystemPromptResponse)
async def get_default_prompt():
    """
    获取默认 System Prompt 模板 (不保存)
    """
    return SystemPromptResponse(
        id=0,
        prompt_key="default",
        prompt_content=DEFAULT_UI_CONFIG_PROMPT,
        created_at=None,
        updated_at=None,
        is_active=True,
        char_count=len(DEFAULT_UI_CONFIG_PROMPT)
    )


@router.get("/stats", response_model=SystemPromptStats)
async def get_prompt_stats(db: AsyncSession = Depends(get_db)):
    """
    获取当前 Prompt 统计信息 (用于前端实时显示)
    
    对应需求: REQ-M1-005
    """
    service = SystemPromptService(db)
    stats = await service.get_stats()
    
    return SystemPromptStats(**stats)

