# app/services/mcp_tools_service.py
"""
MCP 工具信息服务
负责动态获取、格式化 MCP 工具信息，并提供给系统提示词和 LLM
基于调研结果：参考 Cursor/Claude Desktop 的实现方式
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.mcp_server import MCPServer
from app.services.stdio_mcp_manager import stdio_mcp_manager
from app.api.v1.mcp import PRESET_MCP_SERVERS

logger = logging.getLogger(__name__)


@dataclass
class MCPToolInfo:
    """MCP 工具信息"""
    name: str
    description: str
    server_name: str
    server_key: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    is_available: bool = True


@dataclass
class MCPServerInfo:
    """MCP 服务器信息"""
    key: str
    name: str
    description: str
    status: str  # enabled, disabled, running, error
    transport: str  # stdio, http
    tools: List[MCPToolInfo] = field(default_factory=list)
    resources_count: int = 0
    prompts_count: int = 0


class MCPToolsService:
    """
    MCP 工具信息服务
    
    主要功能:
    1. 获取所有已启用的 MCP 服务器及其工具列表
    2. 格式化工具信息为系统提示词格式
    3. 格式化工具信息为 OpenAI/Claude API 的 tools 参数格式
    """
    
    async def get_all_enabled_servers(
        self, 
        db: AsyncSession
    ) -> List[MCPServerInfo]:
        """
        获取所有已启用的 MCP 服务器及其工具信息
        
        Args:
            db: 数据库会话
            
        Returns:
            服务器信息列表
        """
        servers = []
        
        # 1. 获取数据库中的服务器配置
        result = await db.execute(select(MCPServer).where(MCPServer.status == "enabled"))
        db_servers = result.scalars().all()
        
        # 2. 处理预置服务器
        for key, preset in PRESET_MCP_SERVERS.items():
            # 检查是否已在数据库中启用
            db_record = next((s for s in db_servers if s.preset_key == key), None)
            is_db_enabled = db_record is not None
            
            # 检查 stdio 服务器是否正在运行（即使数据库中没有启用记录）
            is_running = stdio_mcp_manager.is_running(key)
            
            # 如果既没有数据库启用，也没有正在运行，则跳过
            if not is_db_enabled and not is_running:
                continue
            
            # 获取 session（如果正在运行）
            session = stdio_mcp_manager.get_session(key) if is_running else None
            
            server_info = MCPServerInfo(
                key=key,
                name=preset["name"],
                description=preset.get("description", ""),
                status="running" if is_running else "enabled",
                transport=preset.get("transport", "stdio"),
                resources_count=len(session.resources) if session else 0,
                prompts_count=len(session.prompts) if session else 0
            )
            
            # 获取工具列表
            if session and session.tools:
                for tool in session.tools:
                    server_info.tools.append(MCPToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        server_name=preset["name"],
                        server_key=key,
                        input_schema=tool.get("inputSchema", {}),
                        is_available=True
                    ))
            else:
                # 服务器未运行，使用预置的工具列表
                for tool_name in preset.get("tools", []):
                    server_info.tools.append(MCPToolInfo(
                        name=tool_name,
                        description=f"{tool_name} (需要启动服务器才能使用)",
                        server_name=preset["name"],
                        server_key=key,
                        is_available=False
                    ))
            
            servers.append(server_info)
        
        # 3. 处理自定义 HTTP 服务器
        for db_server in db_servers:
            if db_server.preset_key:
                continue  # 预置服务器已处理
            
            server_info = MCPServerInfo(
                key=f"custom_{db_server.id}",
                name=db_server.name,
                description=db_server.description or "",
                status=db_server.status,
                transport="http"
            )
            
            # 从数据库中获取工具列表
            for tool_name in (db_server.tools or []):
                server_info.tools.append(MCPToolInfo(
                    name=tool_name,
                    description=tool_name,
                    server_name=db_server.name,
                    server_key=f"custom_{db_server.id}",
                    is_available=db_server.status == "enabled"
                ))
            
            servers.append(server_info)
        
        return servers
    
    async def get_available_tools(
        self, 
        db: AsyncSession
    ) -> List[MCPToolInfo]:
        """
        获取所有可用的 MCP 工具
        
        只返回已启用且正在运行的服务器的工具
        """
        tools = []
        servers = await self.get_all_enabled_servers(db)
        
        for server in servers:
            for tool in server.tools:
                if tool.is_available:
                    tools.append(tool)
        
        return tools
    
    def format_for_system_prompt(
        self, 
        servers: List[MCPServerInfo],
        include_unavailable: bool = False
    ) -> str:
        """
        将 MCP 工具信息格式化为系统提示词格式
        
        这是根据调研结果，参考业界最佳实践设计的格式
        
        Args:
            servers: 服务器信息列表
            include_unavailable: 是否包含不可用的工具
            
        Returns:
            格式化的系统提示词片段
        """
        if not servers:
            return ""
        
        lines = [
            "",
            "## 可用的 MCP 工具",
            "",
            "以下是当前可用的 MCP (Model Context Protocol) 工具，你可以使用这些工具来获取额外信息或执行操作：",
            ""
        ]
        
        for server in servers:
            available_tools = [t for t in server.tools if t.is_available or include_unavailable]
            
            if not available_tools:
                continue
            
            lines.append(f"### {server.name}")
            if server.description:
                lines.append(f"*{server.description}*")
            lines.append(f"状态: {'🟢 运行中' if server.status == 'running' else '🟡 已启用'}")
            lines.append("")
            
            for tool in available_tools:
                availability = "" if tool.is_available else " ⚠️ (不可用)"
                lines.append(f"- **{tool.name}**{availability}")
                if tool.description:
                    lines.append(f"  - 描述: {tool.description}")
                
                # 添加参数信息
                if tool.input_schema and tool.input_schema.get("properties"):
                    props = tool.input_schema["properties"]
                    required = tool.input_schema.get("required", [])
                    params = []
                    for param_name, param_info in props.items():
                        req_mark = "*" if param_name in required else ""
                        param_type = param_info.get("type", "any")
                        param_desc = param_info.get("description", "")
                        params.append(f"`{param_name}{req_mark}` ({param_type}): {param_desc}")
                    
                    if params:
                        lines.append(f"  - 参数:")
                        for param in params:
                            lines.append(f"    - {param}")
            
            lines.append("")
        
        lines.extend([
            "### 使用说明",
            "1. 要调用工具，请明确指定工具名称和所需参数",
            "2. 带 * 的参数为必填参数",
            "3. 状态为「运行中」的服务器工具可以直接使用",
            "4. 如果需要使用未运行的服务器工具，请先提示用户启动对应服务器",
            ""
        ])
        
        return "\n".join(lines)
    
    def format_for_api_tools(
        self, 
        tools: List[MCPToolInfo]
    ) -> List[Dict[str, Any]]:
        """
        将 MCP 工具信息格式化为 OpenAI/Claude API 的 tools 参数格式
        
        这是标准的 function calling 格式，可直接用于 API 调用
        
        Args:
            tools: 工具信息列表
            
        Returns:
            API tools 参数格式的工具列表
        """
        api_tools = []
        
        for tool in tools:
            if not tool.is_available:
                continue
            
            api_tool = {
                "type": "function",
                "function": {
                    "name": f"{tool.server_key}__{tool.name}",  # 使用命名空间避免冲突
                    "description": f"[{tool.server_name}] {tool.description}" if tool.description else f"来自 {tool.server_name} 的工具",
                    "parameters": tool.input_schema if tool.input_schema else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            api_tools.append(api_tool)
        
        return api_tools
    
    def format_for_anthropic_tools(
        self, 
        tools: List[MCPToolInfo]
    ) -> List[Dict[str, Any]]:
        """
        将 MCP 工具信息格式化为 Anthropic Claude API 的工具格式
        
        Claude API 的工具格式与 OpenAI 略有不同
        """
        anthropic_tools = []
        
        for tool in tools:
            if not tool.is_available:
                continue
            
            anthropic_tool = {
                "name": f"{tool.server_key}__{tool.name}",
                "description": f"[{tool.server_name}] {tool.description}" if tool.description else f"来自 {tool.server_name} 的工具",
                "input_schema": tool.input_schema if tool.input_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            anthropic_tools.append(anthropic_tool)
        
        return anthropic_tools
    
    async def get_full_context(
        self, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        获取完整的 MCP 上下文信息
        
        包含服务器列表、工具列表、系统提示词片段等
        """
        servers = await self.get_all_enabled_servers(db)
        tools = []
        for server in servers:
            tools.extend([t for t in server.tools if t.is_available])
        
        return {
            "servers": [
                {
                    "key": s.key,
                    "name": s.name,
                    "description": s.description,
                    "status": s.status,
                    "transport": s.transport,
                    "tools_count": len(s.tools),
                    "resources_count": s.resources_count,
                    "prompts_count": s.prompts_count
                }
                for s in servers
            ],
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "server": t.server_name,
                    "is_available": t.is_available
                }
                for t in tools
            ],
            "system_prompt_snippet": self.format_for_system_prompt(servers),
            "api_tools_openai": self.format_for_api_tools(tools),
            "api_tools_anthropic": self.format_for_anthropic_tools(tools),
            "total_enabled_servers": len(servers),
            "total_available_tools": len([t for t in tools if t.is_available]),
            "generated_at": datetime.now().isoformat()
        }
    
    def parse_tool_call(self, tool_name: str) -> tuple[str, str]:
        """
        解析工具调用名称，提取服务器 key 和工具名
        
        工具名格式: server_key__tool_name
        
        Returns:
            (server_key, tool_name)
        """
        if "__" in tool_name:
            parts = tool_name.split("__", 1)
            return parts[0], parts[1]
        return "", tool_name


# 创建全局单例
mcp_tools_service = MCPToolsService()

