# app/api/v1/mcp_host.py
"""
MCP Host API 端点
提供完整的 Host 功能接口，包括：
1. 对话管理
2. ReAct 循环
3. 工具调用
4. 人机回环确认
5. SSE 服务器管理
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import asyncio
import logging

from app.database import get_db
from app.services.mcp_host_service import mcp_host_service, ToolRiskLevel
from app.services.react_engine import react_engine, LLMConfig, ReActState
from app.services.human_in_loop import human_in_loop_service, ConfirmationStatus
from app.services.sse_mcp_client import sse_mcp_client
from app.services.stdio_mcp_manager import stdio_mcp_manager

router = APIRouter(prefix="/api/v1/host", tags=["MCP Host"])
logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = None
    system_prompt: Optional[str] = ""


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    created_at: str
    message_count: int
    pending_confirmations: int


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    
    # LLM 配置
    llm_provider: str = "openai"  # openai, anthropic, ollama
    llm_model: str = "gpt-4o"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # ReAct 配置
    max_iterations: int = 10
    stream: bool = True


class ConfirmationRequest(BaseModel):
    """确认请求"""
    approved: bool
    modified_arguments: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class SSEServerConfig(BaseModel):
    """SSE 服务器配置"""
    server_key: str
    base_url: str
    sse_endpoint: str = "/sse"
    message_endpoint: str = "/message"
    auth_token: Optional[str] = None
    auth_type: str = "bearer"


class ToolCallRequest(BaseModel):
    """直接工具调用请求"""
    server_key: str
    tool_name: str
    arguments: Dict[str, Any] = {}
    skip_confirmation: bool = False


# ==================== 会话管理 ====================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    创建新的 Host 会话
    """
    import uuid
    session_id = request.session_id or str(uuid.uuid4())
    
    # 创建 Host 会话
    session = mcp_host_service.create_session(session_id)
    
    # 创建 ReAct 上下文
    react_engine.create_context(
        session_id,
        system_prompt=request.system_prompt or ""
    )
    
    return SessionResponse(
        session_id=session_id,
        created_at=session.created_at.isoformat(),
        message_count=len(session.messages),
        pending_confirmations=len(session.pending_tool_calls)
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取会话信息"""
    session = mcp_host_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionResponse(
        session_id=session_id,
        created_at=session.created_at.isoformat(),
        message_count=len(session.messages),
        pending_confirmations=len(session.pending_tool_calls)
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    mcp_host_service.delete_session(session_id)
    
    # 清理 ReAct 上下文
    if session_id in react_engine.contexts:
        del react_engine.contexts[session_id]
    
    return {"success": True}


# ==================== 对话（ReAct 循环） ====================

@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest):
    """
    发送消息并运行 ReAct 循环
    
    支持流式响应，实时返回推理步骤和工具调用结果
    """
    # 构建 LLM 配置
    llm_config = LLMConfig(
        provider=request.llm_provider,
        model=request.llm_model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )
    
    if request.stream:
        # 流式响应
        async def generate():
            async for event in react_engine.run_react_loop(
                session_id=session_id,
                user_input=request.message,
                llm_config=llm_config
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # 非流式响应
        events = []
        final_content = ""
        
        async for event in react_engine.run_react_loop(
            session_id=session_id,
            user_input=request.message,
            llm_config=llm_config
        ):
            events.append(event)
            if event.get("type") == "final":
                final_content = event.get("content", "")
        
        return {
            "content": final_content,
            "events": events
        }


# ==================== 人机回环确认 ====================

@router.get("/sessions/{session_id}/confirmations")
async def get_pending_confirmations(session_id: str):
    """
    获取待确认的工具调用列表
    """
    requests = human_in_loop_service.get_pending_requests(session_id)
    
    return {
        "count": len(requests),
        "requests": [
            human_in_loop_service.format_for_ui(req)
            for req in requests
        ]
    }


@router.post("/sessions/{session_id}/confirmations/{request_id}")
async def confirm_tool_call(
    session_id: str,
    request_id: str,
    request: ConfirmationRequest
):
    """
    确认或拒绝工具调用
    
    这是人机回环的核心接口
    """
    try:
        if request.approved:
            result = await human_in_loop_service.approve(
                request_id=request_id,
                approved_by="user",
                modified_arguments=request.modified_arguments
            )
        else:
            result = await human_in_loop_service.reject(
                request_id=request_id,
                rejected_by="user",
                reason=request.reason or ""
            )
        
        return {
            "success": True,
            "status": result.status.value,
            "request_id": request_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/confirmations/{request_id}/continue")
async def continue_after_confirmation(
    session_id: str,
    request_id: str,
    request: ConfirmationRequest,
    chat_request: Optional[ChatRequest] = None
):
    """
    确认工具调用并继续 ReAct 循环
    
    这是一个组合操作：先确认，然后继续执行
    """
    # 首先处理确认
    try:
        if request.approved:
            await human_in_loop_service.approve(
                request_id=request_id,
                approved_by="user",
                modified_arguments=request.modified_arguments
            )
        else:
            await human_in_loop_service.reject(
                request_id=request_id,
                rejected_by="user",
                reason=request.reason or ""
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 如果有 LLM 配置，继续循环
    if chat_request:
        llm_config = LLMConfig(
            provider=chat_request.llm_provider,
            model=chat_request.llm_model,
            api_key=chat_request.api_key,
            base_url=chat_request.base_url,
            temperature=chat_request.temperature,
            max_tokens=chat_request.max_tokens
        )
        
        async def generate():
            async for event in react_engine.continue_after_confirmation(
                session_id=session_id,
                request_id=request_id,
                approved=request.approved,
                modified_arguments=request.modified_arguments,
                llm_config=llm_config
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    
    return {"success": True, "status": "confirmed" if request.approved else "rejected"}


@router.get("/audit-log")
async def get_audit_log(
    session_id: Optional[str] = None,
    limit: int = 100
):
    """获取审计日志"""
    return {
        "logs": human_in_loop_service.get_audit_log(session_id, limit)
    }


# ==================== 工具管理 ====================

@router.get("/tools")
async def list_all_tools():
    """
    获取所有可用工具
    
    聚合所有已连接的 MCP 服务器的工具
    """
    tools = await mcp_host_service.get_aggregated_tools()
    
    return {
        "count": len(tools),
        "tools": tools
    }


@router.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    """
    直接调用工具（不通过 ReAct 循环）
    
    适用于需要单独调用工具的场景
    """
    # 构建完整工具名
    full_tool_name = f"{request.server_key}__{request.tool_name}"
    
    # 准备调用
    tool_request = await mcp_host_service.prepare_tool_call(
        session_id="direct_call",
        tool_name=full_tool_name,
        arguments=request.arguments
    )
    
    # 检查是否需要确认
    if tool_request.requires_confirmation and not request.skip_confirmation:
        # 创建确认请求
        confirmation = human_in_loop_service.create_confirmation_request(
            session_id="direct_call",
            tool_call=tool_request
        )
        
        return {
            "status": "confirmation_required",
            "confirmation": human_in_loop_service.format_for_ui(confirmation)
        }
    
    # 执行调用
    result = await mcp_host_service.execute_tool_call(
        tool_request,
        force=request.skip_confirmation
    )
    
    return {
        "success": result.success,
        "result": result.result,
        "error": result.error,
        "execution_time_ms": result.execution_time_ms
    }


# ==================== 服务器管理 ====================

@router.get("/servers")
async def list_servers():
    """
    获取所有 MCP 服务器状态
    
    包括 Stdio 和 SSE 服务器
    """
    stdio_status = stdio_mcp_manager.get_status()
    sse_status = sse_mcp_client.get_status()
    
    return {
        "stdio_servers": stdio_status,
        "sse_servers": sse_status,
        "total_stdio": len(stdio_status),
        "total_sse": len(sse_status)
    }


@router.post("/servers/stdio/{server_key}/start")
async def start_stdio_server(
    request: Request,
    server_key: str,
    command: Optional[str] = Query(default=None),
    args: List[str] = Query(default=[]),
    env: Dict[str, str] = Body(default={})
):
    """启动 Stdio MCP 服务器"""
    def _mask_args(raw_args: List[str]) -> List[str]:
        masked = []
        for item in raw_args:
            if item.startswith("--apiKey="):
                masked.append("--apiKey=***")
            else:
                masked.append(item)
        return masked

    # 如果 query 未提供参数，尝试从 JSON body 读取（兼容旧调用方式）
    if command is None and not args:
        try:
            body = await request.json()
            command = body.get("command") if isinstance(body, dict) else command
            body_args = body.get("args") if isinstance(body, dict) else None
            if isinstance(body_args, list):
                args = body_args
            if isinstance(body, dict) and not env:
                body_env = body.get("env")
                if isinstance(body_env, dict):
                    env = body_env
        except Exception:
            pass

    logger.info(
        "Start stdio server request: server_key=%s command=%s args=%s env_keys=%s query=%s",
        server_key,
        command,
        _mask_args(args),
        sorted(list(env.keys())) if isinstance(env, dict) else [],
        dict(request.query_params)
    )

    if not command:
        raise HTTPException(status_code=400, detail="缺少启动命令参数")

    success, message = await stdio_mcp_manager.start_server(
        server_key=server_key,
        command=command,
        args=args,
        env=env
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message}


@router.post("/servers/stdio/{server_key}/stop")
async def stop_stdio_server(server_key: str):
    """停止 Stdio MCP 服务器"""
    success, message = await stdio_mcp_manager.stop_server(server_key)
    
    return {"success": success, "message": message}


@router.post("/servers/sse/connect")
async def connect_sse_server(config: SSEServerConfig):
    """连接 SSE MCP 服务器"""
    success, message = await sse_mcp_client.connect(
        server_key=config.server_key,
        base_url=config.base_url,
        sse_endpoint=config.sse_endpoint,
        message_endpoint=config.message_endpoint,
        auth_token=config.auth_token,
        auth_type=config.auth_type
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message}


@router.post("/servers/sse/{server_key}/disconnect")
async def disconnect_sse_server(server_key: str):
    """断开 SSE MCP 服务器"""
    success, message = await sse_mcp_client.disconnect(server_key)
    
    return {"success": success, "message": message}


# ==================== 风险策略 ====================

@router.get("/policy")
async def get_risk_policy():
    """获取当前风险策略"""
    policy = human_in_loop_service.policy
    
    return {
        "confirmation_levels": [level.value for level in policy.confirmation_levels],
        "confirmation_timeout": policy.confirmation_timeout,
        "allow_modification": policy.allow_modification,
        "require_double_confirmation": policy.require_double_confirmation,
        "whitelisted_tools": policy.whitelisted_tools,
        "blacklisted_tools": policy.blacklisted_tools
    }


@router.put("/policy")
async def update_risk_policy(
    confirmation_levels: Optional[List[str]] = None,
    confirmation_timeout: Optional[int] = None,
    allow_modification: Optional[bool] = None,
    require_double_confirmation: Optional[bool] = None,
    whitelisted_tools: Optional[List[str]] = None,
    blacklisted_tools: Optional[List[str]] = None
):
    """更新风险策略"""
    policy = human_in_loop_service.policy
    
    if confirmation_levels is not None:
        policy.confirmation_levels = [
            ToolRiskLevel(level) for level in confirmation_levels
        ]
    
    if confirmation_timeout is not None:
        policy.confirmation_timeout = confirmation_timeout
    
    if allow_modification is not None:
        policy.allow_modification = allow_modification
    
    if require_double_confirmation is not None:
        policy.require_double_confirmation = require_double_confirmation
    
    if whitelisted_tools is not None:
        policy.whitelisted_tools = whitelisted_tools
    
    if blacklisted_tools is not None:
        policy.blacklisted_tools = blacklisted_tools
    
    return {"success": True, "policy": await get_risk_policy()}


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """Host 健康检查"""
    stdio_count = len([
        s for s in stdio_mcp_manager.sessions.values()
        if s.process.returncode is None
    ])
    
    sse_count = len([
        s for s in sse_mcp_client.sessions.values()
        if s.state.value == "connected"
    ])
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(mcp_host_service.sessions),
        "connected_stdio_servers": stdio_count,
        "connected_sse_servers": sse_count,
        "pending_confirmations": len(human_in_loop_service.pending_requests)
    }
