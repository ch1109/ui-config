# app/api/v1/mcp_context.py
"""
MCP 上下文 API
提供 MCP 工具信息给前端和 LLM 使用

基于调研结果：
- 参考 Cursor/Claude Desktop 的 MCP 集成方式
- 提供系统提示词注入和 API tools 格式两种输出
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.services.mcp_tools_service import mcp_tools_service, MCPToolInfo


router = APIRouter(prefix="/api/v1/mcp-context", tags=["MCP Context"])


class MCPContextResponse(BaseModel):
    """MCP 上下文响应"""
    servers: List[Dict[str, Any]]
    tools: List[Dict[str, Any]]
    system_prompt_snippet: str
    api_tools_openai: List[Dict[str, Any]]
    api_tools_anthropic: List[Dict[str, Any]]
    total_enabled_servers: int
    total_available_tools: int
    generated_at: str


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_name: str  # 格式: server_key__tool_name
    arguments: Dict[str, Any] = {}


@router.get("", response_model=MCPContextResponse)
async def get_mcp_context(db: AsyncSession = Depends(get_db)):
    """
    获取完整的 MCP 上下文信息
    
    返回:
    - servers: 已启用的服务器列表
    - tools: 可用的工具列表
    - system_prompt_snippet: 可注入到系统提示词的 MCP 工具描述
    - api_tools_openai: OpenAI API 格式的工具定义
    - api_tools_anthropic: Anthropic API 格式的工具定义
    - total_enabled_servers: 已启用的服务器数量
    - total_available_tools: 可用的工具数量
    
    用途:
    1. 前端显示 MCP 工具状态
    2. 将 system_prompt_snippet 注入到 AI 的系统提示词中
    3. 将 api_tools_* 传递给 AI API 进行函数调用
    """
    context = await mcp_tools_service.get_full_context(db)
    return context


@router.get("/system-prompt")
async def get_system_prompt_snippet(
    include_unavailable: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    获取 MCP 工具的系统提示词片段
    
    这个片段可以追加到主系统提示词后面，告诉 AI 有哪些 MCP 工具可用
    
    Args:
        include_unavailable: 是否包含不可用的工具（默认不包含）
        
    Returns:
        系统提示词片段字符串
    """
    servers = await mcp_tools_service.get_all_enabled_servers(db)
    snippet = mcp_tools_service.format_for_system_prompt(servers, include_unavailable)
    
    return {
        "success": True,
        "snippet": snippet,
        "servers_count": len(servers),
        "tools_count": sum(
            len([t for t in s.tools if t.is_available or include_unavailable]) 
            for s in servers
        )
    }


@router.get("/tools")
async def get_available_tools(
    format: str = "list",  # list, openai, anthropic
    db: AsyncSession = Depends(get_db)
):
    """
    获取可用的 MCP 工具列表
    
    Args:
        format: 输出格式
            - list: 简单列表格式
            - openai: OpenAI API tools 参数格式
            - anthropic: Anthropic API tools 参数格式
    
    Returns:
        工具列表（格式取决于 format 参数）
    """
    tools = await mcp_tools_service.get_available_tools(db)
    
    if format == "openai":
        return {
            "success": True,
            "format": "openai",
            "tools": mcp_tools_service.format_for_api_tools(tools),
            "count": len(tools)
        }
    elif format == "anthropic":
        return {
            "success": True,
            "format": "anthropic",
            "tools": mcp_tools_service.format_for_anthropic_tools(tools),
            "count": len(tools)
        }
    else:
        return {
            "success": True,
            "format": "list",
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "server_name": t.server_name,
                    "server_key": t.server_key,
                    "input_schema": t.input_schema,
                    "is_available": t.is_available
                }
                for t in tools
            ],
            "count": len(tools)
        }


@router.get("/servers")
async def get_enabled_servers(db: AsyncSession = Depends(get_db)):
    """
    获取已启用的 MCP 服务器列表
    
    返回每个服务器的详细信息，包括其工具列表
    """
    servers = await mcp_tools_service.get_all_enabled_servers(db)
    
    return {
        "success": True,
        "servers": [
            {
                "key": s.key,
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "transport": s.transport,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "is_available": t.is_available,
                        "input_schema": t.input_schema
                    }
                    for t in s.tools
                ],
                "resources_count": s.resources_count,
                "prompts_count": s.prompts_count
            }
            for s in servers
        ],
        "count": len(servers)
    }

