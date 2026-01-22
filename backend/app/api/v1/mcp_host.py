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
    max_iterations: int = 5
    stream: bool = True


class ConfirmationRequest(BaseModel):
    """确认请求"""
    approved: bool
    modified_arguments: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class RootConfig(BaseModel):
    """根目录配置"""
    path: str = Field(..., description="根目录路径")
    name: Optional[str] = Field(None, description="根目录名称")
    type: str = Field("custom", description="根目录类型: project, workspace, resource, custom")


class SSEServerConfig(BaseModel):
    """SSE 服务器配置"""
    server_key: str
    base_url: str
    sse_endpoint: str = "/sse"
    message_endpoint: str = "/message"
    auth_token: Optional[str] = None
    auth_type: str = "bearer"
    roots: Optional[List[RootConfig]] = Field(None, description="根目录配置")


class ToolCallRequest(BaseModel):
    """直接工具调用请求"""
    server_key: str
    tool_name: str
    arguments: Dict[str, Any] = {}
    skip_confirmation: bool = False


class ConfigureRootsRequest(BaseModel):
    """配置根目录请求"""
    roots: List[RootConfig] = Field(..., description="根目录配置列表")
    strict_mode: bool = Field(True, description="是否启用严格模式")


class ValidatePathRequest(BaseModel):
    """路径验证请求"""
    path: str = Field(..., description="要验证的文件路径")


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
    logger.info(
        "MCP Host chat request: session_id=%s provider=%s model=%s max_iterations=%s",
        session_id,
        request.llm_provider,
        request.llm_model,
        request.max_iterations
    )
    # 构建 LLM 配置
    llm_config = LLMConfig(
        provider=request.llm_provider,
        model=request.llm_model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )
    
    context = react_engine.get_context(session_id)
    if not context:
        context = react_engine.create_context(session_id)
    context.max_iterations = request.max_iterations

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


class StartStdioServerRequest(BaseModel):
    """启动 STDIO 服务器请求"""
    command: str = Field(..., description="启动命令")
    args: List[str] = Field(default=[], description="命令参数")
    env: Dict[str, str] = Field(default={}, description="环境变量")
    roots: Optional[List[RootConfig]] = Field(None, description="根目录配置")


@router.post("/servers/stdio/{server_key}/start")
async def start_stdio_server(
    request: Request,
    server_key: str,
    command: Optional[str] = Query(default=None),
    args: List[str] = Query(default=[]),
    env: Dict[str, str] = Body(default={})
):
    """
    启动 Stdio MCP 服务器
    
    支持可选的 roots 配置来限制服务器的文件访问范围
    """
    def _mask_args(raw_args: List[str]) -> List[str]:
        masked = []
        for item in raw_args:
            if item.startswith("--apiKey="):
                masked.append("--apiKey=***")
            else:
                masked.append(item)
        return masked

    roots_config = None
    
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
            # 解析 roots 配置
            if isinstance(body, dict):
                body_roots = body.get("roots")
                if isinstance(body_roots, list):
                    roots_config = [
                        {"path": r.get("path"), "name": r.get("name"), "type": r.get("type", "custom")}
                        for r in body_roots if isinstance(r, dict) and r.get("path")
                    ]
        except Exception:
            pass

    logger.info(
        "Start stdio server request: server_key=%s command=%s args=%s env_keys=%s roots=%s query=%s",
        server_key,
        command,
        _mask_args(args),
        sorted(list(env.keys())) if isinstance(env, dict) else [],
        len(roots_config) if roots_config else 0,
        dict(request.query_params)
    )

    if not command:
        raise HTTPException(status_code=400, detail="缺少启动命令参数")

    success, message = await stdio_mcp_manager.start_server(
        server_key=server_key,
        command=command,
        args=args,
        env=env,
        roots_config=roots_config
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message, "roots_configured": bool(roots_config)}


@router.post("/servers/stdio/{server_key}/stop")
async def stop_stdio_server(server_key: str):
    """停止 Stdio MCP 服务器"""
    success, message = await stdio_mcp_manager.stop_server(server_key)
    
    return {"success": success, "message": message}


