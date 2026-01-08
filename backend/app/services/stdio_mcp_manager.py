# app/services/stdio_mcp_manager.py
"""
Stdio MCP 服务器管理服务
管理通过 stdio 传输协议运行的 MCP 服务器（如 Context7、Everything Server）
"""

import asyncio
import json
import os
import shutil
from typing import Dict, Any, List, Optional, Tuple
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
    tools: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


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
        timeout: float = 30.0
    ) -> Tuple[bool, str]:
        """
        启动 stdio MCP 服务器
        
        Args:
            server_key: 服务器标识 (如 "context7", "everything")
            command: 启动命令 (如 "npx")
            args: 命令参数
            env: 环境变量
            timeout: 超时时间
            
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
                
                # 初始化连接
                try:
                    await asyncio.wait_for(
                        self._initialize(session),
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
    
    async def _initialize(self, session: MCPSession):
        """初始化 MCP 连接"""
        # 发送 initialize 请求
        result = await self._send_request(session, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "ui-config-mcp-client",
                "version": "1.0.0"
            }
        })
        
        session.server_info = result
        
        # 发送 initialized 通知
        await self._send_notification(session, "notifications/initialized", {})
        
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
    
    async def _send_request(
        self,
        session: MCPSession,
        method: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """发送 JSON-RPC 请求"""
        session.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": session.request_id,
            "method": method
        }
        if params:
            request["params"] = params
        
        request_str = json.dumps(request) + "\n"
        session.process.stdin.write(request_str.encode())
        await session.process.stdin.drain()
        
        # 读取响应
        response_line = await session.process.stdout.readline()
        if not response_line:
            raise Exception("MCP 服务器已关闭连接")
        
        response = json.loads(response_line.decode())
        
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
    
    async def stop_server(self, server_key: str) -> Tuple[bool, str]:
        """停止 MCP 服务器"""
        async with self._lock:
            if server_key not in self.sessions:
                return False, "服务器未运行"
            
            session = self.sessions[server_key]
            
            try:
                session.process.terminate()
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    session.process.kill()
                    await session.process.wait()
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
            
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
            status[key] = {
                "running": is_running,
                "initialized": session.initialized,
                "tools_count": len(session.tools),
                "resources_count": len(session.resources),
                "prompts_count": len(session.prompts),
                "created_at": session.created_at.isoformat(),
                "server_info": session.server_info
            }
        return status
    
    async def cleanup(self):
        """清理所有会话"""
        for server_key in list(self.sessions.keys()):
            await self.stop_server(server_key)


# 创建全局单例
stdio_mcp_manager = StdioMCPManager()

