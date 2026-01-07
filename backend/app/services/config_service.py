# app/services/config_service.py
"""
配置生成服务
对应模块: M4
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
import jsonschema
from app.models.parse_session import ParseSession
from app.models.page_config import PageConfig


# REQ-M4-001: Schema 定义
UI_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["pages"],
    "properties": {
        "pages": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_\\.]+$": {
                    "type": "object",
                    "required": ["name", "description", "buttonList"],
                    "properties": {
                        "name": {
                            "type": "object",
                            "required": ["zh-CN", "en"],
                            "properties": {
                                "zh-CN": {"type": "string"},
                                "en": {"type": "string"}
                            }
                        },
                        "description": {
                            "type": "object",
                            "required": ["zh-CN", "en"],
                            "properties": {
                                "zh-CN": {"type": "string"},
                                "en": {"type": "string"}
                            }
                        },
                        "buttonList": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1  # REQ-M4-009
                        },
                        "optionalActions": {
                            "type": "array",
                            "items": {"type": "string"}
                            # REQ-M4-010: 允许任意字符串，不做枚举限制
                        }
                    }
                }
            }
        }
    }
}


class ConfigService:
    """配置生成服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_from_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """从解析会话获取配置数据"""
        result = await self.db.execute(
            select(ParseSession).where(ParseSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if session and session.parse_result:
            return session.parse_result
        return None
    
    def build_config(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 UI Config JSON
        对应需求: REQ-M4-003
        """
        page_id = page_data.get("page_id", "unnamed_page")
        
        # 处理名称
        name = page_data.get("name", {})
        if isinstance(name, dict):
            name_zh = name.get("zh-CN") or name.get("zh_CN", "")
            name_en = name.get("en", "")
        else:
            name_zh = str(name)
            name_en = str(name)
        
        # 处理描述
        description = page_data.get("description", {})
        if isinstance(description, dict):
            desc_zh = description.get("zh-CN") or description.get("zh_CN", "")
            desc_en = description.get("en", "")
        else:
            desc_zh = str(description)
            desc_en = str(description)
        
        # 处理 page_name 和 page_description（从 VL 解析结果）
        page_name = page_data.get("page_name", {})
        if page_name:
            name_zh = page_name.get("zh-CN") or name_zh
            name_en = page_name.get("en") or name_en
        
        page_description = page_data.get("page_description", {})
        if page_description:
            desc_zh = page_description.get("zh-CN") or desc_zh
            desc_en = page_description.get("en") or desc_en
        
        config = {
            "pages": {
                page_id: {
                    "name": {
                        "zh-CN": name_zh,
                        "en": name_en
                    },
                    "description": {
                        "zh-CN": desc_zh,
                        "en": desc_en
                    },
                    "buttonList": page_data.get("button_list", []),
                    "optionalActions": page_data.get("optional_actions", [])
                }
            }
        }
        
        return config
    
    def validate_config(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        验证 JSON Config 格式
        对应需求: REQ-M4-004, REQ-M4-007
        
        Returns:
            List[Dict]: 验证错误列表，空列表表示验证通过
        """
        errors = []
        
        try:
            jsonschema.validate(config, UI_CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append({
                "field": ".".join(str(p) for p in e.path) if e.path else "root",
                "message": e.message
            })
        
        # 额外验证: buttonList 非空 (REQ-M4-009)
        if "pages" in config:
            for page_id, page_config in config["pages"].items():
                button_list = page_config.get("buttonList", [])
                if not button_list:
                    errors.append({
                        "field": f"pages.{page_id}.buttonList",
                        "message": "至少保留一个按钮配置"
                    })
                
                # 必填字段验证 (REQ-M4-008)
                name = page_config.get("name", {})
                if not name.get("zh-CN"):
                    errors.append({
                        "field": f"pages.{page_id}.name.zh-CN",
                        "message": "此字段为必填项"
                    })
                if not name.get("en"):
                    errors.append({
                        "field": f"pages.{page_id}.name.en",
                        "message": "此字段为必填项"
                    })
        
        return errors
    
    async def save_page_config(
        self,
        page_data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> PageConfig:
        """保存页面配置到数据库"""
        page_id = page_data.get("page_id", "unnamed_page")
        
        # 检查是否存在
        result = await self.db.execute(
            select(PageConfig).where(PageConfig.page_id == page_id)
        )
        existing = result.scalar_one_or_none()
        
        # 处理名称和描述
        name = page_data.get("name", {})
        description = page_data.get("description", {})
        page_name = page_data.get("page_name", {})
        page_description = page_data.get("page_description", {})
        
        name_zh = name.get("zh-CN") or name.get("zh_CN") or page_name.get("zh-CN", "")
        name_en = name.get("en") or page_name.get("en", "")
        desc_zh = description.get("zh-CN") or description.get("zh_CN") or page_description.get("zh-CN", "")
        desc_en = description.get("en") or page_description.get("en", "")
        
        if existing:
            # 更新
            existing.name_zh = name_zh
            existing.name_en = name_en
            existing.description_zh = desc_zh
            existing.description_en = desc_en
            existing.button_list = page_data.get("button_list", [])
            existing.optional_actions = page_data.get("optional_actions", [])
            existing.ai_context = page_data.get("ai_context")
            existing.status = "configured"
            page = existing
        else:
            # 创建
            page = PageConfig(
                page_id=page_id,
                name_zh=name_zh,
                name_en=name_en,
                description_zh=desc_zh,
                description_en=desc_en,
                button_list=page_data.get("button_list", []),
                optional_actions=page_data.get("optional_actions", []),
                ai_context=page_data.get("ai_context"),
                screenshot_url=page_data.get("screenshot_url"),
                status="configured"
            )
            self.db.add(page)
        
        # 关联解析会话
        if session_id:
            session_result = await self.db.execute(
                select(ParseSession).where(ParseSession.session_id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if session:
                session.page_config_id = page.id
        
        await self.db.commit()
        await self.db.refresh(page)
        
        return page

