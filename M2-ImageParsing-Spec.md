# Spec Coding: M2 - 页面截图智能解析

## 模块概述

| 项目 | 内容 |
|------|------|
| 模块编号 | M2 |
| 模块名称 | 页面截图智能解析 |
| 优先级 | P0 (核心功能) |
| 预估工时 | 5 人天 |
| 模型依赖 | Qwen3-VL-8B-Instruct |

> **Demo 版本说明**：
> - SSRF 防护采用简化方案（基础地址过滤），仅用于可信内网环境
> - 外部 URL 图片解析功能建议仅在开发测试时使用

---

## 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Image Upload │  │  Form View  │  │    AI Assistant     │  │
│  │  Component   │  │  Component  │  │      Panel          │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼───────────────────┼──────────────┘
          │                │                   │
          ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend API Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ /upload     │  │ /parse      │  │ /clarify            │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼───────────────────┼──────────────┘
          │                │                   │
          ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              VLModelService (Qwen3-VL-8B)               ││
│  │  - Image preprocessing                                   ││
│  │  - Semantic parsing                                      ││
│  │  - Multi-turn clarification                              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 文件结构

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── page_config.py        # 页面配置 API
│   │       └── image_upload.py       # 图片上传 API
│   ├── models/
│   │   ├── page_config.py            # 页面配置数据模型
│   │   └── parse_session.py          # 解析会话模型
│   ├── schemas/
│   │   ├── page_config.py            # 页面配置 Schema
│   │   └── vl_response.py            # VL 模型响应 Schema
│   ├── services/
│   │   ├── vl_model_service.py       # VL 模型服务
│   │   ├── image_service.py          # 图片处理服务
│   │   └── parse_service.py          # 解析业务逻辑
│   └── core/
│       └── vl_config.py              # VL 模型配置
├── uploads/                          # 临时上传目录
└── tests/
    └── test_vl_parsing.py
```

### 临时文件清理策略

- 任务方式: 定时任务 (Cron/内置调度器)
- 清理条件: 超过 24 小时且未关联已保存 PageConfig 的截图
- 清理对象: uploads/ 目录中的临时图片
- 对应需求: REQ-M2-020

---

## 数据模型设计

### 数据库表: page_configs

```sql
CREATE TABLE page_configs (
    id SERIAL PRIMARY KEY,
    page_id VARCHAR(100) UNIQUE NOT NULL,
    name_zh VARCHAR(200) NOT NULL,
    name_en VARCHAR(200) NOT NULL,
    description_zh TEXT,
    description_en TEXT,
    button_list JSONB DEFAULT '[]',
    optional_actions JSONB DEFAULT '[]',
    screenshot_url VARCHAR(500),
    ai_context JSONB,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, configured, pending
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_page_configs_status ON page_configs(status);
```

### 数据库表: parse_sessions

```sql
CREATE TABLE parse_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID UNIQUE NOT NULL,
    page_config_id INTEGER REFERENCES page_configs(id),
    image_path VARCHAR(500) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, parsing, clarifying, completed, failed
    confidence DECIMAL(5,2) DEFAULT 0,
    parse_result JSONB,
    current_questions JSONB DEFAULT '[]',
    clarify_history JSONB DEFAULT '[]',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### SQLAlchemy Models

```python
# app/models/page_config.py

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum

class PageStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    PENDING = "pending"

class PageConfig(Base):
    __tablename__ = "page_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(String(100), unique=True, nullable=False)
    name_zh = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=False)
    description_zh = Column(Text)
    description_en = Column(Text)
    button_list = Column(JSON, default=[])
    optional_actions = Column(JSON, default=[])
    screenshot_url = Column(String(500))
    ai_context = Column(JSON)
    status = Column(String(20), default=PageStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

```python
# app/models/parse_session.py

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid

class ParseSession(Base):
    __tablename__ = "parse_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    page_config_id = Column(Integer, ForeignKey("page_configs.id"))
    image_path = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    confidence = Column(Numeric(5, 2), default=0)
    parse_result = Column(JSON)
    current_questions = Column(JSON, default=[])
    clarify_history = Column(JSON, default=[])
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
```

### Pydantic Schemas

```python
# app/schemas/page_config.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MultiLangText(BaseModel):
    zh_CN: str = Field(..., alias="zh-CN")
    en: str

    class Config:
        populate_by_name = True

class AIContext(BaseModel):
    behavior_rules: Optional[str] = Field(None, description="AI 行为规则")
    page_goal: Optional[str] = Field(None, description="页面目标")

class PageConfigBase(BaseModel):
    page_id: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_\.]+$')
    name: MultiLangText
    description: MultiLangText
    button_list: List[str] = Field(default=[])
    optional_actions: List[str] = Field(default=[])
    ai_context: Optional[AIContext] = None

