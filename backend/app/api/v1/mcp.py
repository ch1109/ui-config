# app/api/v1/mcp.py
"""
MCP 服务器管理 API
对应模块: M6
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import httpx

from app.database import get_db
from app.models.mcp_server import MCPServer
from app.core.exceptions import InvalidJsonError

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Server"])


# REQ-M6-001: 预制 MCP 服务器配置
PRESET_MCP_SERVERS = {
    "context7": {
        "name": "Context7",
        "description": "官方文档搜索 MCP 服务器，提供 resolve-library-id 和 get-library-docs 工具，用于获取最新的库文档",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp@latest"],
        "tools": ["resolve-library-id", "get-library-docs"],
        "is_preset": True,
        "requires_node": True
    },
    "everything": {
        "name": "Everything Server",
        "description": "MCP 官方测试服务器，包含完整的 tools、resources、prompts 示例，非常适合验证 MCP 功能",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything@latest"],
        "tools": ["echo", "add", "longRunningOperation", "sampleLLM", "getTinyImage", "printEnv", "annotatedMessage"],
        "is_preset": True,
        "requires_node": True
    }
}


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""
    name: str
    server_url: str
    health_check_path: Optional[str] = "/health"
    auth_type: Optional[str] = "none"  # none, api_key, oauth
    auth_config: Optional[Dict[str, str]] = None
    tools: List[str] = []
    description: Optional[str] = None


class MCPServerResponse(BaseModel):
    """MCP 服务器响应"""
    id: int
    name: str
    server_url: Optional[str] = None  # HTTP 服务器 URL
    transport: str = "http"  # stdio 或 http
    command: Optional[str] = None  # stdio 命令
    args: Optional[List[str]] = None  # stdio 参数
    status: str  # enabled, disabled, error, running
    tools: List[str]
    is_preset: bool
    description: Optional[str] = None
    last_check: Optional[str] = None


@router.get("", response_model=List[MCPServerResponse])
async def list_mcp_servers(db: AsyncSession = Depends(get_db)):
    """
    获取 MCP 服务器列表
    
    对应需求: REQ-M6-004
    """
    result = await db.execute(select(MCPServer))
    servers = result.scalars().all()
    
    # 构建响应列表
    response_list = []
    
    # 添加预制服务器
    preset_id_counter = -1  # 使用负数 ID 区分预置服务器
    for key, preset in PRESET_MCP_SERVERS.items():
        # 检查是否已有用户配置
        existing = next((s for s in servers if s.preset_key == key), None)
        transport = preset.get("transport", "http")
        
        if existing:
            response_list.append(MCPServerResponse(
                id=existing.id,
                name=preset["name"],
                server_url=preset.get("server_url"),
                transport=transport,
                command=preset.get("command") if transport == "stdio" else None,
                args=preset.get("args") if transport == "stdio" else None,
                status=existing.status,
                tools=preset["tools"],
                is_preset=True,
                description=preset.get("description"),
                last_check=existing.last_check.isoformat() if existing.last_check else None
            ))
        else:
            response_list.append(MCPServerResponse(
                id=preset_id_counter,
                name=preset["name"],
                server_url=preset.get("server_url"),
                transport=transport,
                command=preset.get("command") if transport == "stdio" else None,
                args=preset.get("args") if transport == "stdio" else None,
                status="disabled",
                tools=preset["tools"],
                is_preset=True,
                description=preset.get("description"),
                last_check=None
            ))
        preset_id_counter -= 1
    
    # 添加自定义服务器
    for server in servers:
        if not server.preset_key:
            response_list.append(MCPServerResponse(
                id=server.id,
                name=server.name,
                server_url=server.server_url,
                transport="http",  # 自定义服务器目前只支持 HTTP
                status=server.status,
                tools=server.tools or [],
                is_preset=False,
                description=server.description,
                last_check=server.last_check.isoformat() if server.last_check else None
            ))
    
    return response_list


@router.post("/{preset_key}/toggle")
async def toggle_preset_server(
    preset_key: str,
    enable: bool,
    db: AsyncSession = Depends(get_db)
):
    """
    启用/禁用预制 MCP 服务器
    
    对应需求: REQ-M6-005
    """
    if preset_key not in PRESET_MCP_SERVERS:
        raise HTTPException(status_code=404, detail="预制服务器不存在")
    
    result = await db.execute(
        select(MCPServer).where(MCPServer.preset_key == preset_key)
    )
    existing = result.scalar_one_or_none()
    
    if not existing:
        # 创建配置记录
        preset = PRESET_MCP_SERVERS[preset_key]
        existing = MCPServer(
            preset_key=preset_key,
            name=preset["name"],
            server_url=preset.get("server_url", ""),  # stdio 服务器可能没有 URL
            tools=preset["tools"],
            description=preset.get("description"),
            status="enabled" if enable else "disabled"
        )
        db.add(existing)
    else:
        existing.status = "enabled" if enable else "disabled"
    
    await db.commit()
    
    return {"success": True, "status": existing.status}


@router.post("/upload")
async def upload_mcp_config(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    上传 MCP 配置文件
    
    对应需求: REQ-M6-006, REQ-M6-007, REQ-M6-011, REQ-M6-012
    """
    # REQ-M6-003: 文件大小限制 (1MB)
    content = await file.read()
    if len(content) > 1 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="配置文件不能超过 1MB")
    
    # REQ-M6-011: JSON 格式验证
    try:
        config = json.loads(content)
    except json.JSONDecodeError:
        raise InvalidJsonError()
    
    # 验证必需字段
    if "server_url" not in config:
        raise HTTPException(status_code=400, detail="缺少 server_url 字段")
    if "tools" not in config:
        raise HTTPException(status_code=400, detail="缺少 tools 字段")
    
    # REQ-M6-013: 检查是否重复
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.server_url == config["server_url"],
            MCPServer.preset_key == None
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return {
            "warning": "duplicate",
            "message": "该服务器已存在，是否覆盖现有配置？",
            "existing_id": existing.id
        }
    
    # REQ-M6-012: 连通性测试
    health_check_path = config.get("health_check_path", "/health")
    connectivity_ok = await test_server_connectivity(
        config["server_url"],
        health_check_path
    )
    
    # 保存配置
    server = MCPServer(
        name=config.get("name", "自定义 MCP"),
        server_url=config["server_url"],
        health_check_path=health_check_path,
        tools=config["tools"],
        auth_type=config.get("auth_type", "none"),
        auth_config=config.get("auth_config"),
        description=config.get("description"),
        status="enabled" if connectivity_ok else "error"
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    response = {
        "success": True,
        "id": server.id,
        "connectivity": connectivity_ok
    }
    
    if not connectivity_ok:
        response["warning"] = "服务器连接失败，配置已保存但可能无法正常使用"
    
    return response


@router.post("/config")
async def add_mcp_config(
    config: MCPServerConfig,
    db: AsyncSession = Depends(get_db)
):
    """
    通过代码编辑器方式添加 MCP 配置
    
    对应需求: REQ-M6-008
    """
    # REQ-M6-013: 检查是否重复
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.server_url == config.server_url,
            MCPServer.preset_key == None
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return {
            "warning": "duplicate",
            "message": "该服务器已存在，是否覆盖现有配置？",
            "existing_id": existing.id
        }
    
    # REQ-M6-012: 连通性测试
    connectivity_ok = await test_server_connectivity(
        config.server_url,
        config.health_check_path or "/health"
    )
    
    # 保存配置
    server = MCPServer(
        name=config.name,
        server_url=config.server_url,
        health_check_path=config.health_check_path or "/health",
        tools=config.tools,
        auth_type=config.auth_type or "none",
        auth_config=config.auth_config,
        description=config.description,
        status="enabled" if connectivity_ok else "error"
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    response = {
        "success": True,
        "id": server.id,
        "connectivity": connectivity_ok
    }
    
    if not connectivity_ok:
        response["warning"] = "服务器连接失败，配置已保存但可能无法正常使用"
    
    return response


async def test_server_connectivity(url: str, health_check_path: str) -> bool:
    """
    测试 MCP 服务器连通性
    
    对应需求: REQ-M6-012, REQ-M6-015
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url.rstrip('/')}{health_check_path}")
            return response.status_code == 200
    except Exception:
        return False


@router.put("/{server_id}")
async def update_mcp_server(
    server_id: int,
    config: MCPServerConfig,
    db: AsyncSession = Depends(get_db)
):
    """
    更新 MCP 服务器配置
    
    对应需求: REQ-M6-009
    """
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    
    if server.preset_key:
        raise HTTPException(status_code=400, detail="不能修改预制服务器配置")
    
    # 更新字段
    server.name = config.name
    server.server_url = config.server_url
    server.health_check_path = config.health_check_path or "/health"
    server.tools = config.tools
    server.auth_type = config.auth_type or "none"
    server.auth_config = config.auth_config
    server.description = config.description
    
    # 重新测试连通性
    connectivity_ok = await test_server_connectivity(
        config.server_url,
        config.health_check_path or "/health"
    )
    server.status = "enabled" if connectivity_ok else "error"
    server.last_check = datetime.utcnow()
    
    await db.commit()
    
    return {
        "success": True,
        "connectivity": connectivity_ok
    }


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除自定义 MCP 服务器
    
    对应需求: REQ-M6-010
    """
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    
    if server.preset_key:
        raise HTTPException(status_code=400, detail="不能删除预制服务器")
    
    await db.delete(server)
    await db.commit()
    
    return {"success": True}


@router.post("/{server_id}/test")
async def test_mcp_connection(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    测试 MCP 服务器连通性
    """
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        # 检查是否是预置服务器
        for key, preset in PRESET_MCP_SERVERS.items():
            if server_id == 0:
                # 测试第一个预置服务器
                connectivity_ok = await test_server_connectivity(
                    preset["server_url"],
                    "/health"
                )
                return {
                    "success": True,
                    "connectivity": connectivity_ok,
                    "server_url": preset["server_url"]
                }
        raise HTTPException(status_code=404, detail="服务器不存在")
    
    connectivity_ok = await test_server_connectivity(
        server.server_url,
        server.health_check_path or "/health"
    )
    
    # 更新状态
    server.status = "enabled" if connectivity_ok else "error"
    server.last_check = datetime.utcnow()
    await db.commit()
    
    return {
        "success": True,
        "connectivity": connectivity_ok,
        "server_url": server.server_url
    }

