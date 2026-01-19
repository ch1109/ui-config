# app/api/v1/mcp_test.py
"""
MCP 测试 API
提供 MCP 功能的测试接口，用于验证 MCP 工具调用、资源获取等功能
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import logging
import time

from app.database import get_db
from app.models.mcp_server import MCPServer
from app.services.mcp_client_service import (
    mcp_client,
    demo_mcp_server,
    MCPTool,
    MCPResource,
    MCPPrompt
)
from app.services.stdio_mcp_manager import stdio_mcp_manager
from app.services.sse_mcp_client import sse_mcp_client, SSEConnectionState
from app.api.v1.mcp import PRESET_MCP_SERVERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp-test", tags=["MCP Test"])


# ========== 请求/响应模型 ==========

class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_name: str
    arguments: Dict[str, Any] = {}
    server_id: Optional[int] = None  # None 表示使用内置演示服务器


class ResourceReadRequest(BaseModel):
    """资源读取请求"""
    uri: str
    server_id: Optional[int] = None


class PromptGetRequest(BaseModel):
    """获取提示模板请求"""
    name: str
    arguments: Dict[str, str] = {}
    server_id: Optional[int] = None


class MCPTestResult(BaseModel):
    """MCP 测试结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


# ========== 内置演示服务器 API ==========

@router.get("/demo/tools")
async def list_demo_tools():
    """
    获取内置演示服务器的工具列表
    
    用于测试 MCP 工具发现功能
    """
    tools = demo_mcp_server.get_tools()
    return {
        "success": True,
        "server": "demo",
        "tools": tools
    }