class PageConfigCreate(PageConfigBase):
    screenshot_url: Optional[str] = None

class PageConfigUpdate(BaseModel):
    name: Optional[MultiLangText] = None
    description: Optional[MultiLangText] = None
    button_list: Optional[List[str]] = None
    optional_actions: Optional[List[str]] = None
    ai_context: Optional[AIContext] = None

class PageConfigResponse(PageConfigBase):
    id: int
    screenshot_url: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class PageConfigListItem(BaseModel):
    id: int
    page_id: str
    name_zh: str
    status: str
    screenshot_url: Optional[str]
    updated_at: Optional[datetime]
```

```python
# app/schemas/vl_response.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ParsedElement(BaseModel):
    element_id: str
    element_type: str  # button, input, text, link, etc.
    label: str
    inferred_intent: str
    confidence: float = Field(ge=0, le=1)

class VLParseResult(BaseModel):
    page_name: Dict[str, str]  # {"zh-CN": "...", "en": "..."}
    page_description: Dict[str, str]
    elements: List[ParsedElement]
    button_list: List[str]
    optional_actions: List[str]
    ai_context: Dict[str, str]
    overall_confidence: float = Field(ge=0, le=1)
    clarification_needed: bool
    clarification_questions: Optional[List[str]] = None

class ClarifyQuestion(BaseModel):
    question_id: str
    question_text: str
    context: str
    options: Optional[List[str]] = None  # 可选的快捷选项

class ClarifyResponse(BaseModel):
    session_id: str
    status: str
    confidence: float
    questions: Optional[List[ClarifyQuestion]] = None
    updated_config: Optional[Dict[str, Any]] = None
    message: str
```

---

## API 接口设计

### 接口列表

| 方法 | 路径 | 描述 | 对应需求 |
|------|------|------|----------|
| POST | /api/v1/pages/upload-image | 上传页面截图 | REQ-M2-005, REQ-M2-006 |
| POST | /api/v1/pages/parse | 触发 AI 解析 | REQ-M2-007, REQ-M2-008 |
| GET | /api/v1/pages/parse/{session_id}/status | 获取解析状态 | REQ-M2-009 |
| POST | /api/v1/pages | 保存页面配置 | - |
| GET | /api/v1/pages | 获取页面列表 | - |
| GET | /api/v1/pages/{page_id} | 获取单个页面配置 | - |

### 请求/响应结构示例

#### POST /api/v1/pages/upload-image

请求：`multipart/form-data`

响应：
```json
{
  "success": true,
  "file_url": "/uploads/xxx.png",
  "filename": "xxx.png",
  "size_bytes": 123456
}
```

#### POST /api/v1/pages/parse

请求：
```json
{
  "image_url": "https://example.com/page.png"
}
```

响应：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "pending",
  "message": "AI 正在分析页面...",
  "estimated_time_seconds": 30
}
```

#### GET /api/v1/pages/parse/{session_id}/status

响应（解析中）：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "parsing",
  "confidence": 0
}
```

响应（澄清中）：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "clarifying",
  "confidence": 0.72,
  "result": {
    "page_name": {"zh-CN": "测试页", "en": "Test Page"},
    "page_description": {"zh-CN": "说明", "en": "Desc"},
    "elements": [],
    "button_list": ["btn_1"],
    "optional_actions": [],
    "ai_context": {},
    "overall_confidence": 0.72,
    "clarification_needed": true
  },
  "clarification_questions": [
    {
      "question_id": "q1",
      "question_text": "确认按钮用途？",
      "context": "button_list",
      "options": ["提交", "下一步"]
    }
  ]
}
```

