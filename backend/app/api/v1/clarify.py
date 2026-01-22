# app/api/v1/clarify.py
"""
多轮澄清对话 API
对应模块: M3
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import asyncio
import json

from app.database import get_db, AsyncSessionLocal
from app.models.parse_session import ParseSession, SessionStatus
from app.services.vl_model_service import VLModelService
from app.services.system_prompt_service import SystemPromptService
from app.core.config import settings
from app.core.exceptions import SessionNotFoundError, ClarifyTimeoutError

router = APIRouter(prefix="/api/v1/clarify", tags=["Clarification"])


class ClarifyRequest(BaseModel):
    """澄清请求"""
    user_response: str
    question_id: Optional[str] = None


class ConfirmRequest(BaseModel):
    """确认请求"""
    confirm: bool = True


@router.post("/{session_id}/respond")
async def submit_clarify_response(
    session_id: str,
    request: ClarifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    提交澄清回答
    
    - 将用户回答发送至模型
    - 更新配置草稿
    - 判断是否需要继续澄清
    
    对应需求: REQ-M3-006, REQ-M3-007, REQ-M3-010
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    if session.status not in [SessionStatus.CLARIFYING.value, SessionStatus.PENDING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前状态不支持澄清"
        )
    
    # 获取系统提示词、选择的模型和 VL 服务
    prompt_service = SystemPromptService(db)
    system_prompt = await prompt_service.get_current_prompt()
    selected_model = await prompt_service.get_selected_model()
    
    # 获取可用按钮列表，用于验证 AI 返回的按钮
    from app.services.prompt_injector import PromptInjector
    injector = PromptInjector(db)
    available_buttons = await injector.get_available_button_ids()
    
    vl_service = VLModelService(selected_model=selected_model, available_buttons=available_buttons)
    
    # 更新澄清历史 (REQ-M3-014)
    clarify_history = session.clarify_history or []
    current_questions = session.current_questions or []
    
    # 记录当前问题和用户回答
    if current_questions:
        question_text = ""
        if isinstance(current_questions[0], str):
            question_text = current_questions[0]
        elif isinstance(current_questions[0], dict):
            question_text = current_questions[0].get("question_text", "")
        
        clarify_history.append({
            "question": question_text,
            "answer": request.user_response,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    try:
        # REQ-M3-002: 15秒超时
        # REQ-M3-010: 超时重试
        retry_count = 0
        max_retries = 1
        
        while retry_count <= max_retries:
            try:
                updated_result = await asyncio.wait_for(
                    vl_service.clarify(
                        image_url=session.image_path,
                        previous_result=session.parse_result,
                        clarify_history=clarify_history,
                        user_response=request.user_response,
                        system_prompt=system_prompt.prompt_content
                    ),
                    timeout=settings.CLARIFY_TIMEOUT
                )
                break
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count > max_retries:
                    raise ClarifyTimeoutError(retried=True)
        
        # 更新会话
        session.current_questions = updated_result.clarification_questions or []
        session.parse_result = updated_result.model_dump(exclude={"clarification_questions"})
        session.clarify_history = clarify_history
        session.confidence = updated_result.overall_confidence * 100
        session.clarify_round = len(clarify_history)
        
        # REQ-M3-001/007: 判断是否结束澄清
        clarify_rounds = len(clarify_history)
        
        if updated_result.overall_confidence >= settings.CLARIFY_CONFIDENCE_THRESHOLD:
            session.status = SessionStatus.COMPLETED.value
            message = "配置已生成，请查看右侧表单"
        elif clarify_rounds >= settings.CLARIFY_MAX_ROUNDS:
            # 达到最大轮次，强制结束 (REQ-M3-001)
            session.status = SessionStatus.COMPLETED.value
            message = f"已达到最大澄清轮次({settings.CLARIFY_MAX_ROUNDS}轮)，请手动完善配置"
        elif not updated_result.clarification_needed:
            session.status = SessionStatus.COMPLETED.value
            message = "配置已生成"
        else:
            session.status = SessionStatus.CLARIFYING.value
            message = f"请继续回答澄清问题 (第{clarify_rounds + 1}/{settings.CLARIFY_MAX_ROUNDS}轮)"
        
        await db.commit()
        
        return {
            "session_id": session_id,
            "status": session.status,
            "confidence": float(session.confidence),
            "message": message,
            "updated_config": updated_result.model_dump(),
            "next_questions": session.current_questions if session.status == SessionStatus.CLARIFYING.value else None,
            "clarify_round": clarify_rounds
        }
        
    except ClarifyTimeoutError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"澄清处理失败: {str(e)}"
        )


@router.post("/{session_id}/confirm")
async def confirm_configuration(
    session_id: str,
    request: ConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    确认完成配置
    
    对应需求: REQ-M3-008
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    if request.confirm:
        session.status = SessionStatus.COMPLETED.value
        session.completed_at = datetime.utcnow()
        await db.commit()
        
        return {
            "session_id": session_id,
            "status": "completed",
            "message": "配置已确认完成",
            "final_config": session.parse_result
        }
    else:
        return {
            "session_id": session_id,
            "status": session.status,
            "message": "继续编辑"
        }


@router.get("/{session_id}/history")
async def get_clarify_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取澄清对话历史
    
    - 前端刷新后清空展示，但服务端保留当前会话内历史
    对应需求: REQ-M3-003
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    return {
        "session_id": session_id,
        "history": session.clarify_history or [],
        "current_questions": session.current_questions if session.status == SessionStatus.CLARIFYING.value else None,
        "clarify_round": session.clarify_round or 0,
        "max_rounds": settings.CLARIFY_MAX_ROUNDS
    }


class ChatRequest(BaseModel):
    """聊天请求 - 用于配置修改建议"""
    message: str
    current_config: Optional[dict] = None
    image_url: Optional[str] = None


@router.post("/{session_id}/chat")
async def chat_for_config_modification(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    通用聊天接口 - 用于配置修改建议
    
    用户可以在配置生成后继续与 AI 交互，提出修改建议
    AI 会根据用户的建议更新配置
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    # 获取系统提示词、选择的模型和 VL 服务
    prompt_service = SystemPromptService(db)
    system_prompt = await prompt_service.get_current_prompt()
    selected_model = await prompt_service.get_selected_model()
    
    # 获取可用按钮列表，用于验证 AI 返回的按钮
    from app.services.prompt_injector import PromptInjector
    injector = PromptInjector(db)
    available_buttons = await injector.get_available_button_ids()
    
    vl_service = VLModelService(selected_model=selected_model, available_buttons=available_buttons)
    
    # 获取当前配置
    current_config = request.current_config or session.parse_result or {}
    
    # 更新澄清历史
    clarify_history = session.clarify_history or []
    clarify_history.append({
        "question": "用户修改建议",
        "answer": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    try:
        # 调用 VL 模型进行配置更新
        updated_result = await asyncio.wait_for(
            vl_service.clarify(
                image_url=session.image_path,
                previous_result=current_config,
                clarify_history=clarify_history,
                user_response=f"用户的修改建议: {request.message}",
                system_prompt=system_prompt.prompt_content
            ),
            timeout=settings.VL_TIMEOUT
        )
        
        # 更新会话
        session.parse_result = updated_result.model_dump(exclude={"clarification_questions"})
        session.clarify_history = clarify_history
        session.confidence = updated_result.overall_confidence * 100
        
        await db.commit()
        
        return {
            "session_id": session_id,
            "status": "success",
            "message": "好的，我已根据您的建议更新了配置。",
            "updated_config": updated_result.model_dump()
        }
        
    except asyncio.TimeoutError:
        return {
            "session_id": session_id,
            "status": "error",
            "message": "请求超时，请重试"
        }
    except Exception as e:
        return {
            "session_id": session_id,
            "status": "error",
            "message": f"处理失败: {str(e)}"
        }


@router.post("/{session_id}/chat-stream")
async def chat_for_config_modification_stream(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    通用聊天接口 - 流式输出 (用于配置修改建议)
    
    用户可以在配置生成后继续与 AI 交互，提出修改建议
    AI 会根据用户的建议实时更新配置
    """
    result = await db.execute(
        select(ParseSession).where(ParseSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    # 保存请求信息
    image_path = session.image_path
    current_config = request.current_config or session.parse_result or {}
    clarify_history = session.clarify_history or []
    user_message = request.message
    session_id_str = str(session_id)
    
    async def stream_generator():
        """流式生成器"""
        async with AsyncSessionLocal() as stream_db:
            try:
                # 获取系统提示词和选择的模型
                prompt_service = SystemPromptService(stream_db)
                system_prompt = await prompt_service.get_current_prompt()
                selected_model = await prompt_service.get_selected_model()
                
                # 获取可用按钮列表，用于验证 AI 返回的按钮
                from app.services.prompt_injector import PromptInjector
                injector = PromptInjector(stream_db)
                available_buttons = await injector.get_available_button_ids()
                
                vl_service = VLModelService(selected_model=selected_model, available_buttons=available_buttons)
                
                # 更新澄清历史
                new_history = clarify_history + [{
                    "question": "用户修改建议",
                    "answer": user_message,
                    "timestamp": datetime.utcnow().isoformat()
                }]
                
                # 调用流式接口
                async for chunk in vl_service.clarify_stream(
                    image_url=image_path,
                    previous_result=current_config,
                    clarify_history=new_history,
                    user_response=f"用户的修改建议: {user_message}",
                    system_prompt=system_prompt.prompt_content
                ):
                    # 如果是完成事件,更新数据库
                    if '"type": "complete"' in chunk:
                        try:
                            data = json.loads(chunk.replace("data: ", "").strip())
                            if data.get("type") == "complete":
                                result = await stream_db.execute(
                                    select(ParseSession).where(ParseSession.session_id == session_id_str)
                                )
                                db_session = result.scalar_one_or_none()
                                if db_session:
                                    db_session.parse_result = data["result"]
                                    db_session.clarify_history = new_history
                                    db_session.confidence = data["result"].get("overall_confidence", 0) * 100
                                    await stream_db.commit()
                        except Exception as e:
                            import logging
                            logging.error(f"Failed to update session: {e}")
                    
                    yield chunk
                    
            except Exception as e:
                import logging
                logging.exception(f"Stream chat error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