@router.post("/demo/tools/call")
async def call_demo_tool(request: ToolCallRequest):
    """
    调用内置演示服务器的工具
    
    支持的工具:
    - echo: 回显消息
    - calculate: 数学计算
    - get_time: 获取时间
    - search_docs: 搜索文档
    """
    import time
    start_time = time.time()
    
    try:
        result = await demo_mcp_server.call_tool(
            request.tool_name,
            request.arguments
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=not result.get("isError", False),
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/demo/resources")
async def list_demo_resources():
    """
    获取内置演示服务器的资源列表
    """
    resources = demo_mcp_server.get_resources()
    return {
        "success": True,
        "server": "demo",
        "resources": resources
    }


@router.post("/demo/resources/read")
async def read_demo_resource(request: ResourceReadRequest):
    """
    读取内置演示服务器的资源
    """
    import time
    start_time = time.time()
    
    try:
        result = await demo_mcp_server.read_resource(request.uri)
        duration_ms = (time.time() - start_time) * 1000
        
        has_error = "error" in result and result["error"]
        
        return MCPTestResult(
            success=not has_error,
            data=result,
            error=result.get("error") if has_error else None,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Resource read error: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/demo/prompts")
async def list_demo_prompts():
    """
    获取内置演示服务器的提示模板列表
    """
    prompts = demo_mcp_server.get_prompts()
    return {
        "success": True,
        "server": "demo",
        "prompts": prompts
    }


@router.post("/demo/prompts/get")
async def get_demo_prompt(request: PromptGetRequest):
    """
    获取内置演示服务器的提示模板内容
    """
    import time
    start_time = time.time()
    
    try:
        result = await demo_mcp_server.get_prompt(
            request.name,
            request.arguments
        )
        duration_ms = (time.time() - start_time) * 1000
        
        has_error = "error" in result
        
        return MCPTestResult(
            success=not has_error,
            data=result,
            error=result.get("error") if has_error else None,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Prompt get error: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


# ========== 外部 MCP 服务器 API ==========

@router.get("/servers/{server_id}/tools")
async def list_server_tools(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定 MCP 服务器的工具列表
    """
    # 获取服务器配置
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    
    if server.status != "enabled":
        raise HTTPException(status_code=400, detail="MCP 服务器未启用")
    
    try:
        # 连接服务器
        session_id = await mcp_client.connect_http(
            server.server_url,
            server.auth_config.get("api_key") if server.auth_config else None
        )
        
        try:
            tools = await mcp_client.list_tools(session_id)
            return {
                "success": True,
                "server": server.name,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema
                    }
                    for t in tools
                ]
            }
        finally:
            await mcp_client.disconnect(session_id)
            
    except Exception as e:
        logger.error(f"Failed to list tools from server {server_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取工具列表失败: {str(e)}"
        )


@router.post("/servers/{server_id}/tools/call")
async def call_server_tool(
    server_id: int,
    request: ToolCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    调用指定 MCP 服务器的工具
    """
    import time
    start_time = time.time()
    
    # 获取服务器配置
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    
    if server.status != "enabled":
        raise HTTPException(status_code=400, detail="MCP 服务器未启用")
    
    try:
        # 连接服务器
        session_id = await mcp_client.connect_http(
            server.server_url,
            server.auth_config.get("api_key") if server.auth_config else None
        )
        
        try:
            result = await mcp_client.call_tool(
                session_id,
                request.tool_name,
                request.arguments
            )
            duration_ms = (time.time() - start_time) * 1000
            
            return MCPTestResult(
                success=True,
                data=result,
                duration_ms=round(duration_ms, 2)
            )
        finally:
            await mcp_client.disconnect(session_id)
            
    except Exception as e:
        logger.error(f"Tool call failed on server {server_id}: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


# ========== 批量测试 API ==========

@router.post("/demo/batch-test")
async def batch_test_demo_tools():
    """
    批量测试内置演示服务器的所有工具
    
    用于快速验证 MCP 功能是否正常
    """
    import time
    
    results = []
    
    # 测试 echo 工具
    start = time.time()
    echo_result = await demo_mcp_server.call_tool("echo", {"message": "Hello MCP!"})
    results.append({
        "tool": "echo",
        "success": not echo_result.get("isError", False),
        "result": echo_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 测试 calculate 工具
    start = time.time()
    calc_result = await demo_mcp_server.call_tool("calculate", {"expression": "2 + 3 * 4"})
    results.append({
        "tool": "calculate",
        "success": not calc_result.get("isError", False),
        "result": calc_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 测试 get_time 工具
    start = time.time()
    time_result = await demo_mcp_server.call_tool("get_time", {"timezone": "Asia/Shanghai"})
    results.append({
        "tool": "get_time",
        "success": not time_result.get("isError", False),
        "result": time_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 测试 search_docs 工具
    start = time.time()
    search_result = await demo_mcp_server.call_tool("search_docs", {"query": "MCP", "limit": 3})
    results.append({
        "tool": "search_docs",
        "success": not search_result.get("isError", False),
        "result": search_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 测试资源读取
    start = time.time()
    resource_result = await demo_mcp_server.read_resource("demo://config/app")
    results.append({
        "type": "resource",
        "uri": "demo://config/app",
        "success": "error" not in resource_result,
        "result": resource_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 测试提示模板
    start = time.time()
    prompt_result = await demo_mcp_server.get_prompt("greeting", {"name": "测试用户"})
    results.append({
        "type": "prompt",
        "name": "greeting",
        "success": "error" not in prompt_result,
        "result": prompt_result,
        "duration_ms": round((time.time() - start) * 1000, 2)
    })
    
    # 统计结果
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    
    return {
        "success": passed == total,
        "summary": f"{passed}/{total} 测试通过",
        "results": results
    }


# ========== 流式输出 API ==========

@router.get("/demo/stream-test")
async def stream_test():
    """
    流式输出测试
    
    演示 MCP 工具调用的流式输出能力
    """
    async def generate():
        yield "data: " + json.dumps({"type": "start", "message": "开始 MCP 流式测试..."}) + "\n\n"
        
        # 模拟流式调用多个工具
        tools = [
            ("echo", {"message": "流式测试消息 1"}),
            ("calculate", {"expression": "100 / 4"}),
            ("get_time", {}),
            ("search_docs", {"query": "MCP 协议", "limit": 2})
        ]
        
        for tool_name, args in tools:
            await asyncio.sleep(0.5)  # 模拟延迟
            
            result = await demo_mcp_server.call_tool(tool_name, args)
            
            yield "data: " + json.dumps({
                "type": "tool_result",
                "tool": tool_name,
                "result": result
            }, ensure_ascii=False) + "\n\n"
        
        yield "data: " + json.dumps({"type": "complete", "message": "所有工具调用完成"}) + "\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


# ========== 真实 MCP 服务器 API (stdio) ==========

class StdioServerRequest(BaseModel):
    """Stdio 服务器请求"""
    server_key: str  # context7, everything


class StdioToolCallRequest(BaseModel):
    """Stdio 工具调用请求"""
    server_key: str
    tool_name: str
    arguments: Dict[str, Any] = {}


class StdioResourceRequest(BaseModel):
    """Stdio 资源请求"""
    server_key: str
    uri: str


class StdioPromptRequest(BaseModel):
    """Stdio 提示模板请求"""
    server_key: str
    name: str
    arguments: Dict[str, str] = {}


@router.get("/stdio/status")
async def get_stdio_servers_status():
    """
    获取所有 stdio MCP 服务器的状态
    """
    return {
        "success": True,
        "servers": stdio_mcp_manager.get_status(),
        "available_presets": list(PRESET_MCP_SERVERS.keys())
    }


@router.post("/stdio/start")
async def start_stdio_server(request: StdioServerRequest, db: AsyncSession = Depends(get_db)):
    """
    启动 stdio MCP 服务器
    
    支持预置服务器和自定义服务器:
    - 预置: context7, everything, wttr
    - 自定义: custom_{server_id}
    """
    server_key = request.server_key
    
    # 判断是预置服务器还是自定义服务器
    if server_key in PRESET_MCP_SERVERS:
        preset = PRESET_MCP_SERVERS[server_key]
        
        if preset.get("transport") != "stdio":
            raise HTTPException(
                status_code=400,
                detail=f"服务器 {server_key} 不是 stdio 类型"
            )
        
        command = preset["command"]
        args = preset.get("args", [])
        env = preset.get("env", {})
    elif server_key.startswith("custom_"):
        # 自定义服务器
        try:
            server_id = int(server_key.replace("custom_", ""))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的服务器标识: {server_key}")
        
        result = await db.execute(
            select(MCPServer).where(MCPServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="服务器不存在")
        
        if server.transport != "stdio":
            raise HTTPException(status_code=400, detail="该服务器不是 STDIO 类型")
        
        if not server.command:
            raise HTTPException(status_code=400, detail="服务器未配置启动命令")
        
        command = server.command
        args = server.args or []
        env = server.env or {}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"未知的服务器: {server_key}，可用预置选项: {list(PRESET_MCP_SERVERS.keys())}，或使用 custom_{{id}} 格式"
        )
    
    # 检查是否已在运行
    if stdio_mcp_manager.is_running(server_key):
        session = stdio_mcp_manager.get_session(server_key)
        return {
            "success": True,
            "message": "服务器已在运行",
            "server_key": server_key,
            "tools_count": len(session.tools) if session else 0,
            "resources_count": len(session.resources) if session else 0,
            "prompts_count": len(session.prompts) if session else 0
        }
    
    # 启动服务器
    success, message = await stdio_mcp_manager.start_server(
        server_key=server_key,
        command=command,
        args=args,
        env=env,
        timeout=60.0  # 给 npx 更多时间下载包
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    session = stdio_mcp_manager.get_session(server_key)
    
    return {
        "success": True,
        "message": message,
        "server_key": server_key,
        "server_info": session.server_info if session else {},
        "tools_count": len(session.tools) if session else 0,
        "resources_count": len(session.resources) if session else 0,
        "prompts_count": len(session.prompts) if session else 0
    }


@router.post("/stdio/stop")
async def stop_stdio_server(request: StdioServerRequest):
    """
    停止 stdio MCP 服务器
    """
    success, message = await stdio_mcp_manager.stop_server(request.server_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message
    }


@router.get("/stdio/{server_key}/tools")
async def list_stdio_server_tools(server_key: str):
    """
    获取 stdio MCP 服务器的工具列表
    """
    if not stdio_mcp_manager.is_running(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未运行，请先启动"
        )
    
    try:
        tools = await stdio_mcp_manager.list_tools(server_key)
        return {
            "success": True,
            "server": server_key,
            "tools": tools
        }
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stdio/tools/call")
async def call_stdio_server_tool(request: StdioToolCallRequest):
    """
    调用 stdio MCP 服务器的工具
    """
    if not stdio_mcp_manager.is_running(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未运行，请先启动"
        )
    
    start_time = time.time()
    
    try:
        result = await stdio_mcp_manager.call_tool(
            request.server_key,
            request.tool_name,
            request.arguments
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/stdio/{server_key}/resources")
async def list_stdio_server_resources(server_key: str):
    """
    获取 stdio MCP 服务器的资源列表
    """
    if not stdio_mcp_manager.is_running(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未运行，请先启动"
        )
    
    try:
        resources = await stdio_mcp_manager.list_resources(server_key)
        return {
            "success": True,
            "server": server_key,
            "resources": resources
        }
    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stdio/resources/read")
async def read_stdio_server_resource(request: StdioResourceRequest):
    """
    读取 stdio MCP 服务器的资源
    """
    if not stdio_mcp_manager.is_running(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未运行，请先启动"
        )
    
    start_time = time.time()
    
    try:
        result = await stdio_mcp_manager.read_resource(
            request.server_key,
            request.uri
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Resource read failed: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/stdio/{server_key}/prompts")
async def list_stdio_server_prompts(server_key: str):
    """
    获取 stdio MCP 服务器的提示模板列表
    """
    if not stdio_mcp_manager.is_running(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未运行，请先启动"
        )
    
    try:
        prompts = await stdio_mcp_manager.list_prompts(server_key)
        return {
            "success": True,
            "server": server_key,
            "prompts": prompts
        }
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stdio/prompts/get")
async def get_stdio_server_prompt(request: StdioPromptRequest):
    """
    获取 stdio MCP 服务器的提示模板内容
    """
    if not stdio_mcp_manager.is_running(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未运行，请先启动"
        )
    
    start_time = time.time()
    
    try:
        result = await stdio_mcp_manager.get_prompt(
            request.server_key,
            request.name,
            request.arguments
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"Prompt get failed: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.post("/stdio/{server_key}/batch-test")
async def batch_test_stdio_server(server_key: str):
    """
    批量测试 stdio MCP 服务器的所有工具
    """
    if not stdio_mcp_manager.is_running(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未运行，请先启动"
        )
    
    results = []
    session = stdio_mcp_manager.get_session(server_key)
    
    if not session:
        raise HTTPException(status_code=500, detail="获取会话失败")
    
    # 测试所有工具
    for tool in session.tools[:5]:  # 最多测试 5 个工具
        tool_name = tool.get("name", "")
        start = time.time()
        
        try:
            # 根据工具的 inputSchema 构造测试参数
            test_args = _generate_test_args(tool)
            result = await stdio_mcp_manager.call_tool(server_key, tool_name, test_args)
            
            results.append({
                "type": "tool",
                "name": tool_name,
                "success": True,
                "result": result,
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
        except Exception as e:
            results.append({
                "type": "tool",
                "name": tool_name,
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
    
    # 测试资源（如果有）
    for resource in session.resources[:3]:  # 最多测试 3 个资源
        uri = resource.get("uri", "")
        start = time.time()
        
        try:
            result = await stdio_mcp_manager.read_resource(server_key, uri)
            results.append({
                "type": "resource",
                "uri": uri,
                "success": True,
                "result": result,
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
        except Exception as e:
            results.append({
                "type": "resource",
                "uri": uri,
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
    
    # 统计结果
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    
    return {
        "success": passed == total,
        "summary": f"{passed}/{total} 测试通过",
        "server": server_key,
        "results": results
    }


def _generate_test_args(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据工具的 inputSchema 生成测试参数
    """
    schema = tool.get("inputSchema", {})
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    args = {}
    
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        
        # 只为必需参数生成值
        if prop_name in required or len(required) == 0:
            if prop_type == "string":
                # 特殊处理某些常见参数名
                if "message" in prop_name.lower():
                    args[prop_name] = "Hello from MCP test!"
                elif "query" in prop_name.lower():
                    args[prop_name] = "test query"
                elif "name" in prop_name.lower():
                    args[prop_name] = "test"
                elif "library" in prop_name.lower():
                    args[prop_name] = "react"  # 用于 Context7
                else:
                    args[prop_name] = "test"
            elif prop_type == "number" or prop_type == "integer":
                args[prop_name] = 1
            elif prop_type == "boolean":
                args[prop_name] = True
            elif prop_type == "array":
                args[prop_name] = []
            elif prop_type == "object":
                args[prop_name] = {}
    
    return args


# ========== SSE MCP 服务器 API ==========

class SSEServerConnectRequest(BaseModel):
    """SSE 服务器连接请求"""
    server_key: str
    base_url: str
    sse_endpoint: str = "/sse"
    message_endpoint: str = "/message"
    auth_token: Optional[str] = None
    auth_type: str = "bearer"  # bearer, api_key, custom
    custom_headers: Optional[Dict[str, str]] = None
    auto_reconnect: bool = True


class SSEToolCallRequest(BaseModel):
    """SSE 工具调用请求"""
    server_key: str
    tool_name: str
    arguments: Dict[str, Any] = {}


class SSEResourceRequest(BaseModel):
    """SSE 资源请求"""
    server_key: str
    uri: str


class SSEPromptRequest(BaseModel):
    """SSE 提示模板请求"""
    server_key: str
    name: str
    arguments: Dict[str, str] = {}


@router.get("/sse/status")
async def get_sse_servers_status():
    """
    获取所有 SSE MCP 服务器的连接状态
    
    返回所有已连接的 SSE 服务器及其详细状态
    """
    return {
        "success": True,
        "servers": sse_mcp_client.get_status(),
        "connected_count": len(sse_mcp_client.list_connected_servers())
    }


@router.post("/sse/connect")
async def connect_sse_server(request: SSEServerConnectRequest):
    """
    连接到 SSE MCP 服务器
    
    支持 Bearer Token、API Key 和自定义认证方式
    """
    try:
        success, message = await sse_mcp_client.connect(
            server_key=request.server_key,
            base_url=request.base_url,
            sse_endpoint=request.sse_endpoint,
            message_endpoint=request.message_endpoint,
            auth_token=request.auth_token,
            auth_type=request.auth_type,
            custom_headers=request.custom_headers,
            auto_reconnect=request.auto_reconnect
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        # 获取连接后的状态
        status = sse_mcp_client.get_session_status(request.server_key)
        
        return {
            "success": True,
            "message": message,
            "server_key": request.server_key,
            "status": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE 连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/sse/connect-db/{server_id}")
async def connect_sse_server_from_db(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    从数据库配置连接 SSE MCP 服务器
    
    根据数据库中的服务器配置自动建立连接
    """
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    
    if server.transport != "sse" and server.transport != "http":
        raise HTTPException(
            status_code=400, 
            detail=f"该服务器不是 SSE/HTTP 类型 (当前: {server.transport})"
        )
    
    if not server.server_url:
        raise HTTPException(status_code=400, detail="服务器未配置 URL")
    
    server_key = f"db_{server_id}"
    
    # 获取认证配置
    auth_token = None
    auth_type = server.auth_type or "none"
    if server.auth_config:
        auth_token = server.auth_config.get("api_key") or server.auth_config.get("token")
    
    try:
        success, message = await sse_mcp_client.connect(
            server_key=server_key,
            base_url=server.server_url,
            auth_token=auth_token,
            auth_type=auth_type
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        # 更新数据库状态
        server.status = "enabled"
        await db.commit()
        
        status = sse_mcp_client.get_session_status(server_key)
        
        return {
            "success": True,
            "message": message,
            "server_key": server_key,
            "server_name": server.name,
            "status": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE 连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/sse/disconnect/{server_key}")
async def disconnect_sse_server(server_key: str):
    """
    断开 SSE MCP 服务器连接
    """
    success, message = await sse_mcp_client.disconnect(server_key)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message
    }


@router.post("/sse/reconnect/{server_key}")
async def reconnect_sse_server(server_key: str):
    """
    手动重连 SSE MCP 服务器
    """
    success, message = await sse_mcp_client.reconnect(server_key)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {
        "success": True,
        "message": message
    }


@router.get("/sse/test/{server_key}")
async def test_sse_connection(server_key: str):
    """
    测试 SSE 连接健康状态
    
    发送测试请求并返回延迟信息
    """
    is_healthy, message, latency_ms = await sse_mcp_client.test_connection(server_key)
    
    return {
        "success": is_healthy,
        "message": message,
        "latency_ms": round(latency_ms, 2)
    }


@router.get("/sse/{server_key}/tools")
async def list_sse_server_tools(server_key: str):
    """
    获取 SSE MCP 服务器的工具列表
    """
    if not sse_mcp_client.is_connected(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未连接"
        )
    
    try:
        tools = await sse_mcp_client.list_tools(server_key)
        return {
            "success": True,
            "server": server_key,
            "tools": tools
        }
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sse/tools/call")
async def call_sse_server_tool(request: SSEToolCallRequest):
    """
    调用 SSE MCP 服务器的工具
    """
    if not sse_mcp_client.is_connected(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未连接"
        )
    
    start_time = time.time()
    
    try:
        result = await sse_mcp_client.call_tool(
            request.server_key,
            request.tool_name,
            request.arguments
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"SSE 工具调用失败: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/sse/{server_key}/resources")
async def list_sse_server_resources(server_key: str):
    """
    获取 SSE MCP 服务器的资源列表
    """
    if not sse_mcp_client.is_connected(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未连接"
        )
    
    try:
        resources = await sse_mcp_client.list_resources(server_key)
        return {
            "success": True,
            "server": server_key,
            "resources": resources
        }
    except Exception as e:
        logger.error(f"获取资源列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sse/resources/read")
async def read_sse_server_resource(request: SSEResourceRequest):
    """
    读取 SSE MCP 服务器的资源
    """
    if not sse_mcp_client.is_connected(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未连接"
        )
    
    start_time = time.time()
    
    try:
        result = await sse_mcp_client.read_resource(
            request.server_key,
            request.uri
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"SSE 资源读取失败: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/sse/{server_key}/prompts")
async def list_sse_server_prompts(server_key: str):
    """
    获取 SSE MCP 服务器的提示模板列表
    """
    if not sse_mcp_client.is_connected(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未连接"
        )
    
    try:
        prompts = await sse_mcp_client.list_prompts(server_key)
        return {
            "success": True,
            "server": server_key,
            "prompts": prompts
        }
    except Exception as e:
        logger.error(f"获取提示模板列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sse/prompts/get")
async def get_sse_server_prompt(request: SSEPromptRequest):
    """
    获取 SSE MCP 服务器的提示模板内容
    """
    if not sse_mcp_client.is_connected(request.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {request.server_key} 未连接"
        )
    
    start_time = time.time()
    
    try:
        result = await sse_mcp_client.get_prompt(
            request.server_key,
            request.name,
            request.arguments
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return MCPTestResult(
            success=True,
            data=result,
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        logger.error(f"SSE 提示模板获取失败: {e}")
        return MCPTestResult(
            success=False,
            error=str(e),
            duration_ms=round((time.time() - start_time) * 1000, 2)
        )


@router.get("/sse/all-tools")
async def get_all_sse_tools():
    """
    获取所有已连接 SSE 服务器的工具列表
    
    返回聚合后的工具列表，包含服务器标识
    """
    return {
        "success": True,
        "tools": sse_mcp_client.get_all_tools(),
        "connected_servers": sse_mcp_client.list_connected_servers()
    }


@router.post("/sse/{server_key}/batch-test")
async def batch_test_sse_server(server_key: str):
    """
    批量测试 SSE MCP 服务器的所有工具
    """
    if not sse_mcp_client.is_connected(server_key):
        raise HTTPException(
            status_code=400,
            detail=f"服务器 {server_key} 未连接"
        )
    
    session = sse_mcp_client.get_session(server_key)
    if not session:
        raise HTTPException(status_code=500, detail="获取会话失败")
    
    results = []
    
    # 测试工具
    for tool in session.tools[:5]:
        tool_name = tool.get("name", "")
        start = time.time()
        
        try:
            test_args = _generate_test_args(tool)
            result = await sse_mcp_client.call_tool(server_key, tool_name, test_args)
            
            results.append({
                "type": "tool",
                "name": tool_name,
                "success": True,
                "result": result,
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
        except Exception as e:
            results.append({
                "type": "tool",
                "name": tool_name,
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
    
    # 测试资源
    for resource in session.resources[:3]:
        uri = resource.get("uri", "")
        start = time.time()
        
        try:
            result = await sse_mcp_client.read_resource(server_key, uri)
            results.append({
                "type": "resource",
                "uri": uri,
                "success": True,
                "result": result,
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
        except Exception as e:
            results.append({
                "type": "resource",
                "uri": uri,
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2)
            })
    
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    
    return {
        "success": passed == total,
        "summary": f"{passed}/{total} 测试通过",
        "server": server_key,
        "results": results
    }

