# app/services/mcp_client_service.py
"""
MCP 客户端服务
实现与 MCP 服务器的通信，支持工具调用、资源获取等功能
"""

import asyncio
import json
import subprocess
import sys
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import logging
import httpx

logger = logging.getLogger(__name__)


class MCPTransportType(Enum):
    """MCP 传输类型"""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


@dataclass
class MCPPrompt:
    """MCP 提示模板定义"""
    name: str
    description: str = ""
    arguments: List[Dict[str, Any]] = field(default_factory=list)


class MCPClientService:
    """
    MCP 客户端服务
    支持 stdio 和 HTTP/SSE 两种传输方式
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, Any] = {}
        
    async def connect_stdio(
        self,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        cwd: str = None
    ) -> str:
        """
        通过 stdio 连接到 MCP 服务器
        
        Args:
            command: 启动命令 (如 "npx", "python")
            args: 命令参数
            env: 环境变量
            cwd: 工作目录
            
        Returns:
            session_id: 会话 ID
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        # 构建完整环境变量
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        # 启动子进程
        process = await asyncio.create_subprocess_exec(
            command,
            *(args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
            cwd=cwd
        )
        
        self.active_sessions[session_id] = {
            "type": MCPTransportType.STDIO,
            "process": process,
            "request_id": 0
        }
        
        # 发送初始化请求
        await self._stdio_initialize(session_id)
        
        return session_id
    
    async def connect_http(
        self,
        server_url: str,
        auth_token: str = None
    ) -> str:
        """
        通过 HTTP/SSE 连接到 MCP 服务器
        
        Args:
            server_url: 服务器 URL
            auth_token: 认证令牌（可选）
            
        Returns:
            session_id: 会话 ID
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        self.active_sessions[session_id] = {
            "type": MCPTransportType.HTTP,
            "server_url": server_url.rstrip("/"),
            "headers": headers,
            "client": httpx.AsyncClient(timeout=30.0)
        }
        
        return session_id
    
    async def disconnect(self, session_id: str):
        """断开连接"""
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        
        if session["type"] == MCPTransportType.STDIO:
            process = session["process"]
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
        elif session["type"] == MCPTransportType.HTTP:
            await session["client"].aclose()
        
        del self.active_sessions[session_id]
    
    async def _stdio_initialize(self, session_id: str):
        """发送 stdio 初始化请求"""
        await self._stdio_request(session_id, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "ui-config-mcp-client",
                "version": "1.0.0"
            }
        })
        
        # 发送 initialized 通知
        await self._stdio_notify(session_id, "notifications/initialized", {})
    
    async def _stdio_request(
        self,
        session_id: str,
        method: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """发送 stdio JSON-RPC 请求"""
        session = self.active_sessions[session_id]
        session["request_id"] += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": session["request_id"],
            "method": method
        }
        if params:
            request["params"] = params
        
        request_str = json.dumps(request) + "\n"
        session["process"].stdin.write(request_str.encode())
        await session["process"].stdin.drain()
        
        # 读取响应
        response_line = await session["process"].stdout.readline()
        if not response_line:
            raise Exception("MCP server closed connection")
        
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise Exception(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def _stdio_notify(
        self,
        session_id: str,
        method: str,
        params: Dict[str, Any] = None
    ):
        """发送 stdio JSON-RPC 通知"""
        session = self.active_sessions[session_id]
        
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params
        
        notification_str = json.dumps(notification) + "\n"
        session["process"].stdin.write(notification_str.encode())
        await session["process"].stdin.drain()
    
    async def list_tools(self, session_id: str) -> List[MCPTool]:
        """
        列出 MCP 服务器可用的工具
        
        Returns:
            工具列表
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "tools/list")
        else:
            async with session["client"] as client:
                response = await client.get(
                    f"{session['server_url']}/tools",
                    headers=session["headers"]
                )
                response.raise_for_status()
                result = response.json()
        
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(MCPTool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {})
            ))
        
        return tools
    
    async def call_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具
        
        Args:
            session_id: 会话 ID
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "tools/call", {
                "name": tool_name,
                "arguments": arguments or {}
            })
        else:
            async with session["client"] as client:
                response = await client.post(
                    f"{session['server_url']}/tools/{tool_name}",
                    headers=session["headers"],
                    json={"arguments": arguments or {}}
                )
                response.raise_for_status()
                result = response.json()
        
        return result
    
    async def list_resources(self, session_id: str) -> List[MCPResource]:
        """
        列出 MCP 服务器可用的资源
        
        Returns:
            资源列表
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "resources/list")
        else:
            async with session["client"] as client:
                response = await client.get(
                    f"{session['server_url']}/resources",
                    headers=session["headers"]
                )
                response.raise_for_status()
                result = response.json()
        
        resources = []
        for res_data in result.get("resources", []):
            resources.append(MCPResource(
                uri=res_data.get("uri", ""),
                name=res_data.get("name", ""),
                description=res_data.get("description", ""),
                mime_type=res_data.get("mimeType", "text/plain")
            ))
        
        return resources
    
    async def read_resource(
        self,
        session_id: str,
        uri: str
    ) -> Dict[str, Any]:
        """
        读取 MCP 资源
        
        Args:
            session_id: 会话 ID
            uri: 资源 URI
            
        Returns:
            资源内容
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "resources/read", {
                "uri": uri
            })
        else:
            async with session["client"] as client:
                response = await client.get(
                    f"{session['server_url']}/resources/read",
                    headers=session["headers"],
                    params={"uri": uri}
                )
                response.raise_for_status()
                result = response.json()
        
        return result
    
    async def list_prompts(self, session_id: str) -> List[MCPPrompt]:
        """
        列出 MCP 服务器可用的提示模板
        
        Returns:
            提示模板列表
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "prompts/list")
        else:
            async with session["client"] as client:
                response = await client.get(
                    f"{session['server_url']}/prompts",
                    headers=session["headers"]
                )
                response.raise_for_status()
                result = response.json()
        
        prompts = []
        for prompt_data in result.get("prompts", []):
            prompts.append(MCPPrompt(
                name=prompt_data.get("name", ""),
                description=prompt_data.get("description", ""),
                arguments=prompt_data.get("arguments", [])
            ))
        
        return prompts
    
    async def get_prompt(
        self,
        session_id: str,
        name: str,
        arguments: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        获取提示模板内容
        
        Args:
            session_id: 会话 ID
            name: 提示模板名称
            arguments: 模板参数
            
        Returns:
            提示模板内容
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("Session not found")
        
        if session["type"] == MCPTransportType.STDIO:
            result = await self._stdio_request(session_id, "prompts/get", {
                "name": name,
                "arguments": arguments or {}
            })
        else:
            async with session["client"] as client:
                response = await client.post(
                    f"{session['server_url']}/prompts/{name}",
                    headers=session["headers"],
                    json={"arguments": arguments or {}}
                )
                response.raise_for_status()
                result = response.json()
        
        return result


# 创建全局单例
mcp_client = MCPClientService()


# 内置演示 MCP 服务器（用于测试）
class DemoMCPServer:
    """
    内置演示 MCP 服务器
    提供一些基本工具用于测试 MCP 功能
    """
    
    @staticmethod
    def get_tools() -> List[Dict[str, Any]]:
        """获取演示工具列表"""
        return [
            {
                "name": "echo",
                "description": "回显输入的消息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "要回显的消息"
                        }
                    },
                    "required": ["message"]
                }
            },
            {
                "name": "calculate",
                "description": "执行简单的数学计算",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如 '2 + 3 * 4'"
                        }
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "get_time",
                "description": "获取当前时间",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "时区，如 'Asia/Shanghai'"
                        }
                    }
                }
            },
            {
                "name": "search_docs",
                "description": "搜索文档（模拟）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    @staticmethod
    def get_resources() -> List[Dict[str, Any]]:
        """获取演示资源列表"""
        return [
            {
                "uri": "demo://config/app",
                "name": "应用配置",
                "description": "应用程序配置文件",
                "mimeType": "application/json"
            },
            {
                "uri": "demo://docs/readme",
                "name": "README 文档",
                "description": "项目 README 文档",
                "mimeType": "text/markdown"
            }
        ]
    
    @staticmethod
    def get_prompts() -> List[Dict[str, Any]]:
        """获取演示提示模板列表"""
        return [
            {
                "name": "greeting",
                "description": "生成问候语",
                "arguments": [
                    {
                        "name": "name",
                        "description": "用户姓名",
                        "required": True
                    },
                    {
                        "name": "language",
                        "description": "语言",
                        "required": False
                    }
                ]
            },
            {
                "name": "code_review",
                "description": "代码审查提示",
                "arguments": [
                    {
                        "name": "code",
                        "description": "要审查的代码",
                        "required": True
                    },
                    {
                        "name": "language",
                        "description": "编程语言",
                        "required": False
                    }
                ]
            }
        ]
    
    @staticmethod
    async def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行演示工具"""
        from datetime import datetime, timezone as tz, timedelta
        import re
        
        if name == "echo":
            message = arguments.get("message", "")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}"
                    }
                ]
            }
        
        elif name == "calculate":
            expression = arguments.get("expression", "0")
            # 安全地执行简单数学表达式
            try:
                # 只允许数字和基本运算符
                if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', expression):
                    raise ValueError("Invalid expression")
                result = eval(expression)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"{expression} = {result}"
                        }
                    ]
                }
            except Exception as e:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"计算错误: {str(e)}"
                        }
                    ],
                    "isError": True
                }
        
        elif name == "get_time":
            timezone_name = arguments.get("timezone", "Asia/Shanghai")
            try:
                # 简单的时区映射
                tz_offsets = {
                    "Asia/Shanghai": 8,
                    "Asia/Tokyo": 9,
                    "UTC": 0,
                    "America/New_York": -5,
                    "Europe/London": 0,
                    "Europe/Paris": 1,
                }
                offset_hours = tz_offsets.get(timezone_name, 8)
                now = datetime.now(tz.utc) + timedelta(hours=offset_hours)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"当前时间 ({timezone_name}): {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            except Exception:
                now = datetime.now()
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
        
        elif name == "search_docs":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            # 模拟搜索结果
            mock_results = [
                {"title": f"文档 1: {query} 相关内容", "score": 0.95},
                {"title": f"文档 2: {query} 参考资料", "score": 0.87},
                {"title": f"文档 3: {query} 使用指南", "score": 0.82},
            ][:limit]
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"找到 {len(mock_results)} 个与 '{query}' 相关的文档:\n" + 
                               "\n".join([f"- {r['title']} (相关度: {r['score']})" for r in mock_results])
                    }
                ]
            }
        
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"未知工具: {name}"
                    }
                ],
                "isError": True
            }
    
    @staticmethod
    async def read_resource(uri: str) -> Dict[str, Any]:
        """读取演示资源"""
        if uri == "demo://config/app":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "app_name": "UI Config 智能配置系统",
                            "version": "1.0.0",
                            "debug": True
                        }, ensure_ascii=False, indent=2)
                    }
                ]
            }
        elif uri == "demo://docs/readme":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": "# UI Config 智能配置系统\n\n这是一个基于 VL 模型的 UI 配置智能生成系统。\n\n## 功能\n- 图片解析\n- 配置生成\n- MCP 集成"
                    }
                ]
            }
        else:
            return {
                "contents": [],
                "error": f"Resource not found: {uri}"
            }
    
    @staticmethod
    async def get_prompt(name: str, arguments: Dict[str, str]) -> Dict[str, Any]:
        """获取演示提示模板"""
        if name == "greeting":
            user_name = arguments.get("name", "用户")
            language = arguments.get("language", "zh")
            
            if language == "en":
                text = f"Hello, {user_name}! Welcome to the UI Config system."
            else:
                text = f"你好，{user_name}！欢迎使用 UI Config 智能配置系统。"
            
            return {
                "description": "问候语提示",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": text
                        }
                    }
                ]
            }
        
        elif name == "code_review":
            code = arguments.get("code", "")
            language = arguments.get("language", "python")
            
            return {
                "description": "代码审查提示",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"请审查以下 {language} 代码:\n\n```{language}\n{code}\n```\n\n请指出潜在问题和改进建议。"
                        }
                    }
                ]
            }
        
        else:
            return {
                "error": f"Prompt not found: {name}"
            }


# 演示服务器实例
demo_mcp_server = DemoMCPServer()