@router.post("/servers/sse/connect")
async def connect_sse_server(config: SSEServerConfig):
    """
    连接 SSE MCP 服务器
    
    支持可选的 roots 配置来限制服务器的文件访问范围
    """
    # 转换 roots 配置
    roots_config = None
    if config.roots:
        roots_config = [
            {"path": r.path, "name": r.name, "type": r.type}
            for r in config.roots
        ]
    
    success, message = await sse_mcp_client.connect(
        server_key=config.server_key,
        base_url=config.base_url,
        sse_endpoint=config.sse_endpoint,
        message_endpoint=config.message_endpoint,
        auth_token=config.auth_token,
        auth_type=config.auth_type,
        roots_config=roots_config
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message, "roots_configured": bool(roots_config)}


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


# ==================== Roots 管理（工作区目录） ====================

@router.get("/servers/{server_key}/roots")
async def get_server_roots(server_key: str):
    """
    获取服务器的根目录列表
    
    根目录定义了 MCP 服务器可以访问的文件系统范围
    """
    from app.services.roots_service import roots_service
    
    roots = roots_service.get_session_roots(server_key)
    
    return {
        "server_key": server_key,
        "count": len(roots),
        "roots": [
            {
                "uri": root.uri,
                "name": root.name,
                "path": root.path,
                "type": root.root_type.value
            }
            for root in roots
        ]
    }


@router.put("/servers/{server_key}/roots")
async def configure_server_roots(server_key: str, request: ConfigureRootsRequest):
    """
    配置服务器的根目录
    
    这将替换现有的所有根目录配置
    """
    from app.services.roots_service import roots_service
    
    # 转换为内部格式
    roots_config = [
        {"path": r.path, "name": r.name, "type": r.type}
        for r in request.roots
    ]
    
    config = await roots_service.configure_session_roots(
        server_key,
        roots_config,
        strict_mode=request.strict_mode
    )
    
    # 发送 roots/list_changed 通知
    if stdio_mcp_manager.is_running(server_key):
        await stdio_mcp_manager.send_roots_list_changed(server_key)
    elif sse_mcp_client.is_connected(server_key):
        await sse_mcp_client.send_roots_list_changed(server_key)
    
    return {
        "success": True,
        "server_key": server_key,
        "roots_count": len(config.roots),
        "strict_mode": config.strict_mode
    }


@router.post("/servers/{server_key}/roots")
async def add_server_root(server_key: str, root: RootConfig):
    """
    向服务器添加根目录
    """
    from app.services.roots_service import roots_service
    from app.services.roots_service import RootType
    
    new_root = await roots_service.add_session_root(
        server_key,
        root.path,
        root.name,
        RootType(root.type)
    )
    
    # 发送 roots/list_changed 通知
    if stdio_mcp_manager.is_running(server_key):
        await stdio_mcp_manager.send_roots_list_changed(server_key)
    elif sse_mcp_client.is_connected(server_key):
        await sse_mcp_client.send_roots_list_changed(server_key)
    
    return {
        "success": True,
        "root": {
            "uri": new_root.uri,
            "name": new_root.name,
            "path": new_root.path,
            "type": new_root.root_type.value
        }
    }


@router.delete("/servers/{server_key}/roots")
async def remove_server_root(server_key: str, path: str = Query(..., description="要移除的根目录路径")):
    """
    从服务器移除根目录
    """
    from app.services.roots_service import roots_service
    
    success = await roots_service.remove_session_root(server_key, path)
    
    if success:
        # 发送 roots/list_changed 通知
        if stdio_mcp_manager.is_running(server_key):
            await stdio_mcp_manager.send_roots_list_changed(server_key)
        elif sse_mcp_client.is_connected(server_key):
            await sse_mcp_client.send_roots_list_changed(server_key)
    
    return {
        "success": success,
        "message": "根目录已移除" if success else "未找到指定的根目录"
    }


