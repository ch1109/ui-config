# app/api/v1/page_config.py
"""
页面配置 API
对应模块: M2
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import os
import uuid
from datetime import datetime
import asyncio
import logging

from app.database import get_db, AsyncSessionLocal
from app.schemas.page_config import (
    PageConfigCreate, PageConfigUpdate, PageConfigResponse, PageConfigListItem,
    MultiLangText, AIContext
)
from app.schemas.vl_response import ParseStatusResponse, ClarifyQuestion
from app.models.parse_session import ParseSession, SessionStatus
from app.models.page_config import PageConfig
from app.services.vl_model_service import VLModelService
from app.services.system_prompt_service import SystemPromptService
from app.core.config import settings
from app.core.exceptions import (
    InvalidFileTypeError, FileTooLargeError, ImageRequiredError,
    SessionNotFoundError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/pages", tags=["Page Config"])

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


@router.post("/upload-image")
async def upload_page_screenshot(file: UploadFile = File(...)):
    """
    上传页面截图
    
    - 验证文件格式 (PNG/JPG)
    - 验证文件大小 (<10MB)
    - 保存文件并返回 URL
    
    对应需求: REQ-M2-001, REQ-M2-002, REQ-M2-005, REQ-M2-006, 
              REQ-M2-010, REQ-M2-011, REQ-M2-019
    """
    # 验证文件扩展名 (REQ-M2-010)
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(list(ALLOWED_EXTENSIONS))
    
    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # 确保目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # 流式保存文件并校验大小 (REQ-M2-019, REQ-M2-011)
    total_size = 0
    try:
        with open(upload_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > settings.MAX_UPLOAD_SIZE:
                    f.close()
                    os.remove(upload_path)
                    raise FileTooLargeError(
                        max_size_mb=settings.MAX_UPLOAD_SIZE // (1024 * 1024),
                        actual_size_mb=total_size / (1024 * 1024)
                    )
                f.write(chunk)
    except FileTooLargeError:
        raise
    except Exception as e:
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    # 返回文件 URL
    file_url = f"/uploads/{unique_filename}"
    
    return {
        "success": True,
        "file_url": file_url,
        "filename": unique_filename,
        "size_bytes": total_size
    }


@router.post("/parse")
async def trigger_ai_parse(
    image_url: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    触发 AI 解析页面截图
    
    - 调用 Qwen3-VL-8B-Instruct 模型
    - 执行语义级解析
    - 返回解析会话 ID
    
    对应需求: REQ-M2-007, REQ-M2-014, REQ-M2-015
    """
    # 验证图片是否存在 (REQ-M2-014)
    if not image_url:
        raise ImageRequiredError()
    
    # 验证 URL 格式 (REQ-M2-015)
    if not (image_url.startswith(("http://", "https://")) or image_url.startswith("/uploads/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_IMAGE_URL",
                "message": "仅支持 http/https URL 或本地 uploads 路径"
            }
        )
    
    # 创建解析会话
    session_id = str(uuid.uuid4())
    session = ParseSession(
        session_id=session_id,
        image_path=image_url,
        status=SessionStatus.PENDING.value
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # 后台异步执行解析
    background_tasks.add_task(
        execute_parse,
        session_id,
        image_url
    )
    
    return {
        "session_id": session_id,
        "status": "pending",
        "message": "AI 正在分析页面...",
        "estimated_time_seconds": 30
    }


@router.get("/parse-stream")
async def trigger_ai_parse_stream(
    image_url: str,
    db: AsyncSession = Depends(get_db)
):
    """
    流式 AI 解析页面截图 (SSE)
    
    - 实时返回解析进度
    - 支持流式输出
    - 提升用户体验
    
    对应需求: REQ-M2-007, REQ-M2-014, REQ-M2-015
    """
    # 验证图片是否存在
    if not image_url:
        raise ImageRequiredError()
    
    # 验证 URL 格式
    if not (image_url.startswith(("http://", "https://")) or image_url.startswith("/uploads/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_IMAGE_URL",
                "message": "仅支持 http/https URL 或本地 uploads 路径"
            }
        )
    
    # 创建解析会话
    session_id = str(uuid.uuid4())
    session = ParseSession(
        session_id=session_id,
        image_path=image_url,
        status=SessionStatus.PARSING.value
    )
    db.add(session)
    await db.commit()
    session_id_str = str(session_id)
    
    async def stream_generator():
        """流式生成器"""
        async with AsyncSessionLocal() as stream_db:
            try:
                # 获取 System Prompt
                prompt_service = SystemPromptService(stream_db)
                system_prompt = await prompt_service.get_current_prompt()
                
                # 调用 VL 模型流式接口
                vl_service = VLModelService()
                
                async for chunk in vl_service.parse_image_stream(
                    image_url=image_url,
                    system_prompt=system_prompt.prompt_content
                ):
                    yield chunk
                
                # 获取最新会话状态
                result = await stream_db.execute(
                    select(ParseSession).where(ParseSession.session_id == session_id_str)
                )
                session = result.scalar_one_or_none()
                
                if session and session.status == SessionStatus.PARSING.value:
                    # 更新状态为已完成
                    session.status = SessionStatus.COMPLETED.value
                    await stream_db.commit()
                    
            except Exception as e:
                logger.exception(f"Stream parse error for session {session_id_str}: {e}")
                # 更新状态为失败
                result = await stream_db.execute(
                    select(ParseSession).where(ParseSession.session_id == session_id_str)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.status = SessionStatus.FAILED.value
                    session.error_message = str(e)
                    await stream_db.commit()
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def execute_parse(session_id: str, image_url: str):
    """
    后台执行解析任务
    
    对应需求: REQ-M2-004 (30秒超时), REQ-M2-008, REQ-M2-012, REQ-M2-013
    """
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ParseSession).where(ParseSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return
        
        try:
            session.status = SessionStatus.PARSING.value
            await db.commit()
            
            # 获取 System Prompt
            prompt_service = SystemPromptService(db)
            system_prompt = await prompt_service.get_current_prompt()
            
            # 调用 VL 模型 (REQ-M2-004: 30秒超时)
            vl_service = VLModelService()
            
            try:
                parse_result = await asyncio.wait_for(
                    vl_service.parse_image(
                        image_url=image_url,
                        system_prompt=system_prompt.prompt_content
                    ),
                    timeout=settings.VL_TIMEOUT
                )
            except asyncio.TimeoutError:
                # REQ-M2-012: 超时处理
                session.status = SessionStatus.FAILED.value
                session.error_message = "解析超时，请重试或尝试上传更清晰的截图"
                await db.commit()
                return
            
            # 更新会话结果 (REQ-M3-014: 澄清问题与历史分离)
            session.current_questions = parse_result.clarification_questions or []
            session.parse_result = parse_result.model_dump(exclude={"clarification_questions"})
            session.confidence = parse_result.overall_confidence * 100  # 转为百分比
            
            if parse_result.clarification_needed and parse_result.overall_confidence < settings.CLARIFY_CONFIDENCE_THRESHOLD:
                session.status = SessionStatus.CLARIFYING.value
            else:
                session.status = SessionStatus.COMPLETED.value
            
            await db.commit()
            
        except Exception as e:
            # REQ-M2-013: 解析失败处理
            session.status = SessionStatus.FAILED.value
            session.error_message = f"解析失败：{str(e)}"
            await db.commit()
            logger.exception(f"VL Parse failed for session {session_id}: {e}")


@router.get("/parse/{session_id}/status", response_model=ParseStatusResponse)
async def get_parse_status(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取解析状态
    
    对应需求: REQ-M2-009
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    response = ParseStatusResponse(
        session_id=str(session.session_id),
        status=session.status,
        confidence=float(session.confidence) if session.confidence else 0
    )
    
    if session.status == SessionStatus.COMPLETED.value:
        response.result = session.parse_result
    elif session.status == SessionStatus.CLARIFYING.value:
        response.result = session.parse_result
        # 转换问题格式
        questions = []
        for i, q in enumerate(session.current_questions or []):
            if isinstance(q, str):
                questions.append(ClarifyQuestion(
                    question_id=f"q{i+1}",
                    question_text=q,
                    context="general"
                ))
            elif isinstance(q, dict):
                questions.append(ClarifyQuestion(
                    question_id=q.get("question_id", f"q{i+1}"),
                    question_text=q.get("question_text", str(q)),
                    context=q.get("context", "general"),
                    options=q.get("options")
                ))
        response.clarification_questions = questions
    elif session.status == SessionStatus.FAILED.value:
        response.error = session.error_message
    
    return response


@router.get("", response_model=List[PageConfigListItem])
async def list_pages(
    page_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取页面配置列表"""
    query = select(PageConfig)
    if page_status:
        query = query.where(PageConfig.status == page_status)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    pages = result.scalars().all()
    
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


@router.get("/{page_id}", response_model=PageConfigResponse)
async def get_page(page_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个页面配置"""
    result = await db.execute(
        select(PageConfig).where(PageConfig.page_id == page_id)
    )
    page = result.scalar_one_or_none()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"页面 '{page_id}' 不存在"
        )
    
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=MultiLangText(**{"zh-CN": page.name_zh, "en": page.name_en}),
        description=MultiLangText(**{"zh-CN": page.description_zh or "", "en": page.description_en or ""}),
        button_list=page.button_list or [],
        optional_actions=page.optional_actions or [],
        ai_context=AIContext(**page.ai_context) if page.ai_context else None,
        screenshot_url=page.screenshot_url,
        status=page.status,
        created_at=page.created_at,
        updated_at=page.updated_at
    )


@router.post("", response_model=PageConfigResponse)
async def create_page(
    config: PageConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新页面配置"""
    # 检查 page_id 是否已存在
    result = await db.execute(
        select(PageConfig).where(PageConfig.page_id == config.page_id)
    )
    existing = result.scalar_one_or_none()
    
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
        ai_context=config.ai_context.model_dump() if config.ai_context else None,
        screenshot_url=config.screenshot_url,
        status="configured"
    )
    
    db.add(page)
    await db.commit()
    await db.refresh(page)
    
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=config.name,
        description=config.description,
        button_list=page.button_list,
        optional_actions=page.optional_actions,
        ai_context=config.ai_context,
        screenshot_url=page.screenshot_url,
        status=page.status,
        created_at=page.created_at,
        updated_at=page.updated_at
    )


@router.put("/{page_id}", response_model=PageConfigResponse)
async def update_page(
    page_id: str,
    config: PageConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新页面配置"""
    result = await db.execute(
        select(PageConfig).where(PageConfig.page_id == page_id)
    )
    page = result.scalar_one_or_none()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"页面 '{page_id}' 不存在"
        )
    
    # 更新字段
    if config.name:
        page.name_zh = config.name.zh_CN
        page.name_en = config.name.en
    if config.description:
        page.description_zh = config.description.zh_CN
        page.description_en = config.description.en
    if config.button_list is not None:
        page.button_list = config.button_list
    if config.optional_actions is not None:
        page.optional_actions = config.optional_actions
    if config.ai_context:
        page.ai_context = config.ai_context.model_dump()
    if config.screenshot_url is not None:
        page.screenshot_url = config.screenshot_url
    
    await db.commit()
    await db.refresh(page)
    
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=MultiLangText(**{"zh-CN": page.name_zh, "en": page.name_en}),
        description=MultiLangText(**{"zh-CN": page.description_zh or "", "en": page.description_en or ""}),
        button_list=page.button_list or [],
        optional_actions=page.optional_actions or [],
        ai_context=AIContext(**page.ai_context) if page.ai_context else None,
        screenshot_url=page.screenshot_url,
        status=page.status,
        created_at=page.created_at,
        updated_at=page.updated_at
    )


@router.delete("/{page_id}")
async def delete_page(page_id: str, db: AsyncSession = Depends(get_db)):
    """删除页面配置"""
    result = await db.execute(
        select(PageConfig).where(PageConfig.page_id == page_id)
    )
    page = result.scalar_one_or_none()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"页面 '{page_id}' 不存在"
        )
    
    await db.delete(page)
    await db.commit()
    
    return {"success": True, "message": f"页面 '{page_id}' 已删除"}

