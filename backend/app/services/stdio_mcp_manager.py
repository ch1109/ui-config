# app/services/stdio_mcp_manager.py
"""
Stdio MCP 服务器管理服务
管理通过 stdio 传输协议运行的 MCP 服务器（如 Context7、Everything Server）

支持 MCP Roots 能力：
- 在 initialize 时发送 roots 配置
- 支持 roots/list_changed 通知
- 集成 roots_service 进行路径验证

支持 MCP Sampling 能力：
- 在 initialize 时声明 sampling 能力
- 监听来自 MCP Server 的 sampling/createMessage 请求
- 通过 sampling_service 处理请求并返回响应
"""

import asyncio
import json
import os
import shutil
from typing import Dict, Any, List, Optional, Tuple, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MCPSession:
    """MCP 会话信息"""
    server_key: str
    process: asyncio.subprocess.Process
    request_id: int = 0
    initialized: bool = False
    server_info: Dict[str, Any] = field(default_factory=dict)
    server_capabilities: Dict[str, Any] = field(default_factory=dict)  # 服务器能力
    tools: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[Dict[str, Any]] = field(default_factory=list)
    roots_enabled: bool = False  # 是否启用了 roots
    sampling_enabled: bool = False  # 是否启用了 sampling
    created_at: datetime = field(default_factory=datetime.now)
    
    # 用于异步请求/响应匹配
    pending_responses: Dict[int, asyncio.Future] = field(default_factory=dict)
    listener_task: Optional[asyncio.Task] = None  # 后台监听任务