@router.post("/servers/{server_key}/validate-path")
async def validate_path(server_key: str, request: ValidatePathRequest):
    """
    验证文件路径是否在允许的根目录范围内
    
    返回验证结果和匹配的根目录（如果有）
    """
    from app.services.roots_service import roots_service
    
    result = roots_service.validate_path(server_key, request.path)
    
    return {
        "allowed": result.status.value == "allowed",
        "status": result.status.value,
        "path": result.path,
        "message": result.message,
        "matched_root": {
            "uri": result.matched_root.uri,
            "name": result.matched_root.name,
            "path": result.matched_root.path
        } if result.matched_root else None
    }


@router.get("/roots/status")
async def get_roots_status():
    """
    获取 Roots 服务的整体状态
    
    包括全局根目录和所有会话的根目录配置
    """
    from app.services.roots_service import roots_service
    
    return roots_service.get_status()


@router.post("/roots/global")
async def add_global_root(root: RootConfig):
    """
    添加全局根目录
    
    全局根目录会应用于所有 MCP 服务器
    """
    from app.services.roots_service import roots_service
    from app.services.roots_service import RootType
    
    new_root = roots_service.add_global_root(
        root.path,
        root.name,
        RootType(root.type)
    )
    
    return {
        "success": True,
        "root": {
            "uri": new_root.uri,
            "name": new_root.name,
            "path": new_root.path,
            "type": new_root.root_type.value
        }
    }


@router.delete("/roots/global")
async def remove_global_root(path: str = Query(..., description="要移除的全局根目录路径")):
    """
    移除全局根目录
    """
    from app.services.roots_service import roots_service
    
    success = roots_service.remove_global_root(path)
    
    return {
        "success": success,
        "message": "全局根目录已移除" if success else "未找到指定的全局根目录"
    }


@router.get("/roots/global")
async def get_global_roots():
    """
    获取全局根目录列表
    """
    from app.services.roots_service import roots_service
    
    roots = roots_service.get_global_roots()
    
    return {
        "count": len(roots),
        "roots": [
            {
                "uri": root.uri,
                "name": root.name,
                "path": root.path,
                "type": root.root_type.value
            }
            for root in roots
        ]
    }


# ==================== Sampling 管理（服务端请求 LLM） ====================

class SamplingConfigRequest(BaseModel):
    """Sampling 安全配置请求"""
    max_tokens_limit: Optional[int] = Field(None, description="最大允许的 max_tokens 值")
    default_max_tokens: Optional[int] = Field(None, description="默认 max_tokens")
    rate_limit_per_minute: Optional[int] = Field(None, description="每分钟最大请求数")
    rate_limit_per_server: Optional[int] = Field(None, description="每个 Server 每分钟最大请求数")
    enable_content_filter: Optional[bool] = Field(None, description="是否启用内容过滤")
    blocked_keywords: Optional[List[str]] = Field(None, description="禁止的关键词列表")
    require_approval: Optional[bool] = Field(None, description="是否需要人工审核")
    auto_approve_threshold: Optional[int] = Field(None, description="自动批准的 token 阈值")
    approval_timeout_seconds: Optional[int] = Field(None, description="审核超时时间（秒）")
    allowed_servers: Optional[List[str]] = Field(None, description="允许使用 Sampling 的 Server 列表")
    blocked_servers: Optional[List[str]] = Field(None, description="禁止使用 Sampling 的 Server 列表")


class ApproveSamplingRequest(BaseModel):
    """批准 Sampling 请求"""
    modified_params: Optional[Dict[str, Any]] = Field(None, description="用户修改后的参数")
    llm_config: Optional[Dict[str, Any]] = Field(None, description="LLM 配置")


class RejectSamplingRequest(BaseModel):
    """拒绝 Sampling 请求"""
    reason: str = Field("用户拒绝了此请求", description="拒绝原因")


@router.get("/sampling/config")
async def get_sampling_config():
    """
    获取 Sampling 安全配置
    
    Sampling 允许 MCP Server 请求 Host 调用 LLM。
    安全配置用于控制和限制这些请求。
    """
    return mcp_host_service.get_sampling_config()


