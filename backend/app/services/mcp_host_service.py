# app/services/mcp_host_service.py
"""
MCP Host 核心服务
基于 Gemini 报告的架构理念，实现完整的 Host 功能

Host 职责：
1. 管理 LLM 生命周期
2. 聚合多个 MCP Server 的上下文（STDIO + SSE）
3. 处理用户输入
4. 实施权限控制和人机回环
5. 协调 ReAct 循环
6. Roots 路径验证和工作区管理
7. Sampling 能力支持（处理 MCP Server 的 LLM 请求）

传输支持：
- STDIO: 本地进程通信
- SSE: 远程服务器通信
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.services.stdio_mcp_manager import stdio_mcp_manager, MCPSession
from app.services.sse_mcp_client import sse_mcp_client, SSEConnectionState, SSEMCPSession
from app.services.mcp_tools_service import mcp_tools_service, MCPToolInfo

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """传输类型"""
    STDIO = "stdio"
    SSE = "sse"


class ToolRiskLevel(Enum):
    """工具风险等级"""
    LOW = "low"           # 只读操作，无需确认
    MEDIUM = "medium"     # 可能产生副作用，建议确认
    HIGH = "high"         # 危险操作，必须确认
    CRITICAL = "critical" # 极高风险，需要二次确认


@dataclass
class ToolCallRequest:
    """工具调用请求"""
    id: str
    server_key: str
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    requires_confirmation: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ToolCallResult:
    """工具调用结果"""
    id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    was_confirmed: bool = False
    was_rejected: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationMessage:
    """对话消息"""
    role: str  # user, assistant, tool, system
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HostSession:
    """Host 会话"""
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    pending_tool_calls: List[ToolCallRequest] = field(default_factory=list)
    tool_results: Dict[str, ToolCallResult] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    

# 高风险工具关键词映射
HIGH_RISK_KEYWORDS = {
    ToolRiskLevel.CRITICAL: [
        "delete", "remove", "drop", "truncate", "destroy",
        "execute", "exec", "run", "eval", "shell", "command",
        "transfer", "payment", "transaction", "send_money"
    ],
    ToolRiskLevel.HIGH: [
        "write", "update", "modify", "create", "insert",
        "edit", "patch", "put", "post", "upload",
        "install", "uninstall", "deploy"
    ],
    ToolRiskLevel.MEDIUM: [
        "list", "search", "query", "fetch", "download",
        "export", "generate", "convert"
    ]
}


class MCPHostService:
    """
    MCP Host 核心服务
    
    实现完整的 Host 功能：
    1. 多 Server 连接管理
    2. 工具聚合与 Schema 转换
    3. 风险评估与人机回环
    4. 工具调用执行
    """
    
    def __init__(self):
        self.sessions: Dict[str, HostSession] = {}
        self._confirmation_callbacks: Dict[str, Callable[[ToolCallRequest], Awaitable[bool]]] = {}
        self._lock = asyncio.Lock()
        
    def create_session(self, session_id: str) -> HostSession:
        """创建新的 Host 会话"""
        session = HostSession(session_id=session_id)
        self.sessions[session_id] = session
        logger.info(f"Created host session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[HostSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def assess_tool_risk(self, tool_name: str, arguments: Dict[str, Any]) -> ToolRiskLevel:
        """
        评估工具调用的风险等级
        
        基于工具名称和参数进行风险评估
        """
        tool_lower = tool_name.lower()
        
        # 检查 CRITICAL 级别
        for keyword in HIGH_RISK_KEYWORDS[ToolRiskLevel.CRITICAL]:
            if keyword in tool_lower:
                return ToolRiskLevel.CRITICAL
        
        # 检查 HIGH 级别
        for keyword in HIGH_RISK_KEYWORDS[ToolRiskLevel.HIGH]:
            if keyword in tool_lower:
                return ToolRiskLevel.HIGH
        
        # 检查 MEDIUM 级别
        for keyword in HIGH_RISK_KEYWORDS[ToolRiskLevel.MEDIUM]:
            if keyword in tool_lower:
                return ToolRiskLevel.MEDIUM
        
        # 默认 LOW
        return ToolRiskLevel.LOW
    
    def requires_confirmation(self, risk_level: ToolRiskLevel) -> bool:
        """判断是否需要用户确认"""
        return risk_level in [ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL]
    
    async def get_aggregated_tools(self, db=None) -> List[Dict[str, Any]]:
        """
        聚合所有已连接 MCP Server 的工具（STDIO + SSE）
        
        返回 OpenAI Function Calling 格式的工具列表
        """
        tools = []
        
        # 1. 获取所有运行中的 STDIO 服务器的工具
        for server_key, session in stdio_mcp_manager.sessions.items():
            if session.initialized and session.process.returncode is None:
                for tool in session.tools:
                    api_tool = self._convert_to_openai_tool(
                        server_key=server_key,
                        tool=tool,
                        transport_type=TransportType.STDIO
                    )
                    tools.append(api_tool)
        
        # 2. 获取所有已连接的 SSE 服务器的工具
        for server_key, session in sse_mcp_client.sessions.items():
            if session.state == SSEConnectionState.CONNECTED:
                for tool in session.tools:
                    api_tool = self._convert_to_openai_tool(
                        server_key=server_key,
                        tool=tool,
                        transport_type=TransportType.SSE
                    )
                    tools.append(api_tool)
        
        return tools
    
    def _convert_to_openai_tool(
        self,
        server_key: str,
        tool: Dict[str, Any],
        transport_type: TransportType
    ) -> Dict[str, Any]:
        """
        将 MCP 工具转换为 OpenAI Function Calling 格式
        """
        tool_name = tool.get("name", "")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})
        
        # 添加传输类型标识到工具名
        full_name = f"{server_key}__{tool_name}"
        
        # 描述中添加来源信息
        enhanced_desc = f"[{transport_type.value}:{server_key}] {description}" if description else f"Tool from {server_key}"
        
        return {
            "type": "function",
            "function": {
                "name": full_name,
                "description": enhanced_desc,
                "parameters": input_schema if input_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # 内部元数据（不会发送给 LLM）
            "_metadata": {
                "server_key": server_key,
                "original_name": tool_name,
                "transport": transport_type.value
            }
        }
    
    def parse_tool_call(self, tool_name: str) -> tuple[str, str]:
        """
        解析工具调用名称
        
        格式: server_key__tool_name
        """
        if "__" in tool_name:
            parts = tool_name.split("__", 1)
            return parts[0], parts[1]
        return "", tool_name
    
    async def prepare_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        validate_paths: bool = True
    ) -> ToolCallRequest:
        """
        准备工具调用请求
        
        评估风险并决定是否需要用户确认
        
        Args:
            session_id: 会话 ID
            tool_name: 工具名称（格式: server_key__tool_name）
            arguments: 工具参数
            validate_paths: 是否验证路径权限（默认启用）
        """
        server_key, actual_tool_name = self.parse_tool_call(tool_name)
        
        # 验证路径权限（如果启用了 roots）
        path_validation_failed = False
        path_validation_message = ""
        if validate_paths:
            try:
                from app.services.roots_service import roots_service
                all_allowed, validation_results = roots_service.validate_tool_call(
                    server_key, actual_tool_name, arguments
                )
                if not all_allowed:
                    path_validation_failed = True
                    denied_paths = [
                        r.path for r in validation_results 
                        if r.status.value != "allowed"
                    ]
                    path_validation_message = f"路径权限验证失败: {denied_paths}"
                    logger.warning(f"工具调用路径验证失败: {server_key}/{actual_tool_name} - {path_validation_message}")
            except Exception as e:
                logger.error(f"路径验证异常: {e}")
        
        # 评估风险
        risk_level = self.assess_tool_risk(actual_tool_name, arguments)
        
        # 如果路径验证失败，提升风险等级为 CRITICAL
        if path_validation_failed:
            risk_level = ToolRiskLevel.CRITICAL
        
        needs_confirmation = self.requires_confirmation(risk_level)
        
        # 创建请求
        request = ToolCallRequest(
            id=f"{session_id}_{datetime.now().timestamp()}",
            server_key=server_key,
            tool_name=actual_tool_name,
            arguments=arguments,
            risk_level=risk_level,
            requires_confirmation=needs_confirmation
        )
        
        # 如果需要确认，加入待确认队列
        if needs_confirmation:
            session = self.get_session(session_id)
            if session:
                session.pending_tool_calls.append(request)
        
        return request
    
    def _detect_transport_type(self, server_key: str) -> Optional[TransportType]:
        """
        检测服务器使用的传输类型
        """
        # 先检查 STDIO
        if stdio_mcp_manager.is_running(server_key):
            return TransportType.STDIO
        
        # 再检查 SSE
        if sse_mcp_client.is_connected(server_key):
            return TransportType.SSE
        
        return None
    
    async def execute_tool_call(
        self,
        request: ToolCallRequest,
        force: bool = False,
        skip_path_validation: bool = False
    ) -> ToolCallResult:
        """
        执行工具调用（支持 STDIO 和 SSE）
        
        Args:
            request: 工具调用请求
            force: 是否跳过确认（仅用于低风险操作或已确认的操作）
            skip_path_validation: 是否跳过路径验证（仅在已确认的操作中使用）
        """
        start_time = datetime.now()
        
        # 检查是否需要确认但未确认
        if request.requires_confirmation and not force:
            return ToolCallResult(
                id=request.id,
                success=False,
                error="此操作需要用户确认",
                was_rejected=False
            )
        
        # 执行前再次验证路径权限（除非明确跳过）
        if not skip_path_validation:
            try:
                from app.services.roots_service import roots_service
                all_allowed, validation_results = roots_service.validate_tool_call(
                    request.server_key, request.tool_name, request.arguments
                )
                if not all_allowed:
                    denied_results = [r for r in validation_results if r.status.value != "allowed"]
                    error_msg = "路径权限验证失败: " + ", ".join([
                        f"{r.path} ({r.message})" for r in denied_results
                    ])
                    return ToolCallResult(
                        id=request.id,
                        success=False,
                        error=error_msg
                    )
            except Exception as e:
                logger.warning(f"路径验证异常（继续执行）: {e}")
        
        try:
            # 检测传输类型
            transport = self._detect_transport_type(request.server_key)
            
            if transport is None:
                return ToolCallResult(
                    id=request.id,
                    success=False,
                    error=f"MCP 服务器 {request.server_key} 未连接（STDIO 和 SSE 均不可用）"
                )
            
            # 根据传输类型调用工具
            if transport == TransportType.STDIO:
                result = await stdio_mcp_manager.call_tool(
                    request.server_key,
                    request.tool_name,
                    request.arguments
                )
            else:  # SSE
                result = await sse_mcp_client.call_tool(
                    request.server_key,
                    request.tool_name,
                    request.arguments
                )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ToolCallResult(
                id=request.id,
                success=True,
                result=result,
                execution_time_ms=execution_time,
                was_confirmed=request.requires_confirmation
            )
            
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return ToolCallResult(
                id=request.id,
                success=False,
                error=str(e)
            )
    
    async def confirm_tool_call(
        self,
        session_id: str,
        request_id: str,
        approved: bool,
        modified_arguments: Optional[Dict[str, Any]] = None
    ) -> ToolCallResult:
        """
        确认或拒绝工具调用
        
        实现人机回环的核心方法
        """
        session = self.get_session(session_id)
        if not session:
            return ToolCallResult(
                id=request_id,
                success=False,
                error="会话不存在"
            )
        
        # 查找待确认的请求
        request = None
        for pending in session.pending_tool_calls:
            if pending.id == request_id:
                request = pending
                break
        
        if not request:
            return ToolCallResult(
                id=request_id,
                success=False,
                error="找不到待确认的工具调用请求"
            )
        
        # 从待确认队列移除
        session.pending_tool_calls.remove(request)
        
        if not approved:
            result = ToolCallResult(
                id=request_id,
                success=False,
                error="用户拒绝了此操作",
                was_rejected=True
            )
            session.tool_results[request_id] = result
            return result
        
        # 如果用户修改了参数
        if modified_arguments:
            request.arguments = modified_arguments
        
        # 执行调用（用户已确认，跳过路径验证）
        result = await self.execute_tool_call(request, force=True, skip_path_validation=True)
        session.tool_results[request_id] = result
        return result
    
    async def get_pending_confirmations(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """获取待确认的工具调用列表"""
        session = self.get_session(session_id)
        if not session:
            return []
        
        return [
            {
                "id": req.id,
                "server_key": req.server_key,
                "tool_name": req.tool_name,
                "arguments": req.arguments,
                "risk_level": req.risk_level.value,
                "timestamp": req.timestamp.isoformat()
            }
            for req in session.pending_tool_calls
        ]
    
    def get_connected_servers(self) -> Dict[str, Any]:
        """获取所有已连接的 MCP 服务器状态（STDIO + SSE）"""
        result = {
            "stdio": {},
            "sse": {},
            "summary": {
                "stdio_count": 0,
                "sse_count": 0,
                "total_tools": 0
            }
        }
        
        # STDIO 服务器
        stdio_status = stdio_mcp_manager.get_status()
        for key, status in stdio_status.items():
            result["stdio"][key] = {
                **status,
                "transport": "stdio"
            }
            if status.get("running"):
                result["summary"]["stdio_count"] += 1
                result["summary"]["total_tools"] += status.get("tools_count", 0)
        
        # SSE 服务器
        sse_status = sse_mcp_client.get_status()
        for key, status in sse_status.items():
            result["sse"][key] = {
                **status,
                "transport": "sse"
            }
            if status.get("state") == "connected":
                result["summary"]["sse_count"] += 1
                result["summary"]["total_tools"] += status.get("tools_count", 0)
        
        return result
    
    def get_all_server_keys(self) -> List[str]:
        """获取所有已连接服务器的 key 列表"""
        keys = []
        
        # STDIO
        for key, session in stdio_mcp_manager.sessions.items():
            if session.initialized and session.process.returncode is None:
                keys.append(key)
        
        # SSE
        keys.extend(sse_mcp_client.list_connected_servers())
        
        return keys
    
    async def cleanup_session(self, session_id: str):
        """清理会话资源"""
        self.delete_session(session_id)
    
    async def cleanup_all(self):
        """清理所有资源（STDIO + SSE）"""
        self.sessions.clear()
        await stdio_mcp_manager.cleanup()
        await sse_mcp_client.cleanup()
        
        # 清理 roots 服务
        try:
            from app.services.roots_service import roots_service
            await roots_service.cleanup()
        except Exception as e:
            logger.warning(f"清理 roots 服务失败: {e}")
        
        # 清理 sampling 服务
        try:
            from app.services.sampling_service import sampling_service
            await sampling_service.cleanup()
        except Exception as e:
            logger.warning(f"清理 sampling 服务失败: {e}")
        
        logger.info("MCP Host 已清理所有资源")
    
    # ==================== Roots 相关方法 ====================
    
    async def configure_roots(
        self,
        server_key: str,
        roots: List[Dict[str, Any]],
        strict_mode: bool = True
    ):
        """
        配置服务器的根目录
        
        Args:
            server_key: 服务器标识
            roots: 根目录配置列表
            strict_mode: 是否启用严格模式
        """
        from app.services.roots_service import roots_service
        await roots_service.configure_session_roots(server_key, roots, strict_mode)
    
    async def add_root(
        self,
        server_key: str,
        path: str,
        name: Optional[str] = None
    ):
        """向服务器添加根目录"""
        from app.services.roots_service import roots_service
        return await roots_service.add_session_root(server_key, path, name)
    
    async def remove_root(self, server_key: str, path: str) -> bool:
        """从服务器移除根目录"""
        from app.services.roots_service import roots_service
        return await roots_service.remove_session_root(server_key, path)
    
    def get_roots(self, server_key: str) -> List[Dict[str, Any]]:
        """获取服务器的根目录列表"""
        from app.services.roots_service import roots_service
        roots = roots_service.get_session_roots(server_key)
        return [root.to_dict() for root in roots]
    
    def validate_path(self, server_key: str, file_path: str) -> Dict[str, Any]:
        """
        验证文件路径是否在允许的根目录范围内
        
        Returns:
            {"allowed": bool, "message": str, "matched_root": Optional[dict]}
        """
        from app.services.roots_service import roots_service
        result = roots_service.validate_path(server_key, file_path)
        return {
            "allowed": result.status.value == "allowed",
            "status": result.status.value,
            "path": result.path,
            "message": result.message,
            "matched_root": result.matched_root.to_dict() if result.matched_root else None
        }
    
    def get_roots_status(self) -> Dict[str, Any]:
        """获取 Roots 服务状态"""
        from app.services.roots_service import roots_service
        return roots_service.get_status()
    
    # ==================== Sampling 相关方法 ====================
    
    def get_sampling_config(self) -> Dict[str, Any]:
        """获取 Sampling 安全配置"""
        from app.services.sampling_service import sampling_service
        return sampling_service.get_config()
    
    def update_sampling_config(self, config: Dict[str, Any]):
        """
        更新 Sampling 安全配置
        
        Args:
            config: 配置项，可包含:
                - max_tokens_limit: 最大允许的 max_tokens 值
                - rate_limit_per_minute: 每分钟最大请求数
                - rate_limit_per_server: 每个 Server 每分钟最大请求数
                - enable_content_filter: 是否启用内容过滤
                - blocked_keywords: 禁止的关键词列表
                - require_approval: 是否需要人工审核
                - auto_approve_threshold: 自动批准的 token 阈值
                - allowed_servers: 允许使用 Sampling 的 Server 列表
                - blocked_servers: 禁止使用 Sampling 的 Server 列表
        """
        from app.services.sampling_service import sampling_service
        sampling_service.update_config(config)
        logger.info(f"Sampling 配置已更新: {config}")
    
    def get_sampling_status(self) -> Dict[str, Any]:
        """获取 Sampling 服务状态"""
        from app.services.sampling_service import sampling_service
        return sampling_service.get_status()
    
    def get_pending_sampling_requests(self) -> List[Dict[str, Any]]:
        """获取待审核的 Sampling 请求列表"""
        from app.services.sampling_service import sampling_service
        return sampling_service.get_pending_requests()
    
    async def approve_sampling_request(
        self,
        request_id: str,
        modified_params: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        批准 Sampling 请求
        
        Args:
            request_id: 请求 ID
            modified_params: 用户修改后的参数（可选）
            llm_config: LLM 配置
            
        Returns:
            处理结果
        """
        from app.services.sampling_service import sampling_service
        return await sampling_service.approve_request(request_id, modified_params, llm_config)
    
    async def reject_sampling_request(
        self,
        request_id: str,
        reason: str = "用户拒绝了此请求"
    ) -> Dict[str, Any]:
        """
        拒绝 Sampling 请求
        
        Args:
            request_id: 请求 ID
            reason: 拒绝原因
            
        Returns:
            处理结果
        """
        from app.services.sampling_service import sampling_service
        return await sampling_service.reject_request(request_id, reason)
    
    async def cleanup_expired_sampling_requests(self) -> List[str]:
        """清理过期的 Sampling 请求"""
        from app.services.sampling_service import sampling_service
        return await sampling_service.cleanup_expired_requests()
    
    def get_servers_with_sampling(self) -> List[Dict[str, Any]]:
        """
        获取所有启用了 Sampling 能力的服务器
        
        Returns:
            服务器列表，包含 server_key 和 sampling 状态
        """
        result = []
        
        # STDIO 服务器
        for server_key, session in stdio_mcp_manager.sessions.items():
            if session.sampling_enabled:
                result.append({
                    "server_key": server_key,
                    "transport": "stdio",
                    "sampling_enabled": True,
                    "listener_active": session.listener_task is not None and not session.listener_task.done()
                })
        
        # SSE 服务器
        for server_key, session in sse_mcp_client.sessions.items():
            if session.sampling_enabled:
                result.append({
                    "server_key": server_key,
                    "transport": "sse",
                    "sampling_enabled": True,
                    "connected": session.state == SSEConnectionState.CONNECTED
                })
        
        return result


# 创建全局单例
mcp_host_service = MCPHostService()

