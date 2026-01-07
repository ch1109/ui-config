# app/services/system_prompt_service.py
"""
System Prompt 业务逻辑服务
对应任务: T1.1.5
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system_prompt import SystemPrompt
from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT
from datetime import datetime
from typing import Optional


class SystemPromptService:
    """System Prompt 服务"""
    
    PROMPT_KEY = "global_ui_config"
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_current_prompt(self) -> SystemPrompt:
        """
        获取当前配置，不存在则创建默认配置
        对应需求: REQ-M1-004
        """
        result = await self.db.execute(
            select(SystemPrompt).where(
                SystemPrompt.prompt_key == self.PROMPT_KEY,
                SystemPrompt.is_active == True
            )
        )
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            # 创建默认配置
            prompt = SystemPrompt(
                prompt_key=self.PROMPT_KEY,
                prompt_content=DEFAULT_UI_CONFIG_PROMPT
            )
            self.db.add(prompt)
            await self.db.commit()
            await self.db.refresh(prompt)
        
        return prompt
    
    async def update_prompt(self, content: str) -> SystemPrompt:
        """
        更新 System Prompt (Demo 版本，单用户场景)
        对应需求: REQ-M1-006
        """
        prompt = await self.get_current_prompt()
        prompt.prompt_content = content
        prompt.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(prompt)
        return prompt
    
    async def reset_to_default(self) -> SystemPrompt:
        """
        恢复为默认 Prompt
        对应需求: REQ-M1-007
        """
        return await self.update_prompt(DEFAULT_UI_CONFIG_PROMPT)
    
    async def get_stats(self) -> dict:
        """
        获取 Prompt 统计信息
        对应需求: REQ-M1-005
        """
        prompt = await self.get_current_prompt()
        current_length = len(prompt.prompt_content)
        
        return {
            "current_length": current_length,
            "max_length": 10000,
            "recommended_min_length": 100,
            "is_below_recommended": current_length < 100,
            "is_valid": current_length <= 10000
        }