响应（完成）：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "completed",
  "confidence": 0.91,
  "result": {
    "page_name": {"zh-CN": "测试页", "en": "Test Page"},
    "page_description": {"zh-CN": "说明", "en": "Desc"},
    "elements": [],
    "button_list": ["btn_1"],
    "optional_actions": [],
    "ai_context": {},
    "overall_confidence": 0.91,
    "clarification_needed": false
  }
}
```

#### POST /api/v1/pages

请求：
```json
{
  "page_id": "demo_page",
  "name": {"zh-CN": "示例页", "en": "Demo Page"},
  "description": {"zh-CN": "示例描述", "en": "Demo desc"},
  "button_list": ["btn_primary"],
  "optional_actions": ["chat"],
  "ai_context": {"behavior_rules": "谨慎回答", "page_goal": "完成操作"},
  "screenshot_url": "/uploads/xxx.png"
}
```

响应：
```json
{
  "id": 1,
  "page_id": "demo_page",
  "name": {"zh-CN": "示例页", "en": "Demo Page"},
  "description": {"zh-CN": "示例描述", "en": "Demo desc"},
  "button_list": ["btn_primary"],
  "optional_actions": ["chat"],
  "ai_context": {"behavior_rules": "谨慎回答", "page_goal": "完成操作"},
  "screenshot_url": "/uploads/xxx.png",
  "status": "configured",
  "created_at": "2026-01-06T12:00:00Z",
  "updated_at": "2026-01-06T12:00:00Z"
}
```

### API 实现

```python
# app/api/v1/image_upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
import os
import uuid
from datetime import datetime
from app.core.config import settings

router = APIRouter(prefix="/api/v1/pages", tags=["Image Upload"])

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/upload-image")
async def upload_page_screenshot(file: UploadFile = File(...)):
    """
    上传页面截图
    
    - 验证文件格式 (PNG/JPG)
    - 验证文件大小 (<10MB)
    - 保存文件并返回 URL
    
    对应需求: REQ-M2-001, REQ-M2-002, REQ-M2-005, REQ-M2-006, 
              REQ-M2-010, REQ-M2-011
    """
    # 验证文件扩展名 (REQ-M2-010)
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_FILE_TYPE",
                "message": "仅支持 PNG、JPG 格式的图片",
                "allowed_types": list(ALLOWED_EXTENSIONS)
            }
        )
    
    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # 确保目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # 流式保存文件并校验大小 (REQ-M2-019, REQ-M2-011)
    total_size = 0
    with open(upload_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                f.close()
                os.remove(upload_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "FILE_TOO_LARGE",
                        "message": "图片大小不能超过 10MB",
                        "max_size_mb": 10,
                        "actual_size_mb": round(total_size / (1024 * 1024), 2)
                    }
                )
            f.write(chunk)
    
    # 返回文件 URL
    file_url = f"/uploads/{unique_filename}"
    
    return {
        "success": True,
        "file_url": file_url,
        "filename": unique_filename,
        "size_bytes": total_size
    }
```

```python
# app/api/v1/page_config.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
from app.database import get_db
from app.schemas.page_config import (
    PageConfigCreate, PageConfigUpdate, PageConfigResponse, PageConfigListItem
)
from app.schemas.vl_response import VLParseResult, ClarifyResponse
from app.services.parse_service import ParseService
from app.services.vl_model_service import VLModelService
from app.models.parse_session import ParseSession

router = APIRouter(prefix="/api/v1/pages", tags=["Page Config"])

