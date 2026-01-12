# app/services/human_in_loop.py
"""
人机回环（Human-in-the-Loop）服务
实现高风险操作的用户确认机制

核心原则（来自 Gemini 报告）：
1. 永远不要默认信任 LLM 的工具调用请求
2. 高风险操作必须获得用户明确授权
3. 支持用户修改参数后再执行
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid

from app.services.mcp_host_service import ToolRiskLevel, ToolCallRequest

logger = logging.getLogger(__name__)


class ConfirmationStatus(Enum):
    """确认状态"""
    PENDING = "pending"       # 等待确认
    APPROVED = "approved"     # 已批准
    REJECTED = "rejected"     # 已拒绝
    MODIFIED = "modified"     # 已修改并批准
    EXPIRED = "expired"       # 已过期


@dataclass
class ConfirmationRequest:
    """确认请求"""
    id: str
    session_id: str
    tool_call: ToolCallRequest
    risk_level: ToolRiskLevel
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    
    # 风险描述
    risk_description: str = ""
    warning_message: str = ""
    
    # 用户操作记录
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    modified_arguments: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    
    # 时间控制
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # 回调
    on_complete: Optional[Callable[['ConfirmationRequest'], Awaitable[None]]] = None


@dataclass
class RiskPolicy:
    """风险策略配置"""
    # 需要确认的风险级别
    confirmation_levels: List[ToolRiskLevel] = field(default_factory=lambda: [
        ToolRiskLevel.HIGH,
        ToolRiskLevel.CRITICAL
    ])
    
    # 超时设置（秒）
    confirmation_timeout: int = 300  # 5分钟
    
    # 是否允许修改参数
    allow_modification: bool = True
    
    # 是否需要二次确认（用于 CRITICAL 级别）
    require_double_confirmation: bool = True
    
    # 白名单工具（跳过确认）
    whitelisted_tools: List[str] = field(default_factory=list)
    
    # 黑名单工具（始终需要确认）
    blacklisted_tools: List[str] = field(default_factory=list)


# 默认的风险描述模板
RISK_DESCRIPTIONS = {
    ToolRiskLevel.LOW: {
        "description": "此操作为只读操作，不会修改任何数据",
        "warning": ""
    },
    ToolRiskLevel.MEDIUM: {
        "description": "此操作可能会访问敏感数据或执行计算",
        "warning": "请确认操作参数是否正确"
    },
    ToolRiskLevel.HIGH: {
        "description": "此操作将修改数据或执行可能产生副作用的操作",
        "warning": "⚠️ 此操作可能无法撤销，请仔细确认"
    },
    ToolRiskLevel.CRITICAL: {
        "description": "此操作为高危操作，可能导致数据丢失或系统变更",
        "warning": "🚨 危险操作！请务必确认所有参数无误后再继续"
    }
}


class HumanInLoopService:
    """
    人机回环服务
    
    功能：
    1. 管理待确认的工具调用请求
    2. 提供确认/拒绝/修改接口
    3. 支持超时自动拒绝
    4. 记录审计日志
    """
    
    def __init__(self):
        self.pending_requests: Dict[str, ConfirmationRequest] = {}
        self.completed_requests: Dict[str, ConfirmationRequest] = {}
        self.policy = RiskPolicy()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {}
        
    async def start(self):
        """启动服务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Human-in-the-Loop service started")
    
    async def stop(self):
        """停止服务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Human-in-the-Loop service stopped")
    
    async def _cleanup_loop(self):
        """定期清理过期请求"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """清理过期的请求"""
        now = datetime.now()
        expired_ids = []
        
        for req_id, request in self.pending_requests.items():
            if request.expires_at and now > request.expires_at:
                expired_ids.append(req_id)
                request.status = ConfirmationStatus.EXPIRED
                
                # 触发回调
                if request.on_complete:
                    try:
                        await request.on_complete(request)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
        
        for req_id in expired_ids:
            request = self.pending_requests.pop(req_id)
            self.completed_requests[req_id] = request
            logger.info(f"Request {req_id} expired")
    
    def set_policy(self, policy: RiskPolicy):
        """设置风险策略"""
        self.policy = policy
    
    def needs_confirmation(self, tool_call: ToolCallRequest) -> bool:
        """
        判断工具调用是否需要确认
        """
        # 检查白名单
        if tool_call.tool_name in self.policy.whitelisted_tools:
            return False
        
        # 检查黑名单
        if tool_call.tool_name in self.policy.blacklisted_tools:
            return True
        
        # 根据风险级别判断
        return tool_call.risk_level in self.policy.confirmation_levels
    
    def create_confirmation_request(
        self,
        session_id: str,
        tool_call: ToolCallRequest,
        on_complete: Optional[Callable[[ConfirmationRequest], Awaitable[None]]] = None
    ) -> ConfirmationRequest:
        """
        创建确认请求
        """
        risk_info = RISK_DESCRIPTIONS.get(tool_call.risk_level, RISK_DESCRIPTIONS[ToolRiskLevel.LOW])
        
        request = ConfirmationRequest(
            id=str(uuid.uuid4()),
            session_id=session_id,
            tool_call=tool_call,
            risk_level=tool_call.risk_level,
            risk_description=risk_info["description"],
            warning_message=risk_info["warning"],
            expires_at=datetime.now() + timedelta(seconds=self.policy.confirmation_timeout),
            on_complete=on_complete
        )
        
        self.pending_requests[request.id] = request
        logger.info(f"Created confirmation request: {request.id} for tool {tool_call.tool_name}")
        
        return request
    
    async def approve(
        self,
        request_id: str,
        approved_by: str = "user",
        modified_arguments: Optional[Dict[str, Any]] = None
    ) -> ConfirmationRequest:
        """
        批准工具调用
        """
        request = self.pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Confirmation request {request_id} not found")
        
        if request.status != ConfirmationStatus.PENDING:
            raise ValueError(f"Request {request_id} is not pending (status: {request.status})")
        
        # 检查是否过期
        if request.expires_at and datetime.now() > request.expires_at:
            request.status = ConfirmationStatus.EXPIRED
            raise ValueError(f"Request {request_id} has expired")
        
        # 更新状态
        if modified_arguments:
            request.status = ConfirmationStatus.MODIFIED
            request.modified_arguments = modified_arguments
            request.tool_call.arguments = modified_arguments
        else:
            request.status = ConfirmationStatus.APPROVED
        
        request.approved_by = approved_by
        request.approved_at = datetime.now()
        
        # 从待处理移到已完成
        del self.pending_requests[request_id]
        self.completed_requests[request_id] = request
        
        # 触发回调
        if request.on_complete:
            try:
                await request.on_complete(request)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        logger.info(f"Request {request_id} approved by {approved_by}")
        return request
    
    async def reject(
        self,
        request_id: str,
        rejected_by: str = "user",
        reason: str = ""
    ) -> ConfirmationRequest:
        """
        拒绝工具调用
        """
        request = self.pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Confirmation request {request_id} not found")
        
        if request.status != ConfirmationStatus.PENDING:
            raise ValueError(f"Request {request_id} is not pending (status: {request.status})")
        
        request.status = ConfirmationStatus.REJECTED
        request.approved_by = rejected_by
        request.approved_at = datetime.now()
        request.rejection_reason = reason
        
        # 从待处理移到已完成
        del self.pending_requests[request_id]
        self.completed_requests[request_id] = request
        
        # 触发回调
        if request.on_complete:
            try:
                await request.on_complete(request)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        logger.info(f"Request {request_id} rejected by {rejected_by}: {reason}")
        return request
    
    def get_pending_requests(
        self,
        session_id: Optional[str] = None
    ) -> List[ConfirmationRequest]:
        """
        获取待确认请求列表
        """
        requests = list(self.pending_requests.values())
        
        if session_id:
            requests = [r for r in requests if r.session_id == session_id]
        
        return sorted(requests, key=lambda r: r.created_at)
    
    def get_request(self, request_id: str) -> Optional[ConfirmationRequest]:
        """获取请求详情"""
        return self.pending_requests.get(request_id) or self.completed_requests.get(request_id)
    
    def format_for_ui(self, request: ConfirmationRequest) -> Dict[str, Any]:
        """
        格式化请求信息用于 UI 展示
        """
        return {
            "id": request.id,
            "session_id": request.session_id,
            "tool_name": request.tool_call.tool_name,
            "server_key": request.tool_call.server_key,
            "arguments": request.tool_call.arguments,
            "risk_level": request.risk_level.value,
            "risk_description": request.risk_description,
            "warning_message": request.warning_message,
            "status": request.status.value,
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "time_remaining_seconds": (
                (request.expires_at - datetime.now()).total_seconds()
                if request.expires_at and request.status == ConfirmationStatus.PENDING
                else 0
            ),
            "allow_modification": self.policy.allow_modification,
            "require_double_confirmation": (
                self.policy.require_double_confirmation and 
                request.risk_level == ToolRiskLevel.CRITICAL
            )
        }
    
    def get_audit_log(
        self,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取审计日志
        """
        all_requests = list(self.completed_requests.values())
        
        if session_id:
            all_requests = [r for r in all_requests if r.session_id == session_id]
        
        # 按时间排序
        all_requests = sorted(all_requests, key=lambda r: r.approved_at or r.created_at, reverse=True)
        
        # 限制数量
        all_requests = all_requests[:limit]
        
        return [
            {
                "id": r.id,
                "tool_name": r.tool_call.tool_name,
                "risk_level": r.risk_level.value,
                "status": r.status.value,
                "approved_by": r.approved_by,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                "rejection_reason": r.rejection_reason,
                "was_modified": r.status == ConfirmationStatus.MODIFIED
            }
            for r in all_requests
        ]


# 创建全局单例
human_in_loop_service = HumanInLoopService()

