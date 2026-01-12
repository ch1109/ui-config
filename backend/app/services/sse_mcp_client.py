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
"""

import asyncio
import json
import logging
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


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
    
    # 状态
    state: SSEConnectionState = SSEConnectionState.DISCONNECTED
    session_id: Optional[str] = None
    request_id: int = 0
    
    # 能力
    server_info: Dict[str, Any] = field(default_factory=dict)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[Dict[str, Any]] = field(default_factory=list)
    
    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # 待处理的响应
    pending_responses: Dict[int, asyncio.Future] = field(default_factory=dict)


class SSEMCPClient:
    """
    SSE MCP 客户端
    
    实现基于 SSE 的 MCP 通信协议
    """
    
    def __init__(self):
        self.sessions: Dict[str, SSEMCPSession] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sse_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client
    
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
        timeout: float = 30.0
    ) -> tuple[bool, str]:
        """
        连接到 SSE MCP 服务器
        """
        async with self._lock:
            # 检查是否已连接
            if server_key in self.sessions:
                session = self.sessions[server_key]
                if session.state == SSEConnectionState.CONNECTED:
                    return True, "已连接"
            
            # 创建会话
            session = SSEMCPSession(
                server_key=server_key,
                base_url=base_url.rstrip("/"),
                sse_endpoint=sse_endpoint,
                message_endpoint=message_endpoint,
                auth_token=auth_token,
                auth_type=auth_type,
                state=SSEConnectionState.CONNECTING
            )
            self.sessions[server_key] = session
            
            try:
                # 启动 SSE 连接
                sse_task = asyncio.create_task(
                    self._sse_listener(session)
                )
                self._sse_tasks[server_key] = sse_task
                
                # 等待连接建立
                await asyncio.wait_for(
                    self._wait_for_connection(session),
                    timeout=timeout
                )
                
                # 初始化 MCP 会话
                await self._initialize(session)
                
                return True, f"已连接到 {base_url}"
                
            except asyncio.TimeoutError:
                await self.disconnect(server_key)
                return False, "连接超时"
            except Exception as e:
                await self.disconnect(server_key)
                return False, f"连接失败: {str(e)}"
    
    async def _wait_for_connection(self, session: SSEMCPSession):
        """等待 SSE 连接建立"""
        while session.state == SSEConnectionState.CONNECTING:
            await asyncio.sleep(0.1)
        
        if session.state != SSEConnectionState.CONNECTED:
            raise Exception("连接失败")
    
    async def _sse_listener(self, session: SSEMCPSession):
        """
        SSE 事件监听器
        持续接收服务端推送的消息
        """
        client = await self._get_http_client()
        headers = self._get_auth_headers(session)
        headers["Accept"] = "text/event-stream"
        
        url = f"{session.base_url}{session.sse_endpoint}"
        
        while True:
            try:
                async with client.stream(
                    "GET",
                    url,
                    headers=headers
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"SSE connection failed: {response.status_code}")
                        session.state = SSEConnectionState.ERROR
                        break
                    
                    session.state = SSEConnectionState.CONNECTED
                    logger.info(f"SSE connected to {url}")
                    
                    # 解析 SSE 消息
                    async for message in self._parse_sse_stream(response):
                        await self._handle_sse_message(session, message)
                        
            except httpx.ReadTimeout:
                logger.debug("SSE read timeout, reconnecting...")
                session.state = SSEConnectionState.RECONNECTING
                await asyncio.sleep(1)
                continue
                
            except asyncio.CancelledError:
                logger.info(f"SSE listener cancelled for {session.server_key}")
                break
                
            except Exception as e:
                logger.error(f"SSE error: {e}")
                session.state = SSEConnectionState.ERROR
                await asyncio.sleep(5)  # 重连延迟
                session.state = SSEConnectionState.RECONNECTING
    
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
    
    async def _initialize(self, session: SSEMCPSession):
        """初始化 MCP 会话"""
        # 发送 initialize 请求
        result = await self._send_request(session, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "ui-config-sse-mcp-client",
                "version": "1.0.0"
            }
        })
        
        session.server_info = result
        
        # 发送 initialized 通知
        await self._send_notification(session, "notifications/initialized", {})
        
        # 获取能力
        await self._refresh_tools(session)
        await self._refresh_resources(session)
        await self._refresh_prompts(session)
        
        logger.info(f"SSE MCP session initialized: {session.server_key}")
    
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
        async with self._lock:
            if server_key not in self.sessions:
                return False, "未连接"
            
            # 取消 SSE 任务
            if server_key in self._sse_tasks:
                self._sse_tasks[server_key].cancel()
                try:
                    await self._sse_tasks[server_key]
                except asyncio.CancelledError:
                    pass
                del self._sse_tasks[server_key]
            
            del self.sessions[server_key]
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
            status[key] = {
                "state": session.state.value,
                "base_url": session.base_url,
                "tools_count": len(session.tools),
                "resources_count": len(session.resources),
                "prompts_count": len(session.prompts),
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "server_info": session.server_info
            }
        return status
    
    async def cleanup(self):
        """清理所有连接"""
        for server_key in list(self.sessions.keys()):
            await self.disconnect(server_key)
        
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# 创建全局单例
sse_mcp_client = SSEMCPClient()

