# app/schemas/button.py
"""
按钮配置的 Pydantic Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class MultiLangText(BaseModel):
    """多语言文本"""
    zh_CN: str = Field(default="", alias="zh-CN")
    en: str = Field(default="")
    ja: Optional[str] = Field(default="")
    ms: Optional[str] = Field(default="")
    zh_TW: Optional[str] = Field(default="", alias="zh-TW")
    
    class Config:
        populate_by_name = True


class ButtonCreate(BaseModel):
    """创建按钮请求"""
    button_id: str = Field(..., min_length=1, max_length=100, description="按钮唯一标识（英文）")
    name: Dict[str, str] = Field(..., description="多语言名称")
    description: Optional[Dict[str, str]] = Field(default={}, description="多语言描述")
    response_info: Optional[Dict[str, str]] = Field(default={}, description="响应信息")
    voice_keywords: Optional[List[str]] = Field(default=[], description="语音关键词")
    category: Optional[str] = Field(default="operation", description="按钮分类")
    
    class Config:
        json_schema_extra = {
            "example": {
                "button_id": "confirm_payment",
                "name": {"zh-CN": "确认支付", "en": "Confirm Payment"},
                "description": {"zh-CN": "点击确认支付订单", "en": "Click to confirm payment"},
                "response_info": {"zh-CN": "正在处理支付...", "en": "Processing payment..."},
                "voice_keywords": ["确认支付", "支付", "confirm payment"],
                "category": "operation"
            }
        }


class ButtonUpdate(BaseModel):
    """更新按钮请求"""
    name: Optional[Dict[str, str]] = Field(default=None, description="多语言名称")
    description: Optional[Dict[str, str]] = Field(default=None, description="多语言描述")
    response_info: Optional[Dict[str, str]] = Field(default=None, description="响应信息")
    voice_keywords: Optional[List[str]] = Field(default=None, description="语音关键词")
    category: Optional[str] = Field(default=None, description="按钮分类")


class ButtonResponse(BaseModel):
    """按钮响应"""
    id: int
    button_id: str
    name: Dict[str, Any]
    description: Optional[Dict[str, Any]] = {}
    response_info: Optional[Dict[str, Any]] = {}
    voice_keywords: Optional[List[str]] = []
    category: str = "operation"
    is_preset: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ButtonOptionItem(BaseModel):
    """按钮选项（用于下拉列表）"""
    value: str = Field(..., description="按钮 ID")
    label: str = Field(..., description="显示标签")
    name: Dict[str, Any] = Field(default={}, description="多语言名称")
    description: Optional[Dict[str, Any]] = Field(default={}, description="多语言描述")
    category: str = Field(default="operation", description="按钮分类")


class ButtonListResponse(BaseModel):
    """按钮列表响应"""
    success: bool = True
    total: int
    buttons: List[ButtonResponse]
    options: List[ButtonOptionItem] = Field(default=[], description="下拉选项格式")


class UnrecognizedButton(BaseModel):
    """AI 识别到的未注册按钮"""
    suggested_id: str = Field(..., description="建议的按钮 ID")
    suggested_name_zh: str = Field(..., description="建议的中文名称")
    suggested_name_en: Optional[str] = Field(default="", description="建议的英文名称")
    confidence: float = Field(default=0.8, description="识别置信度")
    context: Optional[str] = Field(default="", description="按钮所在的上下文描述")
