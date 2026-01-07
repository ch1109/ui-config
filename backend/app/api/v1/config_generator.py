# app/api/v1/config_generator.py
"""
JSON Config 生成 API
对应模块: M4
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.database import get_db
from app.services.config_service import ConfigService, UI_CONFIG_SCHEMA
import jsonschema

router = APIRouter(prefix="/api/v1/config", tags=["Config Generator"])


class GenerateConfigRequest(BaseModel):
    """生成配置请求"""
    session_id: Optional[str] = None
    page_data: Optional[Dict[str, Any]] = None


class ValidationError(BaseModel):
    """验证错误"""
    field: str
    message: str


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    config: Optional[Dict[str, Any]] = None
    errors: Optional[List[ValidationError]] = None


@router.post("/generate", response_model=ConfigResponse)
async def generate_config(
    request: GenerateConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成 JSON Config
    
    对应需求: REQ-M4-003, REQ-M4-004, REQ-M4-007, REQ-M4-008
    """
    service = ConfigService(db)
    
    # 获取页面数据
    if request.session_id:
        page_data = await service.get_from_session(request.session_id)
    else:
        page_data = request.page_data
    
    if not page_data:
        raise HTTPException(status_code=400, detail="缺少配置数据")
    
    # 构建配置
    config = service.build_config(page_data)
    
    # REQ-M4-004, REQ-M4-007: Schema 验证
    errors = service.validate_config(config)
    
    if errors:
        return ConfigResponse(
            success=False,
            config=config,
            errors=[ValidationError(**e) for e in errors]
        )
    
    return ConfigResponse(
        success=True,
        config=config,
        errors=None
    )


@router.post("/validate")
async def validate_config(config: Dict[str, Any]):
    """
    验证 JSON Config 格式
    
    对应需求: REQ-M4-007
    """
    try:
        jsonschema.validate(config, UI_CONFIG_SCHEMA)
        return {"valid": True, "errors": []}
    except jsonschema.ValidationError as e:
        return {
            "valid": False,
            "errors": [{
                "field": ".".join(str(p) for p in e.path) if e.path else "root",
                "message": e.message
            }]
        }


@router.post("/save")
async def save_config(
    request: GenerateConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    保存页面配置
    
    - 验证配置
    - 保存到数据库
    - 关联解析会话
    """
    service = ConfigService(db)
    
    # 获取页面数据
    page_data = request.page_data
    if request.session_id and not page_data:
        page_data = await service.get_from_session(request.session_id)
    
    if not page_data:
        raise HTTPException(status_code=400, detail="缺少配置数据")
    
    # 验证
    config = service.build_config(page_data)
    errors = service.validate_config(config)
    
    if errors:
        return {
            "success": False,
            "errors": errors
        }
    
    # 保存
    try:
        page = await service.save_page_config(page_data, request.session_id)
        return {
            "success": True,
            "page_id": page.page_id,
            "config": config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/schema")
async def get_config_schema():
    """
    获取 UI Config Schema 定义
    
    用于前端表单验证
    """
    return {
        "schema": UI_CONFIG_SCHEMA,
        "description": "UI Config JSON Schema 定义"
    }