@router.post("/parse")
async def trigger_ai_parse(
    image_url: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    触发 AI 解析页面截图
    
    - 调用 Qwen3-VL-8B-Instruct 模型
    - 执行语义级解析
    - 返回解析会话 ID
    
    对应需求: REQ-M2-007, REQ-M2-014
    """
    # 验证图片是否存在 (REQ-M2-014)
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "IMAGE_REQUIRED",
                "message": "请先上传页面截图"
            }
        )
    
    # 允许外部 URL，但限制协议 (REQ-M2-015)
    if image_url.startswith(("http://", "https://")) is False and image_url.startswith("/uploads/") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_IMAGE_URL",
                "message": "仅支持 http/https URL 或本地 uploads 路径"
            }
        )
    
    # 创建解析会话
    session = ParseSession(
        session_id=uuid.uuid4(),
        image_path=image_url,
        status="pending"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # 后台异步执行解析
    background_tasks.add_task(
        execute_parse,
        str(session.session_id),
        image_url,
        db
    )
    
    return {
        "session_id": str(session.session_id),
        "status": "pending",
        "message": "AI 正在分析页面...",
        "estimated_time_seconds": 30
    }

async def execute_parse(session_id: str, image_url: str, db: Session):
    """
    后台执行解析任务
    
    对应需求: REQ-M2-004 (30秒超时), REQ-M2-008, REQ-M2-012, REQ-M2-013
    """
    from app.services.vl_model_service import VLModelService
    from app.services.system_prompt_service import SystemPromptService
    import asyncio
    
    session = db.query(ParseSession).filter(
        ParseSession.session_id == session_id
    ).first()
    
    if not session:
        return
    
    try:
        session.status = "parsing"
        db.commit()
        
        # 获取 System Prompt
        prompt_service = SystemPromptService(db)
        system_prompt = prompt_service.get_current_prompt()
        
        # 调用 VL 模型 (REQ-M2-004: 30秒超时)
        vl_service = VLModelService()
        
        try:
            parse_result = await asyncio.wait_for(
                vl_service.parse_image(
                    image_url=image_url,
                    system_prompt=system_prompt.prompt_content
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            # REQ-M2-012: 超时处理
            session.status = "failed"
            session.error_message = "解析超时，请重试或尝试上传更清晰的截图"
            db.commit()
            return
        
        # 更新会话结果 (REQ-M3-014: 澄清问题与历史分离)
        session.current_questions = parse_result.clarification_questions or []
        session.parse_result = parse_result.dict(exclude={"clarification_questions"})
        session.confidence = parse_result.overall_confidence
        
        if parse_result.clarification_needed:
            session.status = "clarifying"
        else:
            session.status = "completed"
        
        db.commit()
        
    except Exception as e:
        # REQ-M2-013: 解析失败处理
        session.status = "failed"
        session.error_message = f"解析失败：{str(e)}"
        db.commit()
        # 记录错误日志
        import logging
        logging.error(f"VL Parse failed for session {session_id}: {e}")

@router.get("/parse/{session_id}/status")
async def get_parse_status(session_id: str, db: Session = Depends(get_db)):
    """
    获取解析状态
    
    对应需求: REQ-M2-009
    """
    session = db.query(ParseSession).filter(
        ParseSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="解析会话不存在"
        )
    
    response = {
        "session_id": str(session.session_id),
        "status": session.status,
        "confidence": float(session.confidence) if session.confidence else 0
    }
    
    if session.status == "completed":
        response["result"] = session.parse_result
    elif session.status == "clarifying":
        response["result"] = session.parse_result
        response["clarification_questions"] = session.current_questions or []
    elif session.status == "failed":
        response["error"] = session.error_message
    
    return response

@router.get("", response_model=List[PageConfigListItem])
async def list_pages(
    status: str = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取页面配置列表"""
    from app.models.page_config import PageConfig
    
    query = db.query(PageConfig)
    if status:
        query = query.filter(PageConfig.status == status)
    
    pages = query.offset(skip).limit(limit).all()
    
    return [
        PageConfigListItem(
            id=p.id,
            page_id=p.page_id,
            name_zh=p.name_zh,
            status=p.status,
            screenshot_url=p.screenshot_url,
            updated_at=p.updated_at
        )
        for p in pages
    ]

@router.post("", response_model=PageConfigResponse)
async def create_page(
    config: PageConfigCreate,
    db: Session = Depends(get_db)
):
    """创建新页面配置"""
    from app.models.page_config import PageConfig
    
    # 检查 page_id 是否已存在
    existing = db.query(PageConfig).filter(
        PageConfig.page_id == config.page_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"页面 ID '{config.page_id}' 已存在"
        )
    
    page = PageConfig(
        page_id=config.page_id,
        name_zh=config.name.zh_CN,
        name_en=config.name.en,
        description_zh=config.description.zh_CN,
        description_en=config.description.en,
        button_list=config.button_list,
        optional_actions=config.optional_actions,
        ai_context=config.ai_context.dict() if config.ai_context else None,
        screenshot_url=config.screenshot_url,
        status="configured"
    )
    
    db.add(page)
    db.commit()
    db.refresh(page)
    
    return page
```

---

## VL 模型服务实现

```python
# app/services/vl_model_service.py

import httpx
import base64
import json
from typing import Optional
from app.schemas.vl_response import VLParseResult, ParsedElement
from app.core.config import settings

class VLModelService:
    """
    Qwen3-VL-8B-Instruct 模型服务封装
    
    支持语义级解析: 元素识别 + 交互意图 + 业务含义推断
    对应需求: REQ-M2-003, REQ-M2-007
    """
    
    def __init__(self):
        self.model_endpoint = settings.VL_MODEL_ENDPOINT
        self.model_name = "Qwen3-VL-8B-Instruct"
        self.timeout = 30.0
    
    async def parse_image(
        self, 
        image_url: str, 
        system_prompt: str
    ) -> VLParseResult:
        """
        解析页面截图
        
        Args:
            image_url: 图片路径或 URL
            system_prompt: System Prompt 内容
            
        Returns:
            VLParseResult: 结构化解析结果
        """
        # 读取并编码图片
        image_base64 = await self._load_image(image_url)
        
        # 构建请求
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": f"data:image/png;base64,{image_base64}"
                    },
                    {
                        "type": "text",
                        "text": self._build_parse_prompt()
                    }
                ]
            }
        ]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.model_endpoint}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": 4096,
                    "temperature": 0.1,  # 低温度以获得更确定性的输出
                    "response_format": {"type": "json_object"}
                },
                headers={"Authorization": f"Bearer {settings.VL_API_KEY}"}
            )
            
            response.raise_for_status()
            result = response.json()
        
        # 解析模型输出 (REQ-M2-021: 解析失败自动纠错重试)
        content = result["choices"][0]["message"]["content"]
        parsed_data = await self._parse_json_with_retry(messages, content)
        
        return self._build_parse_result(parsed_data)
    
    async def _load_image(self, image_url: str) -> str:
        """加载图片并转为 base64"""
        if image_url.startswith(("http://", "https://")):
            # REQ-M2-016: SSRF 防护 (示意实现)
            if not self._is_safe_url(image_url):
                raise ValueError("禁止访问内网/本地/保留地址")
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, follow_redirects=True)
                content_type = resp.headers.get("Content-Type", "")
                if "image/png" not in content_type and "image/jpeg" not in content_type:
                    raise ValueError("仅支持 PNG、JPG 格式的图片")
                image_bytes = resp.content
                if len(image_bytes) > 10 * 1024 * 1024:
                    raise ValueError("图片大小不能超过 10MB")
        else:
            # 本地文件
            import aiofiles
            # REQ-M2-018: 仅允许 uploads 目录
            if not image_url.startswith("/uploads/"):
                raise ValueError("仅允许读取 uploads 目录下的文件")
            async with aiofiles.open(image_url.lstrip("/"), "rb") as f:
                image_bytes = await f.read()
        
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def _build_parse_prompt(self) -> str:
        """构建解析指令"""
        return """请分析这张页面截图，识别所有可交互元素并提取结构化配置。

请按以下 JSON 格式输出：
{
  "page_name": {
    "zh-CN": "页面中文名称",
    "en": "Page English Name"
  },
  "page_description": {
    "zh-CN": "页面功能描述（列出用户可执行的操作）",
    "en": "Page description"
  },
  "elements": [
    {
      "element_id": "snake_case_id",
      "element_type": "button|input|text|link",
      "label": "元素显示文本",
      "inferred_intent": "推断的交互意图",
      "confidence": 0.95
    }
  ],
  "button_list": ["button_id_1", "button_id_2"],
  "optional_actions": ["chat", "knowledge"],
  "ai_context": {
    "behavior_rules": "AI 在此页面的行为规则建议",
    "page_goal": "页面的核心目标"
  },
  "overall_confidence": 0.85,
  "clarification_needed": true/false,
  "clarification_questions": ["如果需要澄清，列出问题"]
}

注意：
1. element_id 使用 snake_case 格式
2. 如果某些元素的用途不明确，请设置 clarification_needed 为 true，并在 clarification_questions 中提出具体问题
3. confidence 取值 0-1，表示识别的置信度
"""
    
    def _build_parse_result(self, data: dict) -> VLParseResult:
        """构建解析结果对象"""
        elements = [
            ParsedElement(**elem) for elem in data.get("elements", [])
        ]
        
        return VLParseResult(
            page_name=data.get("page_name", {}),
            page_description=data.get("page_description", {}),
            elements=elements,
            button_list=data.get("button_list", []),
            optional_actions=data.get("optional_actions", []),
            ai_context=data.get("ai_context", {}),
            overall_confidence=data.get("overall_confidence", 0.5),
            clarification_needed=data.get("clarification_needed", False),
            clarification_questions=data.get("clarification_questions")
        )

    async def _parse_json_with_retry(self, messages: list, content: str) -> dict:
        """模型输出 JSON 解析失败时进行一次纠错重试"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 追加纠错提示，包含原始输出和错误信息，帮助模型纠正
            retry_messages = messages + [
                {
                    "role": "assistant",
                    "content": content  # 让模型知道自己之前输出了什么
                },
                {
                    "role": "user",
                    "content": f"你的输出不是合法的 JSON 格式，解析错误：{str(e)}。请重新输出，确保是有效的 JSON。"
                }
            ]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.model_endpoint}/v1/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": retry_messages,
                        "max_tokens": 4096,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    },
                    headers={"Authorization": f"Bearer {settings.VL_API_KEY}"}
                )
                response.raise_for_status()
                retry_result = response.json()
            retry_content = retry_result["choices"][0]["message"]["content"]
            return json.loads(retry_content)
    
    def _is_safe_url(self, url: str) -> bool:
        """
        SSRF 防护检查 (Demo 简化版)
        
        - 仅允许 http/https 协议
        - 拒绝明显的内网地址
        
        注意: Demo 版本仅做基础检查，生产环境需要更完整的防护
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        
        host = parsed.hostname
        if not host:
            return False
        
        # Demo 简化: 拒绝常见内网地址模式
        blocked_patterns = [
            "localhost", "127.", "10.", "192.168.", "172.16.",
            "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
            "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
            "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
            "169.254.", "::1", "0.0.0.0"
        ]
        
        host_lower = host.lower()
        for pattern in blocked_patterns:
            if host_lower.startswith(pattern) or host_lower == pattern:
                return False
        
        return True
    
    async def clarify(
        self,
        image_url: str,
        previous_result: dict,
        clarify_history: list,
        user_response: str,
        system_prompt: str
    ) -> VLParseResult:
        """
        基于用户回答进行澄清并更新配置
        
        用于模块 M3 的多轮澄清对话
        """
        image_base64 = await self._load_image(image_url)
        
        # 构建包含历史的对话
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": f"data:image/png;base64,{image_base64}"},
                    {"type": "text", "text": self._build_parse_prompt()}
                ]
            },
            {"role": "assistant", "content": json.dumps(previous_result, ensure_ascii=False)}
        ]
        
        # 添加澄清历史
        for item in clarify_history:
            messages.append({"role": "user", "content": item["question"]})
            messages.append({"role": "assistant", "content": item["answer"]})
        
        # 添加当前用户回答
        messages.append({
            "role": "user",
            "content": f"用户回答: {user_response}\n\n请基于这个信息更新配置，并判断是否还需要继续澄清。"
        })
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.model_endpoint}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": 4096,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                },
                headers={"Authorization": f"Bearer {settings.VL_API_KEY}"}
            )
            
            response.raise_for_status()
            result = response.json()
        
        content = result["choices"][0]["message"]["content"]
        parsed_data = json.loads(content)
        
        return self._build_parse_result(parsed_data)
