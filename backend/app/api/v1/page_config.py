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
    PageConfigCreate, PageConfigUpdate, PageConfigDraft, PageConfigResponse, PageConfigListItem,
    MultiLangText, AIContext
)
from app.schemas.vl_response import ParseStatusResponse, ClarifyQuestion
from app.models.parse_session import ParseSession, SessionStatus
from app.models.page_config import PageConfig
from app.models.project import Project
from app.services.vl_model_service import VLModelService
from app.services.system_prompt_service import SystemPromptService
from app.services.prompt_injector import inject_prompt
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
        import json as json_module
        
        # 首先发送包含 session_id 的初始化事件
        yield f"data: {json_module.dumps({'type': 'init', 'session_id': session_id_str})}\n\n"
        
        async with AsyncSessionLocal() as stream_db:
            try:
                # 获取 System Prompt 和选择的模型
                prompt_service = SystemPromptService(stream_db)
                system_prompt = await prompt_service.get_current_prompt()
                selected_model = await prompt_service.get_selected_model()
                
                # 动态注入按钮列表和意图列表到 System Prompt
                injected_prompt = await inject_prompt(stream_db, system_prompt.prompt_content)
                
                # 获取可用按钮列表，用于验证 AI 返回的按钮
                from app.services.prompt_injector import PromptInjector
                injector = PromptInjector(stream_db)
                available_buttons = await injector.get_available_button_ids()
                
                # 调用 VL 模型流式接口 (使用选择的模型，传入可用按钮列表)
                vl_service = VLModelService(selected_model=selected_model, available_buttons=available_buttons)
                
                async for chunk in vl_service.parse_image_stream(
                    image_url=image_url,
                    system_prompt=injected_prompt
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
            
            # 获取 System Prompt 和选择的模型
            prompt_service = SystemPromptService(db)
            system_prompt = await prompt_service.get_current_prompt()
            selected_model = await prompt_service.get_selected_model()
            
            # 动态注入按钮列表和意图列表到 System Prompt
            injected_prompt = await inject_prompt(db, system_prompt.prompt_content)
            
            # 获取可用按钮列表，用于验证 AI 返回的按钮
            from app.services.prompt_injector import PromptInjector
            injector = PromptInjector(db)
            available_buttons = await injector.get_available_button_ids()
            
            # 调用 VL 模型 (REQ-M2-004: 30秒超时，使用选择的模型，传入可用按钮列表)
            vl_service = VLModelService(selected_model=selected_model, available_buttons=available_buttons)
            
            try:
                parse_result = await asyncio.wait_for(
                    vl_service.parse_image(
                        image_url=image_url,
                        system_prompt=injected_prompt
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


@router.get("/check-duplicate")
async def check_duplicate_page(
    page_id: str,
    name_zh: Optional[str] = None,
    exclude_page_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    检查是否存在同名页面（页面 ID 或页面名称重复）
    
    - page_id: 要检查的页面 ID
    - name_zh: 要检查的页面中文名称（可选）
    - exclude_page_id: 排除的页面 ID（用于编辑时排除自身）
    
    返回:
    - exists: 是否存在重复
    - conflict_type: 冲突类型 (page_id / name / both)
    - existing_page: 已存在页面的详细信息
    """
    conflicts = []
    existing_page = None
    
    # 检查页面 ID 是否存在
    query = select(PageConfig, Project.name.label("project_name")).outerjoin(
        Project, PageConfig.project_id == Project.id
    ).where(PageConfig.page_id == page_id)
    
    if exclude_page_id:
        query = query.where(PageConfig.page_id != exclude_page_id)
    
    result = await db.execute(query)
    row = result.first()
    
    if row:
        page = row[0]
        project_name = row[1]
        conflicts.append("page_id")
        existing_page = {
            "id": page.id,
            "page_id": page.page_id,
            "name": {
                "zh-CN": page.name_zh or "",
                "en": page.name_en or ""
            },
            "description": {
                "zh-CN": page.description_zh or "",
                "en": page.description_en or ""
            },
            "button_list": page.button_list or [],
            "optional_actions": page.optional_actions or [],
            "screenshot_url": page.screenshot_url,
            "project_id": page.project_id,
            "project_name": project_name,
            "status": page.status,
            "created_at": page.created_at.isoformat() if page.created_at else None,
            "updated_at": page.updated_at.isoformat() if page.updated_at else None
        }
    
    # 如果提供了名称，也检查名称是否重复
    if name_zh and not existing_page:
        query = select(PageConfig, Project.name.label("project_name")).outerjoin(
            Project, PageConfig.project_id == Project.id
        ).where(PageConfig.name_zh == name_zh)
        
        if exclude_page_id:
            query = query.where(PageConfig.page_id != exclude_page_id)
        
        result = await db.execute(query)
        row = result.first()
        
        if row:
            page = row[0]
            project_name = row[1]
            conflicts.append("name")
            existing_page = {
                "id": page.id,
                "page_id": page.page_id,
                "name": {
                    "zh-CN": page.name_zh or "",
                    "en": page.name_en or ""
                },
                "description": {
                    "zh-CN": page.description_zh or "",
                    "en": page.description_en or ""
                },
                "button_list": page.button_list or [],
                "optional_actions": page.optional_actions or [],
                "screenshot_url": page.screenshot_url,
                "project_id": page.project_id,
                "project_name": project_name,
                "status": page.status,
                "created_at": page.created_at.isoformat() if page.created_at else None,
                "updated_at": page.updated_at.isoformat() if page.updated_at else None
            }
    
    if not conflicts:
        return {
            "exists": False,
            "conflict_type": None,
            "existing_page": None
        }
    
    conflict_type = "both" if len(conflicts) > 1 else conflicts[0]
    
    return {
        "exists": True,
        "conflict_type": conflict_type,
        "existing_page": existing_page
    }


@router.get("", response_model=List[PageConfigListItem])
async def list_pages(
    page_status: Optional[str] = None,
    project_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取页面配置列表，支持按项目筛选"""
    # 使用 outerjoin 获取项目名称
    query = select(PageConfig, Project.name.label("project_name")).outerjoin(
        Project, PageConfig.project_id == Project.id
    )
    
    if page_status:
        query = query.where(PageConfig.status == page_status)
    
    if project_id is not None:
        if project_id == 0:
            # project_id=0 表示筛选未分配项目的页面
            query = query.where(PageConfig.project_id.is_(None))
        else:
            query = query.where(PageConfig.project_id == project_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    return [
        PageConfigListItem(
            id=p.id,
            page_id=p.page_id,
            name_zh=p.name_zh,
            status=p.status,
            project_id=p.project_id,
            project_name=project_name,
            screenshot_url=p.screenshot_url,
            updated_at=p.updated_at
        )
        for p, project_name in rows
    ]


@router.get("/{page_id}", response_model=PageConfigResponse)
async def get_page(page_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个页面配置"""
    result = await db.execute(
        select(PageConfig, Project.name.label("project_name"))
        .outerjoin(Project, PageConfig.project_id == Project.id)
        .where(PageConfig.page_id == page_id)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"页面 '{page_id}' 不存在"
        )
    
    page, project_name = row
    
    # 使用兼容方法获取完整描述（包含旧 ai_context 数据）
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=MultiLangText(**{"zh-CN": page.name_zh, "en": page.name_en}),
        description=MultiLangText(**{
            "zh-CN": page.get_full_description_zh(),
            "en": page.get_full_description_en()
        }),
        button_list=page.button_list or [],
        optional_actions=page.optional_actions or [],
        # ai_context 已废弃，返回 None（旧数据已合并到 description）
        ai_context=None,
        screenshot_url=page.screenshot_url,
        project_id=page.project_id,
        project_name=project_name,
        status=page.status,
        created_at=page.created_at,
        updated_at=page.updated_at
    )


def _get_ai_context_values(ai_context):
    """从 ai_context 中提取 behavior_rules 和 page_goal"""
    if not ai_context:
        return None, None
    
    behavior_rules = getattr(ai_context, 'behavior_rules', None) or (
        ai_context.get("behavior_rules") if isinstance(ai_context, dict) else None
    )
    page_goal = getattr(ai_context, 'page_goal', None) or (
        ai_context.get("page_goal") if isinstance(ai_context, dict) else None
    )
    
    return behavior_rules, page_goal


def _merge_ai_context_to_description_zh(base_description: str, ai_context) -> str:
    """将旧的 ai_context 数据合并到中文描述中"""
    behavior_rules, page_goal = _get_ai_context_values(ai_context)
    if not behavior_rules and not page_goal:
        return base_description
    
    parts = [base_description] if base_description else []
    
    if behavior_rules:
        parts.append(f"\n\n## 行为规则\n{behavior_rules}")
    if page_goal:
        parts.append(f"\n\n## 页面目标\n{page_goal}")
    
    return "".join(parts).strip()


def _merge_ai_context_to_description_en(base_description: str, ai_context) -> str:
    """将旧的 ai_context 数据合并到英文描述中"""
    behavior_rules, page_goal = _get_ai_context_values(ai_context)
    if not behavior_rules and not page_goal:
        return base_description
    
    parts = [base_description] if base_description else []
    
    if behavior_rules:
        parts.append(f"\n\n## Behavior Rules\n{behavior_rules}")
    if page_goal:
        parts.append(f"\n\n## Page Goal\n{page_goal}")
    
    return "".join(parts).strip()


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
    
    # 如果指定了项目，验证项目是否存在
    project_name = None
    if config.project_id:
        project_result = await db.execute(
            select(Project).where(Project.id == config.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 ID {config.project_id} 不存在"
            )
        project_name = project.name
    
    # 如果有 ai_context，将其合并到中文和英文描述中
    description_zh = config.description.zh_CN
    description_en = config.description.en
    if config.ai_context:
        description_zh = _merge_ai_context_to_description_zh(description_zh, config.ai_context)
        description_en = _merge_ai_context_to_description_en(description_en, config.ai_context)
    
    page = PageConfig(
        page_id=config.page_id,
        name_zh=config.name.zh_CN,
        name_en=config.name.en,
        description_zh=description_zh,
        description_en=description_en,
        button_list=config.button_list,
        optional_actions=config.optional_actions,
        # ai_context 不再单独存储，已合并到 description
        ai_context=None,
        screenshot_url=config.screenshot_url,
        project_id=config.project_id,
        status="configured"
    )
    
    db.add(page)
    await db.commit()
    await db.refresh(page)
    
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=config.name,
        description=MultiLangText(**{
            "zh-CN": page.get_full_description_zh(),
            "en": page.get_full_description_en()
        }),
        button_list=page.button_list,
        optional_actions=page.optional_actions,
        # ai_context 已废弃，返回 None
        ai_context=None,
        screenshot_url=page.screenshot_url,
        project_id=page.project_id,
        project_name=project_name,
        status=page.status,
        created_at=page.created_at,
        updated_at=page.updated_at
    )


@router.post("/draft", response_model=PageConfigResponse)
async def save_draft(
    config: PageConfigDraft,
    db: AsyncSession = Depends(get_db)
):
    """保存页面配置草稿"""
    result = await db.execute(
        select(PageConfig).where(PageConfig.page_id == config.page_id)
    )
    page = result.scalar_one_or_none()

    name_zh = ""
    name_en = ""
    if config.name:
        name_zh = config.name.zh_CN or ""
        name_en = config.name.en or ""
    elif page:
        name_zh = page.name_zh or ""
        name_en = page.name_en or ""

    description_zh = ""
    description_en = ""
    if config.description:
        description_zh = config.description.zh_CN or ""
        description_en = config.description.en or ""
    elif page:
        description_zh = page.description_zh or ""
        description_en = page.description_en or ""

    if config.ai_context:
        description_zh = _merge_ai_context_to_description_zh(description_zh, config.ai_context)
        description_en = _merge_ai_context_to_description_en(description_en, config.ai_context)

    button_list = config.button_list if config.button_list is not None else None
    optional_actions = config.optional_actions if config.optional_actions is not None else None

    if page:
        page.name_zh = name_zh
        page.name_en = name_en
        page.description_zh = description_zh
        page.description_en = description_en
        if button_list is not None:
            page.button_list = button_list
        if optional_actions is not None:
            page.optional_actions = optional_actions
        page.ai_context = None
        if config.screenshot_url is not None:
            page.screenshot_url = config.screenshot_url
        if config.project_id is not None:
            if config.project_id == 0:
                page.project_id = None
            else:
                project_result = await db.execute(
                    select(Project).where(Project.id == config.project_id)
                )
                project = project_result.scalar_one_or_none()
                if not project:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"项目 ID {config.project_id} 不存在"
                    )
                page.project_id = config.project_id
        page.status = "draft"
    else:
        if config.project_id not in (0, None):
            project_result = await db.execute(
                select(Project).where(Project.id == config.project_id)
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目 ID {config.project_id} 不存在"
                )
        page = PageConfig(
            page_id=config.page_id,
            name_zh=name_zh,
            name_en=name_en,
            description_zh=description_zh,
            description_en=description_en,
            button_list=button_list or [],
            optional_actions=optional_actions or [],
            ai_context=None,
            screenshot_url=config.screenshot_url,
            project_id=config.project_id if config.project_id not in (0, None) else None,
            status="draft"
        )
        db.add(page)

    await db.commit()
    await db.refresh(page)

    project_name = None
    if page.project_id:
        project_result = await db.execute(
            select(Project.name).where(Project.id == page.project_id)
        )
        project_name = project_result.scalar_one_or_none()

    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=MultiLangText(**{"zh-CN": page.name_zh or "", "en": page.name_en or ""}),
        description=MultiLangText(**{
            "zh-CN": page.get_full_description_zh() or "",
            "en": page.get_full_description_en() or ""
        }),
        button_list=page.button_list or [],
        optional_actions=page.optional_actions or [],
        ai_context=None,
        screenshot_url=page.screenshot_url,
        project_id=page.project_id,
        project_name=project_name,
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
        # 如果同时提供了 ai_context，将其合并到中文和英文描述中
        description_zh = config.description.zh_CN
        description_en = config.description.en
        if config.ai_context:
            description_zh = _merge_ai_context_to_description_zh(description_zh, config.ai_context)
            description_en = _merge_ai_context_to_description_en(description_en, config.ai_context)
        page.description_zh = description_zh
        page.description_en = description_en
    elif config.ai_context:
        # 只有 ai_context 没有 description，合并到现有描述
        page.description_zh = _merge_ai_context_to_description_zh(
            page.description_zh or "", 
            config.ai_context
        )
        page.description_en = _merge_ai_context_to_description_en(
            page.description_en or "", 
            config.ai_context
        )
    
    if config.button_list is not None:
        page.button_list = config.button_list
    if config.optional_actions is not None:
        page.optional_actions = config.optional_actions
    
    # ai_context 不再单独存储，清空旧字段
    page.ai_context = None
    
    if config.screenshot_url is not None:
        page.screenshot_url = config.screenshot_url
    
    # 更新项目关联 (project_id 可以设为 null 来取消关联)
    if config.project_id is not None:
        if config.project_id == 0:
            # project_id=0 表示取消项目关联
            page.project_id = None
        else:
            # 验证项目是否存在
            project_result = await db.execute(
                select(Project).where(Project.id == config.project_id)
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目 ID {config.project_id} 不存在"
                )
            page.project_id = config.project_id

    page.status = "configured"
    
    await db.commit()
    await db.refresh(page)
    
    # 获取项目名称
    project_name = None
    if page.project_id:
        project_result = await db.execute(
            select(Project.name).where(Project.id == page.project_id)
        )
        project_name = project_result.scalar_one_or_none()
    
    return PageConfigResponse(
        id=page.id,
        page_id=page.page_id,
        name=MultiLangText(**{"zh-CN": page.name_zh, "en": page.name_en}),
        description=MultiLangText(**{
            "zh-CN": page.get_full_description_zh(),
            "en": page.get_full_description_en()
        }),
        button_list=page.button_list or [],
        optional_actions=page.optional_actions or [],
        # ai_context 已废弃，返回 None
        ai_context=None,
        screenshot_url=page.screenshot_url,
        project_id=page.project_id,
        project_name=project_name,
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