@router.put("/sampling/config")
async def update_sampling_config(request: SamplingConfigRequest):
    """
    更新 Sampling 安全配置
    
    可配置的选项：
    - max_tokens_limit: 单次请求允许的最大 token 数
    - rate_limit_per_minute: 全局速率限制
    - rate_limit_per_server: 每个 Server 的速率限制
    - require_approval: 是否需要人工审核
    - blocked_keywords: 内容过滤关键词
    - allowed_servers / blocked_servers: Server 白名单/黑名单
    """
    config = request.model_dump(exclude_none=True)
    mcp_host_service.update_sampling_config(config)
    
    return {
        "success": True,
        "config": mcp_host_service.get_sampling_config()
    }


@router.get("/sampling/status")
async def get_sampling_status():
    """
    获取 Sampling 服务状态
    
    返回当前配置、待审核请求数、速率限制状态等
    """
    return mcp_host_service.get_sampling_status()


@router.get("/sampling/requests")
async def get_pending_sampling_requests():
    """
    获取待审核的 Sampling 请求列表
    
    当 require_approval 为 true 且请求 token 数超过 auto_approve_threshold 时，
    请求会进入待审核队列。
    """
    requests = mcp_host_service.get_pending_sampling_requests()
    
    return {
        "count": len(requests),
        "requests": requests
    }


@router.post("/sampling/requests/{request_id}/approve")
async def approve_sampling_request(
    request_id: str,
    request: ApproveSamplingRequest = Body(default=ApproveSamplingRequest())
):
    """
    批准 Sampling 请求
    
    批准后将调用 LLM 并将结果返回给发起请求的 MCP Server。
    可以在批准时修改请求参数（如 max_tokens、temperature 等）。
    """
    result = await mcp_host_service.approve_sampling_request(
        request_id,
        modified_params=request.modified_params,
        llm_config=request.llm_config
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=400 if result["error"].get("code") == -32602 else 500,
            detail=result["error"].get("message", "处理请求时发生错误")
        )
    
    return {
        "success": True,
        "result": result.get("result")
    }


@router.post("/sampling/requests/{request_id}/reject")
async def reject_sampling_request(
    request_id: str,
    request: RejectSamplingRequest = Body(default=RejectSamplingRequest())
):
    """
    拒绝 Sampling 请求
    
    拒绝后会向发起请求的 MCP Server 返回错误响应。
    """
    result = await mcp_host_service.reject_sampling_request(
        request_id,
        reason=request.reason
    )
    
    if "error" not in result:
        raise HTTPException(status_code=500, detail="拒绝操作应返回错误响应")
    
    return {
        "success": True,
        "message": f"请求已拒绝: {request.reason}"
    }


@router.post("/sampling/cleanup")
async def cleanup_expired_sampling_requests():
    """
    清理过期的 Sampling 请求
    
    超过 approval_timeout_seconds 的请求会被自动标记为过期。
    调用此接口可以手动触发清理。
    """
    expired_ids = await mcp_host_service.cleanup_expired_sampling_requests()
    
    return {
        "success": True,
        "expired_count": len(expired_ids),
        "expired_ids": expired_ids
    }


@router.get("/sampling/servers")
async def get_servers_with_sampling():
    """
    获取所有启用了 Sampling 能力的服务器
    
    返回支持 Sampling 的 MCP Server 列表及其状态
    """
    servers = mcp_host_service.get_servers_with_sampling()
    
    return {
        "count": len(servers),
        "servers": servers
    }


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
    
    # 获取 roots 服务状态
    from app.services.roots_service import roots_service
    roots_status = roots_service.get_status()
    
    # 获取 sampling 服务状态
    sampling_status = mcp_host_service.get_sampling_status()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(mcp_host_service.sessions),
        "connected_stdio_servers": stdio_count,
        "connected_sse_servers": sse_count,
        "pending_confirmations": len(human_in_loop_service.pending_requests),
        "roots": {
            "global_roots_count": len(roots_status.get("global_roots", [])),
            "session_roots_count": len(roots_status.get("sessions", {}))
        },
        "sampling": {
            "enabled": sampling_status.get("enabled", False),
            "pending_requests": sampling_status.get("pending_requests_count", 0)
        }
    }
