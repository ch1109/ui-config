# app/services/sse_mcp_client.py
"""
SSE (Server-Sent Events) MCP 客户端
支持远程 MCP 服务器的双向通信

SSE 传输特点（来自 Gemini 报告）：
1. 使用 HTTP/1.1 或 HTTP/2
2. 客户端发起 GET 请求建立 SSE 连接接收服务端推送
3. 使用独立的 POST 请求发送指令
4. 支持多客户端连接同一服务器
5. 服务器可以独立运行（松耦合）

增强功能：
- 指数退避重连机制
- 连接健康检查
- 心跳保活
- 详细的连接状态管理
- MCP Roots 能力支持
- MCP Sampling 能力支持
"""

import asyncio
import json
import logging
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
import random

logger = logging.getLogger(__name__)

# ========== 配置常量 ==========
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_REQUEST_TIMEOUT = 60.0
DEFAULT_HEARTBEAT_INTERVAL = 30.0  # 心跳间隔（秒）
MAX_RECONNECT_ATTEMPTS = 5
INITIAL_RECONNECT_DELAY = 1.0  # 初始重连延迟（秒）
MAX_RECONNECT_DELAY = 60.0  # 最大重连延迟（秒）


class SSEConnectionState(Enum):
    """SSE 连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class SSEMessage:
    """SSE 消息"""
    event: str = "message"
    data: str = ""
    id: Optional[str] = None
    retry: Optional[int] = None


@dataclass
class SSEMCPSession:
    """SSE MCP 会话"""
    server_key: str
    base_url: str
    sse_endpoint: str = "/sse"
    message_endpoint: str = "/message"
    
    # 认证
    auth_token: Optional[str] = None
    auth_type: str = "bearer"  # bearer, api_key, custom
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    # 状态
    state: SSEConnectionState = SSEConnectionState.DISCONNECTED
    session_id: Optional[str] = None
    request_id: int = 0
    error_message: Optional[str] = None
    
    # 重连配置
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS
    last_reconnect_attempt: Optional[datetime] = None
    
    # 能力
    server_info: Dict[str, Any] = field(default_factory=dict)
    server_capabilities: Dict[str, Any] = field(default_factory=dict)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[Dict[str, Any]] = field(default_factory=list)
    roots_enabled: bool = False  # 是否启用了 roots
    sampling_enabled: bool = False  # 是否启用了 sampling
    
    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    connected_at: Optional[datetime] = None
    
    # 待处理的响应
    pending_responses: Dict[int, asyncio.Future] = field(default_factory=dict)
    
    # 健康检查
    last_heartbeat: Optional[datetime] = None
    heartbeat_failures: int = 0


class SSEMCPClient:
    """
    SSE MCP 客户端
    
    实现基于 SSE 的 MCP 通信协议
    
    增强功能：
    - 自动重连（指数退避）
    - 心跳保活
    - 连接健康监控
    - 详细状态跟踪
    """
    
    def __init__(self):
        self.sessions: Dict[str, SSEMCPSession] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sse_tasks: Dict[str, asyncio.Task] = {}
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._lock: Optional[asyncio.Lock] = None  # 延迟初始化
        self._event_callbacks: Dict[str, List[Callable]] = {}
    
    def _get_lock(self) -> asyncio.Lock:
        """获取或创建锁（延迟初始化以避免事件循环问题）"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=DEFAULT_REQUEST_TIMEOUT,
                    write=DEFAULT_REQUEST_TIMEOUT,
                    pool=DEFAULT_REQUEST_TIMEOUT
                ),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
        return self._http_client
    
    def _calculate_reconnect_delay(self, attempts: int) -> float:
        """计算重连延迟（指数退避 + 抖动）"""
        delay = min(
            INITIAL_RECONNECT_DELAY * (2 ** attempts),
            MAX_RECONNECT_DELAY
        )
        # 添加随机抖动（±25%）
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        return delay + jitter
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """注册事件回调"""
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """触发事件"""
        if event_type in self._event_callbacks:
            for callback in self._event_callbacks[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
    
    def _get_auth_headers(self, session: SSEMCPSession) -> Dict[str, str]:
        """获取认证头"""
        headers = {}
        
        if session.auth_token:
            if session.auth_type == "bearer":
                headers["Authorization"] = f"Bearer {session.auth_token}"
            elif session.auth_type == "api_key":
                headers["X-API-Key"] = session.auth_token
            else:
                headers["Authorization"] = session.auth_token
        
        return headers
    
    async def connect(
        self,
        server_key: str,
        base_url: str,
        sse_endpoint: str = "/sse",
        message_endpoint: str = "/message",
        auth_token: Optional[str] = None,
        auth_type: str = "bearer",
        custom_headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS,
        roots_config: Optional[List[Dict[str, Any]]] = None
    ) -> tuple[bool, str]:
        """
        连接到 SSE MCP 服务器
        
        Args:
            server_key: 服务器唯一标识
            base_url: 服务器基础 URL
            sse_endpoint: SSE 端点路径
            message_endpoint: 消息端点路径
            auth_token: 认证令牌
            auth_type: 认证类型 (bearer, api_key, custom)
            custom_headers: 自定义请求头
            timeout: 连接超时时间
            auto_reconnect: 是否自动重连
            max_reconnect_attempts: 最大重连次数
            roots_config: 可选的根目录配置，格式: [{"path": "/path/to/dir", "name": "名称"}, ...]
            
        Returns:
            (success, message)
        """
        async with self._get_lock():
            # 检查是否已连接
            if server_key in self.sessions:
                session = self.sessions[server_key]
                if session.state == SSEConnectionState.CONNECTED:
                    return True, "已连接"
                # 如果正在连接，等待连接完成
                if session.state == SSEConnectionState.CONNECTING:
                    try:
                        await asyncio.wait_for(
                            self._wait_for_connection(session),
                            timeout=timeout
                        )
                        return True, "已连接"
                    except asyncio.TimeoutError:
                        pass
            
            # 创建会话
            session = SSEMCPSession(
                server_key=server_key,
                base_url=base_url.rstrip("/"),
                sse_endpoint=sse_endpoint,
                message_endpoint=message_endpoint,
                auth_token=auth_token,
                auth_type=auth_type,
                custom_headers=custom_headers or {},
                state=SSEConnectionState.CONNECTING,
                max_reconnect_attempts=max_reconnect_attempts if auto_reconnect else 0
            )
            self.sessions[server_key] = session
            
            # 配置会话的 roots（如果提供）
            if roots_config:
                from app.services.roots_service import roots_service
                await roots_service.configure_session_roots(
                    server_key,
                    roots_config,
                    strict_mode=True
                )
                session.roots_enabled = True
            
            try:
                # 启动 SSE 连接
                sse_task = asyncio.create_task(
                    self._sse_listener(session, auto_reconnect)
                )
                self._sse_tasks[server_key] = sse_task
                
                # 等待连接建立
                await asyncio.wait_for(
                    self._wait_for_connection(session),
                    timeout=timeout
                )
                
                # 初始化 MCP 会话
                await self._initialize(session, roots_config)
                
                # 启动心跳任务
                heartbeat_task = asyncio.create_task(
                    self._heartbeat_loop(session)
                )
                self._heartbeat_tasks[server_key] = heartbeat_task
                
                session.connected_at = datetime.now()
                session.error_message = None
                
                # 触发连接成功事件
                await self._emit_event("connected", {
                    "server_key": server_key,
                    "base_url": base_url
                })
                
                logger.info(f"SSE MCP 客户端已连接: {server_key} -> {base_url}")
                return True, f"已连接到 {base_url}"
                
            except asyncio.TimeoutError:
                session.state = SSEConnectionState.ERROR
                session.error_message = "连接超时"
                await self.disconnect(server_key)
                return False, "连接超时"
            except Exception as e:
                session.state = SSEConnectionState.ERROR
                session.error_message = str(e)
                await self.disconnect(server_key)
                return False, f"连接失败: {str(e)}"
    
    async def _wait_for_connection(self, session: SSEMCPSession):
        """等待 SSE 连接建立"""
        while session.state == SSEConnectionState.CONNECTING:
            await asyncio.sleep(0.1)
        
        if session.state != SSEConnectionState.CONNECTED:
            raise Exception("连接失败")
    
    async def _sse_listener(self, session: SSEMCPSession, auto_reconnect: bool = True):
        """
        SSE 事件监听器
        持续接收服务端推送的消息
        
        支持自动重连（指数退避）
        """
        client = await self._get_http_client()
        url = f"{session.base_url}{session.sse_endpoint}"
        
        while True:
            headers = self._get_auth_headers(session)
            headers["Accept"] = "text/event-stream"
            headers["Cache-Control"] = "no-cache"
            
            try:
                async with client.stream(
                    "GET",
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(
                        connect=DEFAULT_CONNECT_TIMEOUT,
                        read=None,  # SSE 连接不应超时
                        write=DEFAULT_REQUEST_TIMEOUT,
                        pool=DEFAULT_REQUEST_TIMEOUT
                    )
                ) as response:
                    if response.status_code != 200:
                        error_text = f"SSE 连接失败: HTTP {response.status_code}"
                        logger.error(f"{error_text} for {session.server_key}")
                        session.state = SSEConnectionState.ERROR
                        session.error_message = error_text
                        
                        if not auto_reconnect or not await self._should_reconnect(session):
                            break
                        continue
                    
                    # 连接成功，重置重连计数
                    session.state = SSEConnectionState.CONNECTED
                    session.reconnect_attempts = 0
                    session.error_message = None
                    logger.info(f"SSE 已连接: {session.server_key} -> {url}")
                    
                    # 触发重连成功事件（如果是重连）
                    if session.last_reconnect_attempt:
                        await self._emit_event("reconnected", {
                            "server_key": session.server_key
                        })
                    
                    # 解析 SSE 消息
                    async for message in self._parse_sse_stream(response):
                        await self._handle_sse_message(session, message)
                        session.last_activity = datetime.now()
                        
            except httpx.ReadTimeout:
                logger.debug(f"SSE 读取超时: {session.server_key}")
                if session.state == SSEConnectionState.CONNECTED:
                    session.state = SSEConnectionState.RECONNECTING
                    session.last_reconnect_attempt = datetime.now()
                
                if not auto_reconnect or not await self._should_reconnect(session):
                    break
                continue
                
            except httpx.ConnectError as e:
                error_msg = f"SSE 连接错误: {e}"
                logger.error(f"{error_msg} for {session.server_key}")
                session.state = SSEConnectionState.ERROR
                session.error_message = error_msg
                
                if not auto_reconnect or not await self._should_reconnect(session):
                    break
                continue
                
            except asyncio.CancelledError:
                logger.info(f"SSE 监听器已取消: {session.server_key}")
                break
                
            except Exception as e:
                error_msg = f"SSE 未知错误: {e}"
                logger.error(f"{error_msg} for {session.server_key}")
                session.state = SSEConnectionState.ERROR
                session.error_message = error_msg
                
                if not auto_reconnect or not await self._should_reconnect(session):
                    break
                continue
    
    async def _should_reconnect(self, session: SSEMCPSession) -> bool:
        """判断是否应该重连"""
        if session.reconnect_attempts >= session.max_reconnect_attempts:
            logger.warning(
                f"SSE 达到最大重连次数 ({session.max_reconnect_attempts}): {session.server_key}"
            )
            session.state = SSEConnectionState.ERROR
            session.error_message = f"达到最大重连次数 ({session.max_reconnect_attempts})"
            
            await self._emit_event("connection_failed", {
                "server_key": session.server_key,
                "attempts": session.reconnect_attempts,
                "error": session.error_message
            })
            return False
        
        session.reconnect_attempts += 1
        session.last_reconnect_attempt = datetime.now()
        session.state = SSEConnectionState.RECONNECTING
        
        delay = self._calculate_reconnect_delay(session.reconnect_attempts)
        logger.info(
            f"SSE 将在 {delay:.1f}s 后重连 (尝试 {session.reconnect_attempts}/{session.max_reconnect_attempts}): {session.server_key}"
        )
        
        await self._emit_event("reconnecting", {
            "server_key": session.server_key,
            "attempt": session.reconnect_attempts,
            "delay": delay
        })
        
        await asyncio.sleep(delay)
        return True
    
    async def _heartbeat_loop(self, session: SSEMCPSession):
        """心跳保活循环"""
        while True:
            try:
                await asyncio.sleep(DEFAULT_HEARTBEAT_INTERVAL)
                
                if session.state != SSEConnectionState.CONNECTED:
                    continue
                
                # 检查最后活动时间
                if session.last_activity:
                    inactive_time = (datetime.now() - session.last_activity).total_seconds()
                    if inactive_time > DEFAULT_HEARTBEAT_INTERVAL * 3:
                        logger.warning(f"SSE 连接可能已断开 (无活动 {inactive_time:.0f}s): {session.server_key}")
                        session.heartbeat_failures += 1
                        
                        if session.heartbeat_failures >= 3:
                            logger.error(f"SSE 心跳失败次数过多，标记为断开: {session.server_key}")
                            session.state = SSEConnectionState.ERROR
                            await self._emit_event("heartbeat_failed", {
                                "server_key": session.server_key
                            })
                    else:
                        session.heartbeat_failures = 0
                
                session.last_heartbeat = datetime.now()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳循环错误: {e}")
    
    async def _parse_sse_stream(
        self,
        response: httpx.Response
    ) -> AsyncGenerator[SSEMessage, None]:
        """解析 SSE 流"""
        current_message = SSEMessage()
        
        async for line in response.aiter_lines():
            if not line:
                # 空行表示消息结束
                if current_message.data:
                    yield current_message
                    current_message = SSEMessage()
                continue
            
            if line.startswith(":"):
                # 注释行，忽略
                continue
            
            if ":" in line:
                field, _, value = line.partition(":")
                value = value.lstrip()
                
                if field == "event":
                    current_message.event = value
                elif field == "data":
                    if current_message.data:
                        current_message.data += "\n"
                    current_message.data += value
                elif field == "id":
                    current_message.id = value
                elif field == "retry":
                    try:
                        current_message.retry = int(value)
                    except ValueError:
                        pass
    
    async def _handle_sse_message(
        self,
        session: SSEMCPSession,
        message: SSEMessage
    ):
        """处理 SSE 消息"""
        try:
            data = json.loads(message.data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in SSE message: {message.data}")
            return
        
        # 处理 JSON-RPC 响应
        if "id" in data and "result" in data:
            request_id = data["id"]
            if request_id in session.pending_responses:
                future = session.pending_responses.pop(request_id)
                future.set_result(data.get("result", {}))
        
        elif "id" in data and "error" in data:
            request_id = data["id"]
            if request_id in session.pending_responses:
                future = session.pending_responses.pop(request_id)
                error = data["error"]
                future.set_exception(
                    Exception(f"MCP Error [{error.get('code')}]: {error.get('message')}")
                )
        
        # 处理服务器发起的请求（如 roots/list）
        elif "id" in data and "method" in data:
            request_id = data["id"]
            method = data["method"]
            params = data.get("params", {})
            await self._handle_sse_request(session, request_id, method, params)
        
        # 处理通知
        elif "method" in data and "id" not in data:
            method = data["method"]
            params = data.get("params", {})
            await self._handle_notification(session, method, params)
        
        session.last_activity = datetime.now()
    
    async def _handle_notification(
        self,
        session: SSEMCPSession,
        method: str,
        params: Dict[str, Any]
    ):
        """处理服务器通知"""
        if method == "notifications/tools/list_changed":
            # 工具列表变更，刷新
            try:
                await self._refresh_tools(session)
            except Exception as e:
                logger.error(f"Failed to refresh tools: {e}")
        
        elif method == "notifications/resources/list_changed":
            try:
                await self._refresh_resources(session)
            except Exception as e:
                logger.error(f"Failed to refresh resources: {e}")
        
        elif method == "notifications/message":
            # 日志消息
            level = params.get("level", "info")
            message = params.get("data", "")
            logger.log(
                getattr(logging, level.upper(), logging.INFO),
                f"[{session.server_key}] {message}"
            )
    
    async def _handle_sse_request(
        self,
        session: SSEMCPSession,
        request_id: int,
        method: str,
        params: Dict[str, Any]
    ):
        """
        处理来自服务器的请求
        
        支持的请求：
        - roots/list: 请求根目录列表
        - sampling/createMessage: 请求 Host 调用 LLM
        """
        logger.info(f"收到 SSE 服务器请求: {session.server_key} - {method}")
        
        if method == "roots/list":
            # 服务器请求根目录列表
            try:
                roots = await self.handle_roots_list_request(session.server_key)
                await self._send_response(session, request_id, {"roots": roots})
            except Exception as e:
                logger.error(f"处理 roots/list 请求失败: {e}")
                await self._send_error_response(session, request_id, -32603, str(e))
        
        elif method == "sampling/createMessage":
            # 服务器请求 Host 调用 LLM
            await self._handle_sampling_request(session, request_id, params)
        
        else:
            # 未知的请求方法
            logger.warning(f"收到未知的服务器请求: {method}")
            await self._send_error_response(session, request_id, -32601, f"未知方法: {method}")
    
    async def _handle_sampling_request(
        self,
        session: SSEMCPSession,
        request_id: int,
        params: Dict[str, Any]
    ):
        """
        处理 sampling/createMessage 请求
        
        将请求转发给 sampling_service 处理
        """
        if not session.sampling_enabled:
            await self._send_error_response(
                session,
                request_id,
                -32600,
                "Sampling capability not enabled for this session"
            )
            return
        
        try:
            from app.services.sampling_service import sampling_service
            
            # 调用 sampling_service 处理请求
            result = await sampling_service.handle_sampling_request(
                server_key=session.server_key,
                jsonrpc_id=request_id,
                params=params
            )
            
            # 发送响应
            if "error" in result:
                await self._send_error_response(
                    session,
                    request_id,
                    result["error"].get("code", -32603),
                    result["error"].get("message", "Unknown error")
                )
            else:
                await self._send_response(session, request_id, result.get("result"))
                
        except Exception as e:
            logger.error(f"处理 Sampling 请求失败: {e}")
            await self._send_error_response(
                session,
                request_id,
                -32603,
                f"Sampling error: {str(e)}"
            )
    
    async def _send_response(
        self,
        session: SSEMCPSession,
        request_id: int,
        result: Dict[str, Any]
    ):
        """发送 JSON-RPC 响应"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        
        client = await self._get_http_client()
        headers = self._get_auth_headers(session)
        headers["Content-Type"] = "application/json"
        
        url = f"{session.base_url}{session.message_endpoint}"
        
        await client.post(url, headers=headers, json=response)
    
    async def _send_error_response(
        self,
        session: SSEMCPSession,
        request_id: int,
        code: int,
        message: str
    ):
        """发送 JSON-RPC 错误响应"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        client = await self._get_http_client()
        headers = self._get_auth_headers(session)
        headers["Content-Type"] = "application/json"
        
        url = f"{session.base_url}{session.message_endpoint}"
        
        await client.post(url, headers=headers, json=response)
    
    async def _send_request(
        self,
        session: SSEMCPSession,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        发送 JSON-RPC 请求
        通过 HTTP POST 发送，通过 SSE 接收响应
        """
        session.request_id += 1
        request_id = session.request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method
        }
        if params:
            request["params"] = params
        
        # 创建 Future 等待响应
        future: asyncio.Future = asyncio.Future()
        session.pending_responses[request_id] = future
        
        # 发送请求
        client = await self._get_http_client()
        headers = self._get_auth_headers(session)
        headers["Content-Type"] = "application/json"
        
        url = f"{session.base_url}{session.message_endpoint}"
        
        try:
            response = await client.post(url, headers=headers, json=request)
            response.raise_for_status()
            
            # 等待 SSE 响应
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            session.pending_responses.pop(request_id, None)
            raise Exception(f"请求超时 (method: {method})")
        except Exception as e:
            session.pending_responses.pop(request_id, None)
            raise
    
    async def _send_notification(
        self,
        session: SSEMCPSession,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ):
        """发送通知（无响应）"""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params
        
        client = await self._get_http_client()
        headers = self._get_auth_headers(session)
        headers["Content-Type"] = "application/json"
        
        url = f"{session.base_url}{session.message_endpoint}"
        
        await client.post(url, headers=headers, json=notification)
    
    async def _initialize(
        self,
        session: SSEMCPSession,
        roots_config: Optional[List[Dict[str, Any]]] = None,
        enable_sampling: bool = True
    ):
        """
        初始化 MCP 会话
        
        Args:
            session: SSE MCP 会话
            roots_config: 可选的根目录配置
            enable_sampling: 是否启用 sampling 能力（默认启用）
        """
        # 延迟导入避免循环依赖
        from app.services.roots_service import roots_service
        
        # 构建客户端能力
        capabilities: Dict[str, Any] = {}
        
        # 声明 sampling 能力
        if enable_sampling:
            capabilities["sampling"] = {}
            session.sampling_enabled = True
        
        # 如果有 roots 配置，声明 roots 能力
        if roots_config or roots_service.get_global_roots():
            capabilities["roots"] = {"listChanged": True}
            session.roots_enabled = True
        
        # 发送 initialize 请求
        result = await self._send_request(session, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities,
            "clientInfo": {
                "name": "ui-config-sse-mcp-client",
                "version": "1.0.0"
            }
        })
        
        session.server_info = result
        session.server_capabilities = result.get("capabilities", {})
        
        # 发送 initialized 通知
        await self._send_notification(session, "notifications/initialized", {})
        
        # 如果启用了 roots，注册变更回调
        if session.roots_enabled:
            async def on_roots_changed(server_key: str, roots):
                if server_key == session.server_key:
                    await self._send_roots_list_changed(session)
            
            roots_service.register_change_callback(session.server_key, on_roots_changed)
        
        # 获取能力
        await self._refresh_tools(session)
        await self._refresh_resources(session)
        await self._refresh_prompts(session)
        
        logger.info(f"SSE MCP session initialized: {session.server_key}")
    
    async def _send_roots_list_changed(self, session: SSEMCPSession):
        """
        发送 roots/list_changed 通知
        """
        if not session.roots_enabled:
            return
        
        try:
            await self._send_notification(
                session,
                "notifications/roots/list_changed",
                {}
            )
            logger.info(f"已发送 roots/list_changed 通知到 SSE 服务器 {session.server_key}")
        except Exception as e:
            logger.error(f"发送 roots/list_changed 通知失败: {e}")
    
    async def send_roots_list_changed(self, server_key: str):
        """
        公开的发送 roots/list_changed 通知方法
        """
        session = self.sessions.get(server_key)
        if session and session.state == SSEConnectionState.CONNECTED:
            await self._send_roots_list_changed(session)
    
    async def handle_roots_list_request(self, server_key: str) -> List[Dict[str, Any]]:
        """
        处理 MCP 服务器的 roots/list 请求
        """
        from app.services.roots_service import roots_service
        return roots_service.get_roots_list(server_key)
    
    async def _refresh_tools(self, session: SSEMCPSession):
        """刷新工具列表"""
        result = await self._send_request(session, "tools/list", {})
        session.tools = result.get("tools", [])
    
    async def _refresh_resources(self, session: SSEMCPSession):
        """刷新资源列表"""
        result = await self._send_request(session, "resources/list", {})
        session.resources = result.get("resources", [])
    
    async def _refresh_prompts(self, session: SSEMCPSession):
        """刷新提示列表"""
        result = await self._send_request(session, "prompts/list", {})
        session.prompts = result.get("prompts", [])
    
    async def disconnect(self, server_key: str) -> tuple[bool, str]:
        """断开连接"""
        async with self._get_lock():
            if server_key not in self.sessions:
                return False, "未连接"
            
            session = self.sessions[server_key]
            
            # 取消心跳任务
            if server_key in self._heartbeat_tasks:
                self._heartbeat_tasks[server_key].cancel()
                try:
                    await self._heartbeat_tasks[server_key]
                except asyncio.CancelledError:
                    pass
                del self._heartbeat_tasks[server_key]
            
            # 取消 SSE 任务
            if server_key in self._sse_tasks:
                self._sse_tasks[server_key].cancel()
                try:
                    await self._sse_tasks[server_key]
                except asyncio.CancelledError:
                    pass
                del self._sse_tasks[server_key]
            
            # 取消所有待处理的请求
            for future in session.pending_responses.values():
                if not future.done():
                    future.cancel()
            
            # 清理 roots 配置
            try:
                from app.services.roots_service import roots_service
                await roots_service.clear_session_roots(server_key)
            except Exception as e:
                logger.warning(f"清理 roots 配置失败: {e}")
            
            # 触发断开连接事件
            await self._emit_event("disconnected", {
                "server_key": server_key
            })
            
            del self.sessions[server_key]
            logger.info(f"SSE MCP 客户端已断开: {server_key}")
            return True, "已断开"
    
    def is_connected(self, server_key: str) -> bool:
        """检查是否已连接"""
        session = self.sessions.get(server_key)
        return session is not None and session.state == SSEConnectionState.CONNECTED
    
    def get_session(self, server_key: str) -> Optional[SSEMCPSession]:
        """获取会话"""
        return self.sessions.get(server_key)
    
    async def list_tools(self, server_key: str) -> List[Dict[str, Any]]:
        """获取工具列表"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        await self._refresh_tools(session)
        return session.tools
    
    async def call_tool(
        self,
        server_key: str,
        tool_name: str,
        arguments: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """调用工具"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        result = await self._send_request(session, "tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        return result
    
    async def list_resources(self, server_key: str) -> List[Dict[str, Any]]:
        """获取资源列表"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        await self._refresh_resources(session)
        return session.resources
    
    async def read_resource(self, server_key: str, uri: str) -> Dict[str, Any]:
        """读取资源"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        result = await self._send_request(session, "resources/read", {
            "uri": uri
        })
        return result
    
    async def list_prompts(self, server_key: str) -> List[Dict[str, Any]]:
        """获取提示列表"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        await self._refresh_prompts(session)
        return session.prompts
    
    async def get_prompt(
        self,
        server_key: str,
        name: str,
        arguments: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """获取提示内容"""
        session = self.sessions.get(server_key)
        if not session or session.state != SSEConnectionState.CONNECTED:
            raise Exception("未连接")
        
        result = await self._send_request(session, "prompts/get", {
            "name": name,
            "arguments": arguments or {}
        })
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有连接状态"""
        status = {}
        for key, session in self.sessions.items():
            status[key] = self._get_session_status(session)
        return status
    
    def _get_session_status(self, session: SSEMCPSession) -> Dict[str, Any]:
        """获取单个会话的详细状态"""
        uptime = None
        if session.connected_at and session.state == SSEConnectionState.CONNECTED:
            uptime = (datetime.now() - session.connected_at).total_seconds()
        
        # 获取 roots 信息
        roots_info = None
        if session.roots_enabled:
            try:
                from app.services.roots_service import roots_service
                roots_list = roots_service.get_session_roots(session.server_key)
                roots_info = {
                    "enabled": True,
                    "count": len(roots_list),
                    "roots": [{"uri": r.uri, "name": r.name} for r in roots_list]
                }
            except Exception:
                roots_info = {"enabled": True, "count": 0, "roots": []}
        
        return {
            "state": session.state.value,
            "base_url": session.base_url,
            "sse_endpoint": session.sse_endpoint,
            "message_endpoint": session.message_endpoint,
            "tools_count": len(session.tools),
            "resources_count": len(session.resources),
            "prompts_count": len(session.prompts),
            "roots_enabled": session.roots_enabled,
            "roots": roots_info,
            "sampling_enabled": session.sampling_enabled,
            "created_at": session.created_at.isoformat(),
            "connected_at": session.connected_at.isoformat() if session.connected_at else None,
            "last_activity": session.last_activity.isoformat(),
            "last_heartbeat": session.last_heartbeat.isoformat() if session.last_heartbeat else None,
            "uptime_seconds": uptime,
            "reconnect_attempts": session.reconnect_attempts,
            "error_message": session.error_message,
            "server_info": session.server_info,
            "server_capabilities": session.server_capabilities
        }
    
    def get_session_status(self, server_key: str) -> Optional[Dict[str, Any]]:
        """获取指定会话的详细状态"""
        session = self.sessions.get(server_key)
        if not session:
            return None
        return self._get_session_status(session)
    
    async def test_connection(self, server_key: str) -> tuple[bool, str, float]:
        """
        测试 SSE 连接是否正常
        
        Returns:
            (is_healthy, message, latency_ms)
        """
        session = self.sessions.get(server_key)
        if not session:
            return False, "会话不存在", 0.0
        
        if session.state != SSEConnectionState.CONNECTED:
            return False, f"连接状态异常: {session.state.value}", 0.0
        
        # 发送一个简单的请求测试连通性
        start_time = datetime.now()
        try:
            # 尝试刷新工具列表作为健康检查
            await self._refresh_tools(session)
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return True, "连接正常", latency
        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return False, f"测试失败: {str(e)}", latency
    
    async def reconnect(self, server_key: str) -> tuple[bool, str]:
        """
        手动触发重连
        """
        session = self.sessions.get(server_key)
        if not session:
            return False, "会话不存在"
        
        # 保存原始配置
        config = {
            "base_url": session.base_url,
            "sse_endpoint": session.sse_endpoint,
            "message_endpoint": session.message_endpoint,
            "auth_token": session.auth_token,
            "auth_type": session.auth_type,
            "custom_headers": session.custom_headers
        }
        
        # 断开现有连接
        await self.disconnect(server_key)
        
        # 重新连接
        return await self.connect(
            server_key=server_key,
            **config
        )
    
    async def cleanup(self):
        """清理所有连接和资源"""
        # 断开所有会话
        for server_key in list(self.sessions.keys()):
            await self.disconnect(server_key)
        
        # 关闭 HTTP 客户端
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        # 清理事件回调
        self._event_callbacks.clear()
        
        logger.info("SSE MCP 客户端已完全清理")
    
    def list_connected_servers(self) -> List[str]:
        """获取所有已连接的服务器列表"""
        return [
            key for key, session in self.sessions.items()
            if session.state == SSEConnectionState.CONNECTED
        ]
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有已连接服务器的工具列表（带服务器标识）"""
        all_tools = []
        for server_key, session in self.sessions.items():
            if session.state == SSEConnectionState.CONNECTED:
                for tool in session.tools:
                    all_tools.append({
                        "server_key": server_key,
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "inputSchema": tool.get("inputSchema", {}),
                        # OpenAI Function Calling 兼容格式
                        "full_name": f"{server_key}__{tool.get('name', '')}"
                    })
        return all_tools


# 创建全局单例
sse_mcp_client = SSEMCPClient()