```

---

## 前端组件设计

### 图片上传组件

```vue
<!-- components/PageConfig/ImageUploader.vue -->
<template>
  <div 
    class="image-uploader"
    :class="{ 
      'is-dragover': isDragover,
      'has-image': imageUrl,
      'is-disabled': disabled || isUploading
    }"
    @dragover.prevent="handleDragover"
    @dragleave="handleDragleave"
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <!-- 已上传状态 -->
    <template v-if="imageUrl">
      <img :src="imageUrl" alt="页面截图" class="preview-image" />
      <div class="overlay">
        <button class="btn-replace" @click.stop="triggerFileInput">
          更换图片
        </button>
        <button class="btn-remove" @click.stop="handleRemove">
          移除
        </button>
      </div>
    </template>
    
    <!-- 上传中状态 -->
    <template v-else-if="isUploading">
      <div class="upload-progress">
        <div class="progress-bar" :style="{ width: `${uploadProgress}%` }"></div>
        <span class="progress-text">上传中 {{ uploadProgress }}%</span>
      </div>
    </template>
    
    <!-- 默认状态 -->
    <template v-else>
      <div class="upload-placeholder">
        <svg class="upload-icon" viewBox="0 0 24 24">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
        </svg>
        <span class="upload-text">上传页面截图</span>
        <span class="upload-hint">支持 PNG, JPG 格式</span>
      </div>
    </template>
    
    <input
      ref="fileInput"
      type="file"
      accept=".png,.jpg,.jpeg"
      class="file-input"
      @change="handleFileSelect"
    />
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue'
import { uploadPageImage } from '@/api/pageConfig'

