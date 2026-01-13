# app/schemas/vl_response.py
"""
VL 模型响应 Schema
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ParsedElement(BaseModel):
    """解析的页面元素"""
    element_id: str
    element_type: str  # button, input, text, link, etc.
    label: str
    inferred_intent: str
    confidence: float = Field(ge=0, le=1)


class VLParseResult(BaseModel):
    """VL 模型解析结果"""
    page_id: Optional[str] = None  # 页面英文标识，如 "4.1face_authorization_page"
    page_name: Dict[str, str]  # {"zh-CN": "...", "en": "..."}
    page_description: Dict[str, str]
    elements: List[ParsedElement] = []
    button_list: List[str] = []
    optional_actions: List[str] = []
    ai_context: Dict[str, str] = {}
    overall_confidence: float = Field(ge=0, le=1)
    clarification_needed: bool = False
    clarification_questions: Optional[List[str]] = None


class ClarifyQuestion(BaseModel):
    """澄清问题"""
    question_id: str
    question_text: str
    context: str
    options: Optional[List[str]] = None  # 可选的快捷选项


class ClarifyResponse(BaseModel):
    """澄清响应"""
    session_id: str
    status: str
    confidence: float
    message: str
    questions: Optional[List[ClarifyQuestion]] = None
    updated_config: Optional[Dict[str, Any]] = None


class ParseStatusResponse(BaseModel):
    """解析状态响应"""
    session_id: str
    status: str
    confidence: float = 0
    result: Optional[Dict[str, Any]] = None
    clarification_questions: Optional[List[ClarifyQuestion]] = None
    error: Optional[str] = None

