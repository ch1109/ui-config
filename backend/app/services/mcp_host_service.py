# app/services/mcp_host_service.py
"""
MCP Host 核心服务
基于 Gemini 报告的架构理念，实现完整的 Host 功能

Host 职责：
1. 管理 LLM 生命周期
2. 聚合多个 MCP Server 的上下文
3. 处理用户输入
4. 实施权限控制和人机回环
5. 协调 ReAct 循环
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.services.stdio_mcp_manager import stdio_mcp_manager, MCPSession
from app.services.mcp_tools_service import mcp_tools_service, MCPToolInfo

logger = logging.getLogger(__name__)


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
        聚合所有已连接 MCP Server 的工具
        
        返回 OpenAI Function Calling 格式的工具列表
        """
        tools = []
        
        # 获取所有运行中的 stdio 服务器的工具
        for server_key, session in stdio_mcp_manager.sessions.items():
            if session.initialized and session.process.returncode is None:
                for tool in session.tools:
                    tool_info = MCPToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        server_name=server_key,
                        server_key=server_key,
                        input_schema=tool.get("inputSchema", {}),
                        is_available=True
                    )
                    
                    # 转换为 OpenAI 格式
                    api_tool = {
                        "type": "function",
                        "function": {
                            "name": f"{server_key}__{tool_info.name}",
                            "description": f"[{server_key}] {tool_info.description}" if tool_info.description else f"Tool from {server_key}",
                            "parameters": tool_info.input_schema if tool_info.input_schema else {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    }
                    tools.append(api_tool)
        
        return tools
    
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
        arguments: Dict[str, Any]
    ) -> ToolCallRequest:
        """
        准备工具调用请求
        
        评估风险并决定是否需要用户确认
        """
        server_key, actual_tool_name = self.parse_tool_call(tool_name)
        
        # 评估风险
        risk_level = self.assess_tool_risk(actual_tool_name, arguments)
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
    
    async def execute_tool_call(
        self,
        request: ToolCallRequest,
        force: bool = False
    ) -> ToolCallResult:
        """
        执行工具调用
        
        Args:
            request: 工具调用请求
            force: 是否跳过确认（仅用于低风险操作或已确认的操作）
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
        
        try:
            # 检查服务器是否运行
            if not stdio_mcp_manager.is_running(request.server_key):
                return ToolCallResult(
                    id=request.id,
                    success=False,
                    error=f"MCP 服务器 {request.server_key} 未运行"
                )
            
            # 调用工具
            result = await stdio_mcp_manager.call_tool(
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
        
        # 执行调用
        result = await self.execute_tool_call(request, force=True)
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
    
    def get_connected_servers(self) -> List[Dict[str, Any]]:
        """获取所有已连接的 MCP 服务器状态"""
        return stdio_mcp_manager.get_status()
    
    async def cleanup_session(self, session_id: str):
        """清理会话资源"""
        self.delete_session(session_id)
    
    async def cleanup_all(self):
        """清理所有资源"""
        self.sessions.clear()
        await stdio_mcp_manager.cleanup()


# 创建全局单例
mcp_host_service = MCPHostService()