const props = defineProps({
  modelValue: String,
  disabled: Boolean
})

const emit = defineEmits(['update:modelValue', 'upload-success', 'upload-error'])

const fileInput = ref(null)
const isDragover = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const imageUrl = ref(props.modelValue)

const triggerFileInput = () => {
  if (!props.disabled && !isUploading.value) {
    fileInput.value?.click()
  }
}

const handleDragover = () => {
  if (!props.disabled) isDragover.value = true
}

const handleDragleave = () => {
  isDragover.value = false
}

const handleDrop = (e) => {
  isDragover.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const processFile = async (file) => {
  // 验证文件类型 (REQ-M2-010)
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg']
  if (!allowedTypes.includes(file.type)) {
    emit('upload-error', {
      code: 'INVALID_FILE_TYPE',
      message: '仅支持 PNG、JPG 格式的图片'
    })
    return
  }
  
  // 验证文件大小 (REQ-M2-011)
  const maxSize = 10 * 1024 * 1024 // 10MB
  if (file.size > maxSize) {
    emit('upload-error', {
      code: 'FILE_TOO_LARGE',
      message: '图片大小不能超过 10MB'
    })
    return
  }
  
  // 上传文件
  isUploading.value = true
  uploadProgress.value = 0
  
  try {
    const result = await uploadPageImage(file, (progress) => {
      uploadProgress.value = Math.round(progress * 100)
    })
    
    imageUrl.value = result.file_url
    emit('update:modelValue', result.file_url)
    emit('upload-success', result)
  } catch (error) {
    emit('upload-error', error)
  } finally {
    isUploading.value = false
  }
}

const handleRemove = () => {
  imageUrl.value = null
  emit('update:modelValue', null)
}
</script>

<style scoped>
.image-uploader {
  width: 100%;
  min-height: 300px;
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.image-uploader:hover:not(.is-disabled) {
  border-color: #1890ff;
}

.image-uploader.is-dragover {
  border-color: #1890ff;
  background-color: #e6f7ff;
}

.image-uploader.has-image {
  border-style: solid;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}

.image-uploader:hover .overlay {
  opacity: 1;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #999;
}

.upload-icon {
  width: 48px;
  height: 48px;
  fill: #d9d9d9;
}

.file-input {
  display: none;
}

.upload-progress {
  width: 200px;
  text-align: center;
}

.progress-bar {
  height: 4px;
  background: #1890ff;
  border-radius: 2px;
  margin-bottom: 8px;
}
</style>
```

---

## 测试用例

```python
# tests/test_vl_parsing.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
import io

client = TestClient(app)

class TestImageUpload:
    """图片上传测试"""
    
    def test_upload_png_success(self):
        """REQ-M2-001: 支持 PNG 格式"""
        # 创建测试图片
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", img_bytes, "image/png")}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        assert "file_url" in response.json()
    
    def test_upload_invalid_type(self):
        """REQ-M2-010: 拒绝非 PNG/JPG 格式"""
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.gif", b"fake gif content", "image/gif")}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "INVALID_FILE_TYPE"
    
    def test_upload_too_large(self):
        """REQ-M2-011: 拒绝超过 10MB 的文件"""
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", large_content, "image/png")}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "FILE_TOO_LARGE"


class TestAIParsing:
    """AI 解析测试"""
    
    def test_parse_without_image(self):
        """REQ-M2-014: 无图片时提示"""
        response = client.post(
            "/api/v1/pages/parse",
            json={"image_url": ""}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "IMAGE_REQUIRED"
    
    def test_parse_invalid_image_url(self):
        """REQ-M2-015: 非法 URL 拒绝解析"""
        response = client.post(
            "/api/v1/pages/parse",
            json={"image_url": "file:///etc/passwd"}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "INVALID_IMAGE_URL"
    
    @patch('app.services.vl_model_service.VLModelService.parse_image')
    async def test_parse_success(self, mock_parse):
        """REQ-M2-007, REQ-M2-008: 成功解析"""
        mock_result = {
            "page_name": {"zh-CN": "测试页面", "en": "Test Page"},
            "page_description": {"zh-CN": "测试描述", "en": "Test desc"},
            "elements": [],
            "button_list": ["btn_1"],
            "optional_actions": [],
            "ai_context": {},
            "overall_confidence": 0.9,
            "clarification_needed": False
        }
        mock_parse.return_value = AsyncMock(return_value=mock_result)
        
        response = client.post(
            "/api/v1/pages/parse",
            json={"image_url": "/uploads/test.png"}
        )
        
        assert response.status_code == 200
        assert "session_id" in response.json()
    
    @patch('app.services.vl_model_service.VLModelService.parse_image')
    async def test_parse_timeout(self, mock_parse):
        """REQ-M2-012: 超时处理"""
        import asyncio
        mock_parse.side_effect = asyncio.TimeoutError()
        
        # 触发解析并等待后台任务完成
        response = client.post(
            "/api/v1/pages/parse",
            json={"image_url": "/uploads/test.png"}
        )
        
        session_id = response.json()["session_id"]
        
        # 轮询状态
        import time
        time.sleep(1)  # 等待后台任务
        
        status_response = client.get(f"/api/v1/pages/parse/{session_id}/status")
        
        # 应该返回超时错误
        assert status_response.json()["status"] == "failed"

    @patch('app.services.vl_model_service.httpx.AsyncClient.post')
    async def test_model_output_invalid_json_retry(self, mock_post):
        """REQ-M2-021: 非 JSON 输出自动纠错重试"""
        # 第一次返回无效 JSON，第二次返回有效 JSON
        mock_post.side_effect = [
            AsyncMock(return_value=AsyncMock(
                json=AsyncMock(return_value={
                    "choices": [{"message": {"content": "{invalid json"}}]
                }),
                raise_for_status=AsyncMock()
            )),
            AsyncMock(return_value=AsyncMock(
                json=AsyncMock(return_value={
                    "choices": [{"message": {"content": "{\"page_name\": {\"zh-CN\": \"A\", \"en\": \"B\"}, \"page_description\": {\"zh-CN\": \"C\", \"en\": \"D\"}, \"elements\": [], \"button_list\": [\"b1\"], \"optional_actions\": [], \"ai_context\": {}, \"overall_confidence\": 0.9, \"clarification_needed\": false}"}]
                }),
                raise_for_status=AsyncMock()
            ))
        ]
        
        from app.services.vl_model_service import VLModelService
        service = VLModelService()
        service._load_image = AsyncMock(return_value="base64data")
        
        result = await service.parse_image("http://example.com/test.png", "prompt")
        assert result.page_name["zh-CN"] == "A"
        assert mock_post.call_count == 2
```

---

## 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M2-001 | 支持 PNG/JPG 上传 | 单元测试 |
| REQ-M2-002 | 文件大小限制 10MB | 单元测试 |
| REQ-M2-003 | 单图上传模式 | E2E 测试 |
| REQ-M2-004 | 30秒超时限制 | 模拟测试 |
| REQ-M2-005 | 点击添加页面跳转正确 | E2E 测试 |
| REQ-M2-006 | 上传进度条正常显示 | E2E 测试 |
| REQ-M2-007 | AI 辅助填写调用 VL 模型 | 集成测试 |
| REQ-M2-008 | 解析结果正确填充表单 | E2E 测试 |
| REQ-M2-009 | 解析中状态正确显示 | E2E 测试 |
| REQ-M2-010 | 非法格式拒绝上传 | 单元测试 |
| REQ-M2-011 | 超大文件拒绝上传 | 单元测试 |
| REQ-M2-012 | 超时正确提示 | 模拟测试 |
| REQ-M2-013 | 解析失败记录日志 | 日志测试 |
| REQ-M2-014 | 无图片提示上传 | 单元测试 |
| REQ-M2-015 | 仅允许 http/https URL | 单元测试 |
| REQ-M2-016 | 外部 URL SSRF 防护与大小限制 | *Demo 简化版* |
| REQ-M2-017 | 外部 URL 校验图片类型 | 单元测试 |
| REQ-M2-018 | 仅允许读取 uploads 目录 | 单元测试 |
| REQ-M2-019 | 上传流式写入防 OOM | 压力测试 |
| REQ-M2-020 | 临时文件 24h 清理 | 运维测试 |
| REQ-M2-021 | 输出非 JSON 自动纠错重试 | 单元测试 |
