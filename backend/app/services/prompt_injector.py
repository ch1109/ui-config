# app/services/prompt_injector.py
"""
System Prompt 动态注入服务
负责将按钮列表和意图列表动态注入到 System Prompt 中
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.button import Button
from app.core.default_prompts import BUTTON_LIST_PLACEHOLDER, OPTIONAL_ACTIONS_PLACEHOLDER


# 预设意图列表（与前端 ConfigEditor.vue 保持同步）
PRESET_INTENTS = [
    {"id": "knowledge", "name": "知识问答", "description": "回答用户的知识性问题"},
    {"id": "chat", "name": "闲聊模式", "description": "与用户进行日常对话"},
    {"id": "comprehension", "name": "阅读理解", "description": "帮助用户理解协议或文档内容"},
    {"id": "Dir-read-agreement", "name": "朗读协议", "description": "为用户朗读协议内容"},
    {"id": "UpdateFormLossReason", "name": "更新挂失原因", "description": "更新表单中的挂失原因字段"},
    {"id": "UpdateFormCancelAccount", "name": "更新转账表单", "description": "更新转账表单中的收款信息"}
]


class PromptInjector:
    """System Prompt 动态注入器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_button_list_text(self) -> str:
        """
        获取格式化的按钮列表文本
        
        Returns:
            格式化的按钮列表，供 System Prompt 使用
        """
        result = await self.db.execute(
            select(Button).order_by(Button.category, Button.button_id)
        )
        buttons = result.scalars().all()
        
        if not buttons:
            return "（暂无配置的按钮）"
        
        # 按分类组织按钮
        categories = {
            "operation": "操作按钮",
            "function": "功能按钮", 
            "navigation": "导航按钮",
            "input_trigger": "输入触发按钮",
            "selection": "选择按钮"
        }
        
        category_buttons = {}
        for btn in buttons:
            cat = btn.category or "operation"
            if cat not in category_buttons:
                category_buttons[cat] = []
            
            zh_name = btn.name.get("zh-CN", btn.button_id) if isinstance(btn.name, dict) else btn.button_id
            category_buttons[cat].append(f"- `{btn.button_id}`: {zh_name}")
        
        # 生成格式化文本
        lines = []
        for cat_key, cat_name in categories.items():
            if cat_key in category_buttons:
                lines.append(f"\n**{cat_name}**:")
                lines.extend(category_buttons[cat_key])
        
        # 处理未知分类
        for cat_key, btns in category_buttons.items():
            if cat_key not in categories:
                lines.append(f"\n**其他**:")
                lines.extend(btns)
        
        return "\n".join(lines) if lines else "（暂无配置的按钮）"
    
    def get_intent_list_text(self) -> str:
        """
        获取格式化的意图列表文本
        
        Returns:
            格式化的意图列表，供 System Prompt 使用
        """
        if not PRESET_INTENTS:
            return "（暂无配置的意图）"
        
        lines = []
        for intent in PRESET_INTENTS:
            lines.append(f"- `{intent['id']}`: {intent['name']} - {intent['description']}")
        
        return "\n".join(lines)
    
    async def inject_dynamic_content(self, prompt_content: str) -> str:
        """
        将动态内容注入到 System Prompt 中
        
        Args:
            prompt_content: 原始 System Prompt 内容
            
        Returns:
            注入动态内容后的 System Prompt
        """
        # 获取按钮列表
        button_list_text = await self.get_button_list_text()
        
        # 获取意图列表
        intent_list_text = self.get_intent_list_text()
        
        # 替换占位符
        result = prompt_content
        result = result.replace(BUTTON_LIST_PLACEHOLDER, button_list_text)
        result = result.replace(OPTIONAL_ACTIONS_PLACEHOLDER, intent_list_text)
        
        return result
    
    async def get_available_button_ids(self) -> List[str]:
        """
        获取所有可用的按钮 ID 列表
        
        Returns:
            按钮 ID 列表
        """
        result = await self.db.execute(
            select(Button.button_id)
        )
        return [row[0] for row in result.all()]
    
    def get_available_intent_ids(self) -> List[str]:
        """
        获取所有可用的意图 ID 列表
        
        Returns:
            意图 ID 列表
        """
        return [intent["id"] for intent in PRESET_INTENTS]


async def inject_prompt(db: AsyncSession, prompt_content: str) -> str:
    """
    便捷函数：将动态内容注入到 System Prompt 中
    
    Args:
        db: 数据库会话
        prompt_content: 原始 System Prompt 内容
        
    Returns:
        注入动态内容后的 System Prompt
    """
    injector = PromptInjector(db)
    return await injector.inject_dynamic_content(prompt_content)