class StdioMCPManager:
    """
    Stdio MCP 服务器管理器
    负责启动、管理和调用 stdio MCP 服务器
    """
    
    def __init__(self):
        self.sessions: Dict[str, MCPSession] = {}
        self._lock = asyncio.Lock()
    
    async def start_server(
        self,
        server_key: str,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        timeout: float = 30.0,
        roots_config: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, str]:
        """
        启动 stdio MCP 服务器
        
        Args:
            server_key: 服务器标识 (如 "context7", "everything")
            command: 启动命令 (如 "npx")
            args: 命令参数
            env: 环境变量
            timeout: 超时时间
            roots_config: 可选的根目录配置，格式: [{"path": "/path/to/dir", "name": "名称"}, ...]
            
        Returns:
            (success, message)
        """
        async with self._lock:
            # 检查是否已运行
            if server_key in self.sessions:
                session = self.sessions[server_key]
                if session.process.returncode is None:
                    return True, "服务器已在运行"
                else:
                    # 进程已退出，清理
                    del self.sessions[server_key]
            
            # 检查命令是否存在
            if command == "npx":
                # 检查 Node.js 是否可用
                if not shutil.which("npx"):
                    return False, "未找到 npx 命令，请确保已安装 Node.js"
            
            # 构建完整环境变量
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
            
            try:
                # 启动子进程
                process = await asyncio.create_subprocess_exec(
                    command,
                    *(args or []),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=full_env
                )
                
                session = MCPSession(
                    server_key=server_key,
                    process=process
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
                
                # 初始化连接
                try:
                    await asyncio.wait_for(
                        self._initialize(session, roots_config),
                        timeout=timeout
                    )
                    return True, f"服务器 {server_key} 启动成功"
                except asyncio.TimeoutError:
                    await self.stop_server(server_key)
                    return False, f"服务器初始化超时 ({timeout}秒)"
                except Exception as e:
                    await self.stop_server(server_key)
                    return False, f"服务器初始化失败: {str(e)}"
                    
            except FileNotFoundError:
                return False, f"命令 {command} 未找到"
            except Exception as e:
                return False, f"启动服务器失败: {str(e)}"
    
    async def _send_roots_list_changed(self, session: MCPSession):
        """
        发送 roots/list_changed 通知
        
        当根目录列表变更时调用此方法通知 MCP 服务器
        """
        if not session.initialized or not session.roots_enabled:
            return
        
        try:
            await self._send_notification(
                session,
                "notifications/roots/list_changed",
                {}
            )
            logger.info(f"已发送 roots/list_changed 通知到 {session.server_key}")
        except Exception as e:
            logger.error(f"发送 roots/list_changed 通知失败: {e}")
    
    async def send_roots_list_changed(self, server_key: str):
        """
        公开的发送 roots/list_changed 通知方法
        
        Args:
            server_key: 服务器标识
        """
        session = self.sessions.get(server_key)
        if session:
            await self._send_roots_list_changed(session)
    
    async def handle_roots_list_request(self, server_key: str) -> List[Dict[str, Any]]:
        """
        处理 MCP 服务器的 roots/list 请求
        
        Args:
            server_key: 服务器标识
            
        Returns:
            根目录列表，MCP 规范格式
        """
        from app.services.roots_service import roots_service
        return roots_service.get_roots_list(server_key)
    
    async def _initialize(
        self,
        session: MCPSession,
        roots_config: Optional[List[Dict[str, Any]]] = None,
        enable_sampling: bool = True
    ):
        """
        初始化 MCP 连接
        
        Args:
            session: MCP 会话
            roots_config: 可选的根目录配置列表，每个元素包含 uri 和可选的 name
            enable_sampling: 是否启用 sampling 能力（默认启用）
        """
        # 延迟导入避免循环依赖
        from app.services.roots_service import roots_service
        
        # 构建客户端能力
        capabilities: Dict[str, Any] = {}
        
        # 如果有 roots 配置，声明 roots 能力
        if roots_config or roots_service.get_global_roots():
            capabilities["roots"] = {"listChanged": True}
            session.roots_enabled = True
        
        # 声明 sampling 能力
        if enable_sampling:
            capabilities["sampling"] = {}
            session.sampling_enabled = True
        
        # 发送 initialize 请求
        result = await self._send_request(session, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities,
            "clientInfo": {
                "name": "ui-config-mcp-client",
                "version": "1.0.0"
            }
        })
        
        session.server_info = result
        # 提取服务器能力
        session.server_capabilities = result.get("capabilities", {})
        
        # 发送 initialized 通知
        await self._send_notification(session, "notifications/initialized", {})
        
        # 如果启用了 roots，注册变更回调
        if session.roots_enabled:
            async def on_roots_changed(server_key: str, roots):
                if server_key == session.server_key:
                    await self._send_roots_list_changed(session)
            
            roots_service.register_change_callback(session.server_key, on_roots_changed)
        
        # 获取能力列表
        try:
            tools_result = await self._send_request(session, "tools/list", {})
            session.tools = tools_result.get("tools", [])
        except Exception as e:
            logger.warning(f"Failed to list tools: {e}")
        
        try:
            resources_result = await self._send_request(session, "resources/list", {})
            session.resources = resources_result.get("resources", [])
        except Exception as e:
            logger.warning(f"Failed to list resources: {e}")
        
        try:
            prompts_result = await self._send_request(session, "prompts/list", {})
            session.prompts = prompts_result.get("prompts", [])
        except Exception as e:
            logger.warning(f"Failed to list prompts: {e}")
        
        session.initialized = True
        
        # 启动后台监听任务（用于接收服务器主动发送的请求，如 sampling/createMessage）
        session.listener_task = asyncio.create_task(
            self._stdout_listener(session)
        )
    
    async def _send_request(
        self,
        session: MCPSession,
        method: str,
        params: Dict[str, Any] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        发送 JSON-RPC 请求
        
        如果监听任务已启动，使用 Future 等待响应；否则直接读取 stdout。
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
        
        request_str = json.dumps(request) + "\n"
        
        # 如果监听任务已启动，使用 Future 等待响应
        if session.listener_task is not None:
            future = asyncio.get_event_loop().create_future()
            session.pending_responses[request_id] = future
            
            try:
                session.process.stdin.write(request_str.encode())
                await session.process.stdin.drain()
                
                # 等待响应
                response = await asyncio.wait_for(future, timeout=timeout)
            finally:
                session.pending_responses.pop(request_id, None)
        else:
            # 初始化阶段，直接读取 stdout
            session.process.stdin.write(request_str.encode())
            await session.process.stdin.drain()
            
            # 读取响应，忽略非 JSON 输出
            while True:
                response_line = await session.process.stdout.readline()
                if not response_line:
                    raise Exception("MCP 服务器已关闭连接")
                try:
                    response = json.loads(response_line.decode())
                    break
                except json.JSONDecodeError:
                    logger.warning(
                        "Non-JSON output from MCP server %s: %s",
                        session.server_key,
                        response_line.decode(errors="replace").strip()
                    )
                    continue
        
        if "error" in response:
            error = response["error"]
            raise Exception(f"MCP 错误 [{error.get('code')}]: {error.get('message')}")
        
        return response.get("result", {})
    
    async def _send_notification(
        self,
        session: MCPSession,
        method: str,
        params: Dict[str, Any] = None
    ):
        """发送 JSON-RPC 通知（无响应）"""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params
        
        notification_str = json.dumps(notification) + "\n"
        session.process.stdin.write(notification_str.encode())
        await session.process.stdin.drain()
    
    async def _send_response(
        self,
        session: MCPSession,
        request_id: Any,
        result: Any = None,
        error: Dict[str, Any] = None
    ):
        """发送 JSON-RPC 响应（用于回复服务器请求）"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id
        }
        
        if error:
            response["error"] = error
        else:
            response["result"] = result
        
        response_str = json.dumps(response) + "\n"
        session.process.stdin.write(response_str.encode())
        await session.process.stdin.drain()
    
    async def _stdout_listener(self, session: MCPSession):
        """
        后台任务：监听 MCP Server 的 stdout
        
        处理：
        1. 响应消息（有 id，匹配到 pending_responses）
        2. 请求消息（有 id 和 method，如 sampling/createMessage）
        3. 通知消息（无 id，有 method）
        """
        logger.info(f"启动 stdout 监听任务: {session.server_key}")
        
        try:
            while session.process.returncode is None:
                try:
                    line = await session.process.stdout.readline()
                    if not line:
                        # 进程已关闭
                        break
                    
                    try:
                        message = json.loads(line.decode())
                    except json.JSONDecodeError:
                        # 非 JSON 输出（可能是日志），忽略
                        logger.debug(
                            "Non-JSON output from %s: %s",
                            session.server_key,
                            line.decode(errors="replace").strip()
                        )
                        continue
                    
                    await self._handle_server_message(session, message)
                    
                except asyncio.CancelledError:
                    logger.info(f"stdout 监听任务被取消: {session.server_key}")
                    break
                except Exception as e:
                    logger.error(f"处理 MCP 消息时出错: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"stdout 监听任务异常退出: {session.server_key} - {e}")
        finally:
            logger.info(f"stdout 监听任务结束: {session.server_key}")
    
    async def _handle_server_message(self, session: MCPSession, message: Dict[str, Any]):
        """
        处理来自 MCP Server 的消息
        
        消息类型：
        1. 响应：{"jsonrpc": "2.0", "id": N, "result": {...}} 或 {"error": {...}}
        2. 请求：{"jsonrpc": "2.0", "id": N, "method": "...", "params": {...}}
        3. 通知：{"jsonrpc": "2.0", "method": "...", "params": {...}}
        """
        msg_id = message.get("id")
        method = message.get("method")
        
        # 1. 响应消息（有 id，无 method）
        if msg_id is not None and method is None:
            future = session.pending_responses.get(msg_id)
            if future and not future.done():
                future.set_result(message)
            else:
                logger.warning(f"收到未匹配的响应 ID: {msg_id}")
            return
        
        # 2. 请求消息（有 id 和 method）
        if msg_id is not None and method is not None:
            await self._handle_server_request(session, msg_id, method, message.get("params", {}))
            return
        
        # 3. 通知消息（无 id，有 method）
        if method is not None:
            await self._handle_server_notification(session, method, message.get("params", {}))
            return
        
        logger.warning(f"收到未知格式的消息: {message}")
    
    async def _handle_server_request(
        self,
        session: MCPSession,
        request_id: Any,
        method: str,
        params: Dict[str, Any]
    ):
        """
        处理 MCP Server 发来的请求
        
        支持的请求：
        - sampling/createMessage: 请求 Host 调用 LLM
        - roots/list: 请求根目录列表
        """
        logger.info(f"收到服务器请求: {session.server_key} - {method}")
        
        try:
            if method == "sampling/createMessage":
                # 处理 Sampling 请求
                await self._handle_sampling_request(session, request_id, params)
            
            elif method == "roots/list":
                # 处理 roots/list 请求
                roots_list = await self.handle_roots_list_request(session.server_key)
                await self._send_response(session, request_id, {"roots": roots_list})
            
            else:
                # 不支持的请求方法
                await self._send_response(
                    session,
                    request_id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                )
        except Exception as e:
            logger.error(f"处理服务器请求失败: {method} - {e}")
            await self._send_response(
                session,
                request_id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            )
    
    async def _handle_sampling_request(
        self,
        session: MCPSession,
        request_id: Any,
        params: Dict[str, Any]
    ):
        """
        处理 sampling/createMessage 请求
        
        将请求转发给 sampling_service 处理
        """
        if not session.sampling_enabled:
            await self._send_response(
                session,
                request_id,
                error={
                    "code": -32600,
                    "message": "Sampling capability not enabled for this session"
                }
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
                await self._send_response(session, request_id, error=result["error"])
            else:
                await self._send_response(session, request_id, result=result.get("result"))
                
        except Exception as e:
            logger.error(f"处理 Sampling 请求失败: {e}")
            await self._send_response(
                session,
                request_id,
                error={
                    "code": -32603,
                    "message": f"Sampling error: {str(e)}"
                }
            )
    
    async def _handle_server_notification(
        self,
        session: MCPSession,
        method: str,
        params: Dict[str, Any]
    ):
        """
        处理 MCP Server 发来的通知
        
        支持的通知：
        - notifications/tools/list_changed: 工具列表变更
        - notifications/resources/list_changed: 资源列表变更
        - notifications/prompts/list_changed: 提示模板列表变更
        """
        logger.info(f"收到服务器通知: {session.server_key} - {method}")
        
        try:
            if method == "notifications/tools/list_changed":
                # 刷新工具列表
                tools_result = await self._send_request(session, "tools/list", {})
                session.tools = tools_result.get("tools", [])
                logger.info(f"工具列表已更新: {session.server_key} - {len(session.tools)} 个工具")
            
            elif method == "notifications/resources/list_changed":
                # 刷新资源列表
                resources_result = await self._send_request(session, "resources/list", {})
                session.resources = resources_result.get("resources", [])
                logger.info(f"资源列表已更新: {session.server_key}")
            
            elif method == "notifications/prompts/list_changed":
                # 刷新提示模板列表
                prompts_result = await self._send_request(session, "prompts/list", {})
                session.prompts = prompts_result.get("prompts", [])
                logger.info(f"提示模板列表已更新: {session.server_key}")
            
            else:
                logger.debug(f"未处理的通知: {method}")
                
        except Exception as e:
            logger.error(f"处理服务器通知失败: {method} - {e}")
    
    async def stop_server(self, server_key: str) -> Tuple[bool, str]:
        """停止 MCP 服务器"""
        async with self._lock:
            if server_key not in self.sessions:
                return False, "服务器未运行"
            
            session = self.sessions[server_key]
            
            # 取消监听任务
            if session.listener_task:
                session.listener_task.cancel()
                try:
                    await session.listener_task
                except asyncio.CancelledError:
                    pass
                session.listener_task = None
            
            # 取消所有待处理的响应
            for future in session.pending_responses.values():
                if not future.done():
                    future.cancel()
            session.pending_responses.clear()
            
            try:
                session.process.terminate()
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    session.process.kill()
                    await session.process.wait()
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
            
            # 清理 roots 配置
            try:
                from app.services.roots_service import roots_service
                await roots_service.clear_session_roots(server_key)
            except Exception as e:
                logger.warning(f"清理 roots 配置失败: {e}")
            
            del self.sessions[server_key]
            return True, f"服务器 {server_key} 已停止"
    
    def is_running(self, server_key: str) -> bool:
        """检查服务器是否正在运行"""
        if server_key not in self.sessions:
            return False
        session = self.sessions[server_key]
        return session.process.returncode is None
    
    def get_session(self, server_key: str) -> Optional[MCPSession]:
        """获取会话信息"""
        return self.sessions.get(server_key)
    
    async def list_tools(self, server_key: str) -> List[Dict[str, Any]]:
        """获取工具列表"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        # 刷新工具列表
        result = await self._send_request(session, "tools/list", {})
        session.tools = result.get("tools", [])
        return session.tools
    
    async def call_tool(
        self,
        server_key: str,
        tool_name: str,
        arguments: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """调用工具"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        result = await self._send_request(session, "tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        return result
    
    async def list_resources(self, server_key: str) -> List[Dict[str, Any]]:
        """获取资源列表"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        result = await self._send_request(session, "resources/list", {})
        session.resources = result.get("resources", [])
        return session.resources
    
    async def read_resource(self, server_key: str, uri: str) -> Dict[str, Any]:
        """读取资源"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        result = await self._send_request(session, "resources/read", {
            "uri": uri
        })
        return result
    
    async def list_prompts(self, server_key: str) -> List[Dict[str, Any]]:
        """获取提示模板列表"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        result = await self._send_request(session, "prompts/list", {})
        session.prompts = result.get("prompts", [])
        return session.prompts
    
    async def get_prompt(
        self,
        server_key: str,
        name: str,
        arguments: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """获取提示模板内容"""
        session = self.sessions.get(server_key)
        if not session or not session.initialized:
            raise Exception("服务器未运行或未初始化")
        
        result = await self._send_request(session, "prompts/get", {
            "name": name,
            "arguments": arguments or {}
        })
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有服务器状态"""
        status = {}
        for key, session in self.sessions.items():
            is_running = session.process.returncode is None
            
            # 获取 roots 信息
            roots_info = None
            if session.roots_enabled:
                try:
                    from app.services.roots_service import roots_service
                    roots_list = roots_service.get_session_roots(key)
                    roots_info = {
                        "enabled": True,
                        "count": len(roots_list),
                        "roots": [{"uri": r.uri, "name": r.name} for r in roots_list]
                    }
                except Exception:
                    roots_info = {"enabled": True, "count": 0, "roots": []}
            
            # 获取 sampling 信息
            sampling_info = {
                "enabled": session.sampling_enabled,
                "listener_active": session.listener_task is not None and not session.listener_task.done()
            }
            
            status[key] = {
                "running": is_running,
                "initialized": session.initialized,
                "tools_count": len(session.tools),
                "resources_count": len(session.resources),
                "prompts_count": len(session.prompts),
                "roots_enabled": session.roots_enabled,
                "roots": roots_info,
                "sampling_enabled": session.sampling_enabled,
                "sampling": sampling_info,
                "created_at": session.created_at.isoformat(),
                "server_info": session.server_info,
                "server_capabilities": session.server_capabilities
            }
        return status
    
    async def cleanup(self):
        """清理所有会话"""
        for server_key in list(self.sessions.keys()):
            await self.stop_server(server_key)


# 创建全局单例
stdio_mcp_manager = StdioMCPManager()
