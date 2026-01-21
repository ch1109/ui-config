# app/services/sampling_service.py
"""
MCP Sampling 服务

实现 MCP 协议中的 Sampling 能力，允许 MCP Server 请求 Host 调用 LLM。

功能：
1. 处理 sampling/createMessage 请求
2. 安全策略（token 限制、内容过滤、速率限制）
3. 人机回环审核支持
4. 多 LLM 提供商适配

参考规范：MCP Protocol Revision 2024-11-05
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class SamplingStopReason(Enum):
    """Sampling 停止原因"""
    END_TURN = "endTurn"           # 正常完成
    STOP_SEQUENCE = "stopSequence"  # 遇到停止序列
    MAX_TOKENS = "maxTokens"        # 达到 token 上限
    ERROR = "error"                 # 错误


class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    IMAGE = "image"


class SamplingApprovalStatus(Enum):
    """Sampling 请求审核状态"""
    PENDING = "pending"       # 等待审核
    APPROVED = "approved"     # 已批准
    REJECTED = "rejected"     # 已拒绝
    AUTO_APPROVED = "auto"    # 自动批准（低风险）
    EXPIRED = "expired"       # 已过期


@dataclass
class SamplingMessage:
    """Sampling 消息"""
    role: str  # "user" 或 "assistant"
    content: Dict[str, Any]  # {"type": "text", "text": "..."} 或 {"type": "image", ...}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SamplingMessage":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", {"type": "text", "text": ""})
        )
    
    def get_text(self) -> str:
        """获取文本内容"""
        if self.content.get("type") == "text":
            return self.content.get("text", "")
        return ""


@dataclass
class ModelPreferences:
    """模型偏好"""
    hints: List[Dict[str, str]] = field(default_factory=list)  # [{"name": "claude-3-sonnet"}]
    intelligence_priority: float = 0.5  # 0-1
    speed_priority: float = 0.5         # 0-1
    cost_priority: float = 0.5          # 0-1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hints": self.hints,
            "intelligencePriority": self.intelligence_priority,
            "speedPriority": self.speed_priority,
            "costPriority": self.cost_priority
        }
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ModelPreferences":
        if not data:
            return cls()
        return cls(
            hints=data.get("hints", []),
            intelligence_priority=data.get("intelligencePriority", 0.5),
            speed_priority=data.get("speedPriority", 0.5),
            cost_priority=data.get("costPriority", 0.5)
        )


@dataclass
class SamplingRequest:
    """
    Sampling 请求
    
    对应 MCP 协议的 sampling/createMessage 请求
    """
    id: str                                    # 请求 ID
    server_key: str                            # 发起请求的 MCP Server
    messages: List[SamplingMessage]            # 消息历史
    max_tokens: int                            # 最大 token 数（必填）
    system_prompt: Optional[str] = None        # 系统提示词
    model_preferences: ModelPreferences = field(default_factory=ModelPreferences)
    temperature: Optional[float] = None        # 温度
    stop_sequences: List[str] = field(default_factory=list)  # 停止序列
    metadata: Dict[str, Any] = field(default_factory=dict)   # 元数据
    include_context: str = "none"              # 上下文包含策略: "none", "thisServer", "allServers"
    
    # 内部字段
    approval_status: SamplingApprovalStatus = SamplingApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    modified_request: Optional[Dict[str, Any]] = None  # 用户修改后的请求
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "server_key": self.server_key,
            "messages": [m.to_dict() for m in self.messages],
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "model_preferences": self.model_preferences.to_dict(),
            "temperature": self.temperature,
            "stop_sequences": self.stop_sequences,
            "metadata": self.metadata,
            "include_context": self.include_context,
            "approval_status": self.approval_status.value,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_mcp_params(
        cls,
        request_id: str,
        server_key: str,
        params: Dict[str, Any]
    ) -> "SamplingRequest":
        """从 MCP 请求参数构建"""
        messages = [
            SamplingMessage.from_dict(m) 
            for m in params.get("messages", [])
        ]
        
        return cls(
            id=request_id,
            server_key=server_key,
            messages=messages,
            max_tokens=params.get("maxTokens", 1024),
            system_prompt=params.get("systemPrompt"),
            model_preferences=ModelPreferences.from_dict(params.get("modelPreferences")),
            temperature=params.get("temperature"),
            stop_sequences=params.get("stopSequences", []),
            metadata=params.get("metadata", {}),
            include_context=params.get("includeContext", "none")
        )


@dataclass
class SamplingResponse:
    """
    Sampling 响应
    
    对应 MCP 协议的 sampling/createMessage 响应
    """
    role: str = "assistant"
    content: Dict[str, Any] = field(default_factory=lambda: {"type": "text", "text": ""})
    model: str = ""
    stop_reason: SamplingStopReason = SamplingStopReason.END_TURN
    
    def to_mcp_result(self) -> Dict[str, Any]:
        """转换为 MCP 响应格式"""
        return {
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "stopReason": self.stop_reason.value
        }


@dataclass
class SamplingSecurityConfig:
    """Sampling 安全配置"""
    # Token 限制
    max_tokens_limit: int = 4096              # 最大允许的 max_tokens 值
    default_max_tokens: int = 1024            # 默认 max_tokens
    
    # 速率限制
    rate_limit_per_minute: int = 60           # 每分钟最大请求数
    rate_limit_per_server: int = 10           # 每个 Server 每分钟最大请求数
    
    # 内容过滤
    enable_content_filter: bool = True         # 是否启用内容过滤
    blocked_keywords: List[str] = field(default_factory=list)  # 禁止的关键词
    
    # 审核策略
    require_approval: bool = False             # 是否需要人工审核
    auto_approve_threshold: int = 100          # 自动批准的 token 阈值
    approval_timeout_seconds: int = 300        # 审核超时时间（秒）
    
    # 允许的 Server
    allowed_servers: List[str] = field(default_factory=list)   # 空表示允许所有
    blocked_servers: List[str] = field(default_factory=list)   # 阻止的 Server
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_tokens_limit": self.max_tokens_limit,
            "default_max_tokens": self.default_max_tokens,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_server": self.rate_limit_per_server,
            "enable_content_filter": self.enable_content_filter,
            "blocked_keywords": self.blocked_keywords,
            "require_approval": self.require_approval,
            "auto_approve_threshold": self.auto_approve_threshold,
            "approval_timeout_seconds": self.approval_timeout_seconds,
            "allowed_servers": self.allowed_servers,
            "blocked_servers": self.blocked_servers
        }


class SamplingService:
    """
    MCP Sampling 服务
    
    核心功能：
    1. 接收并处理 sampling/createMessage 请求
    2. 安全策略检查（token 限制、内容过滤、速率限制）
    3. 人机回环审核
    4. 调用 LLM 并返回结果
    """
    
    def __init__(self):
        self.config = SamplingSecurityConfig()
        self._pending_requests: Dict[str, SamplingRequest] = {}
        self._rate_limit_tracker: Dict[str, List[float]] = {}  # server_key -> [timestamps]
        self._global_rate_tracker: List[float] = []
        self._http_client: Optional[httpx.AsyncClient] = None
        self._approval_callbacks: Dict[str, Callable[[SamplingRequest], Awaitable[bool]]] = {}
        self._lock = asyncio.Lock()
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client
    
    def update_config(self, config: Dict[str, Any]):
        """更新安全配置"""
        if "max_tokens_limit" in config:
            self.config.max_tokens_limit = config["max_tokens_limit"]
        if "default_max_tokens" in config:
            self.config.default_max_tokens = config["default_max_tokens"]
        if "rate_limit_per_minute" in config:
            self.config.rate_limit_per_minute = config["rate_limit_per_minute"]
        if "rate_limit_per_server" in config:
            self.config.rate_limit_per_server = config["rate_limit_per_server"]
        if "enable_content_filter" in config:
            self.config.enable_content_filter = config["enable_content_filter"]
        if "blocked_keywords" in config:
            self.config.blocked_keywords = config["blocked_keywords"]
        if "require_approval" in config:
            self.config.require_approval = config["require_approval"]
        if "auto_approve_threshold" in config:
            self.config.auto_approve_threshold = config["auto_approve_threshold"]
        if "approval_timeout_seconds" in config:
            self.config.approval_timeout_seconds = config["approval_timeout_seconds"]
        if "allowed_servers" in config:
            self.config.allowed_servers = config["allowed_servers"]
        if "blocked_servers" in config:
            self.config.blocked_servers = config["blocked_servers"]
        
        logger.info(f"Sampling 安全配置已更新: {self.config.to_dict()}")
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前安全配置"""
        return self.config.to_dict()
    
    # ==================== 安全策略检查 ====================
    
    def _check_server_permission(self, server_key: str) -> tuple[bool, str]:
        """检查 Server 权限"""
        # 检查是否在黑名单
        if server_key in self.config.blocked_servers:
            return False, f"服务器 {server_key} 已被阻止使用 Sampling 能力"
        
        # 检查是否在白名单（如果启用）
        if self.config.allowed_servers and server_key not in self.config.allowed_servers:
            return False, f"服务器 {server_key} 不在 Sampling 白名单中"
        
        return True, ""
    
    def _check_rate_limit(self, server_key: str) -> tuple[bool, str]:
        """检查速率限制"""
        now = time.time()
        minute_ago = now - 60
        
        # 全局速率限制
        self._global_rate_tracker = [t for t in self._global_rate_tracker if t > minute_ago]
        if len(self._global_rate_tracker) >= self.config.rate_limit_per_minute:
            return False, f"全局速率限制已达上限 ({self.config.rate_limit_per_minute}/分钟)"
        
        # Server 级速率限制
        if server_key not in self._rate_limit_tracker:
            self._rate_limit_tracker[server_key] = []
        
        self._rate_limit_tracker[server_key] = [
            t for t in self._rate_limit_tracker[server_key] if t > minute_ago
        ]
        
        if len(self._rate_limit_tracker[server_key]) >= self.config.rate_limit_per_server:
            return False, f"服务器 {server_key} 速率限制已达上限 ({self.config.rate_limit_per_server}/分钟)"
        
        return True, ""
    
    def _record_request(self, server_key: str):
        """记录请求用于速率限制"""
        now = time.time()
        self._global_rate_tracker.append(now)
        
        if server_key not in self._rate_limit_tracker:
            self._rate_limit_tracker[server_key] = []
        self._rate_limit_tracker[server_key].append(now)
    
    def _check_token_limit(self, max_tokens: int) -> tuple[bool, int, str]:
        """
        检查并调整 token 限制
        
        Returns:
            (is_valid, adjusted_max_tokens, message)
        """
        if max_tokens <= 0:
            return True, self.config.default_max_tokens, "使用默认 token 限制"
        
        if max_tokens > self.config.max_tokens_limit:
            return True, self.config.max_tokens_limit, f"max_tokens 已调整为上限 {self.config.max_tokens_limit}"
        
        return True, max_tokens, ""
    
    def _filter_content(self, messages: List[SamplingMessage]) -> tuple[bool, str]:
        """
        过滤消息内容
        
        检查是否包含敏感关键词
        """
        if not self.config.enable_content_filter:
            return True, ""
        
        if not self.config.blocked_keywords:
            return True, ""
        
        for msg in messages:
            text = msg.get_text().lower()
            for keyword in self.config.blocked_keywords:
                if keyword.lower() in text:
                    return False, f"消息内容包含禁止的关键词: {keyword}"
        
        return True, ""
    
    def _should_auto_approve(self, request: SamplingRequest) -> bool:
        """判断是否应该自动批准"""
        if not self.config.require_approval:
            return True
        
        # 低 token 请求自动批准
        if request.max_tokens <= self.config.auto_approve_threshold:
            return True
        
        return False
    
    async def validate_request(
        self,
        request: SamplingRequest
    ) -> tuple[bool, str, SamplingRequest]:
        """
        验证 Sampling 请求
        
        Returns:
            (is_valid, error_message, adjusted_request)
        """
        # 1. 检查 Server 权限
        ok, msg = self._check_server_permission(request.server_key)
        if not ok:
            return False, msg, request
        
        # 2. 检查速率限制
        ok, msg = self._check_rate_limit(request.server_key)
        if not ok:
            return False, msg, request
        
        # 3. 检查并调整 token 限制
        ok, adjusted_tokens, msg = self._check_token_limit(request.max_tokens)
        if not ok:
            return False, msg, request
        request.max_tokens = adjusted_tokens
        
        # 4. 内容过滤
        ok, msg = self._filter_content(request.messages)
        if not ok:
            return False, msg, request
        
        # 5. 判断审核策略
        if self._should_auto_approve(request):
            request.approval_status = SamplingApprovalStatus.AUTO_APPROVED
        else:
            request.approval_status = SamplingApprovalStatus.PENDING
        
        return True, "", request
    
    # ==================== 请求处理 ====================
    
    async def handle_sampling_request(
        self,
        server_key: str,
        jsonrpc_id: Any,
        params: Dict[str, Any],
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理 sampling/createMessage 请求
        
        这是主入口方法，完整处理从接收请求到返回响应的流程。
        
        Args:
            server_key: 发起请求的 MCP Server 标识
            jsonrpc_id: JSON-RPC 请求 ID
            params: 请求参数
            llm_config: LLM 配置（可选，如果不提供则使用默认配置）
            
        Returns:
            MCP 响应格式的结果或错误
        """
        request_id = f"sampling_{server_key}_{datetime.now().timestamp()}"
        
        # 1. 构建请求对象
        try:
            request = SamplingRequest.from_mcp_params(request_id, server_key, params)
        except Exception as e:
            logger.error(f"解析 Sampling 请求失败: {e}")
            return {
                "error": {
                    "code": -32602,
                    "message": f"无效的请求参数: {str(e)}"
                }
            }
        
        # 2. 验证请求
        is_valid, error_msg, request = await self.validate_request(request)
        if not is_valid:
            logger.warning(f"Sampling 请求验证失败: {error_msg}")
            return {
                "error": {
                    "code": -32600,
                    "message": error_msg
                }
            }
        
        # 3. 处理审核流程
        if request.approval_status == SamplingApprovalStatus.PENDING:
            # 需要人工审核，将请求加入待审核队列
            async with self._lock:
                self._pending_requests[request.id] = request
            
            logger.info(f"Sampling 请求 {request.id} 需要人工审核")
            
            # 返回等待审核的响应
            # 注意：在实际实现中，这里可能需要阻塞等待审核结果
            # 或者通过回调机制处理
            return {
                "error": {
                    "code": -32001,
                    "message": "请求需要人工审核，请稍候"
                }
            }
        
        # 4. 记录请求（用于速率限制统计）
        self._record_request(server_key)
        
        # 5. 调用 LLM
        try:
            response = await self._call_llm(request, llm_config)
            logger.info(f"Sampling 请求 {request.id} 处理完成")
            return {"result": response.to_mcp_result()}
        except Exception as e:
            logger.error(f"Sampling LLM 调用失败: {e}")
            return {
                "error": {
                    "code": -32603,
                    "message": f"LLM 调用失败: {str(e)}"
                }
            }
    
    async def _call_llm(
        self,
        request: SamplingRequest,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> SamplingResponse:
        """
        调用 LLM 生成响应
        
        复用 react_engine 中的 LLM 调用逻辑
        """
        from app.core.config import settings
        
        # 构建 LLM 配置
        config = llm_config or {}
        provider = config.get("provider", "zhipu")
        model = config.get("model") or self._select_model(request.model_preferences, provider)
        api_key = config.get("api_key") or getattr(settings, "ZHIPU_API_KEY", "")
        base_url = config.get("base_url")
        temperature = request.temperature if request.temperature is not None else config.get("temperature", 0.7)
        
        # 转换消息格式
        messages = []
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })
        
        for msg in request.messages:
            if msg.content.get("type") == "text":
                messages.append({
                    "role": msg.role,
                    "content": msg.content.get("text", "")
                })
            # 图片等其他类型暂不支持，转为文本描述
            elif msg.content.get("type") == "image":
                messages.append({
                    "role": msg.role,
                    "content": "[图片内容]"
                })
        
        # 调用 LLM
        client = await self._get_http_client()
        
        if provider == "zhipu":
            result = await self._call_zhipu(
                client, messages, model, api_key, base_url,
                temperature, request.max_tokens, request.stop_sequences
            )
        elif provider == "openai":
            result = await self._call_openai(
                client, messages, model, api_key, base_url,
                temperature, request.max_tokens, request.stop_sequences
            )
        elif provider == "anthropic":
            result = await self._call_anthropic(
                client, messages, model, api_key, base_url,
                temperature, request.max_tokens, request.stop_sequences
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")
        
        return result
    
    def _select_model(
        self,
        preferences: ModelPreferences,
        provider: str
    ) -> str:
        """根据偏好选择模型"""
        # 检查 hints
        for hint in preferences.hints:
            name = hint.get("name", "")
            if name:
                return name
        
        # 根据 provider 返回默认模型
        default_models = {
            "zhipu": "glm-4",
            "openai": "gpt-4o",
            "anthropic": "claude-3-sonnet-20240229",
            "ollama": "llama2"
        }
        return default_models.get(provider, "gpt-4o")
    
    async def _call_zhipu(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        model: str,
        api_key: str,
        base_url: Optional[str],
        temperature: float,
        max_tokens: int,
        stop_sequences: List[str]
    ) -> SamplingResponse:
        """调用智谱 API，支持 429 限流重试"""
        url = base_url or "https://open.bigmodel.cn/api/paas/v4"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if stop_sequences:
            payload["stop"] = stop_sequences
        
        # 重试配置 - 针对 429 错误使用更长的延迟
        max_retries = 3
        base_delay = 5.0  # 起始延迟增加到 5 秒（429 错误通常需要更长时间）
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(
                    f"{url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                choice = result["choices"][0]
                message = choice["message"]
                
                # 确定停止原因
                finish_reason = choice.get("finish_reason", "stop")
                if finish_reason == "stop":
                    stop_reason = SamplingStopReason.END_TURN
                elif finish_reason == "length":
                    stop_reason = SamplingStopReason.MAX_TOKENS
                else:
                    stop_reason = SamplingStopReason.END_TURN
                
                return SamplingResponse(
                    role="assistant",
                    content={"type": "text", "text": message.get("content", "")},
                    model=model,
                    stop_reason=stop_reason
                )
            except Exception as e:
                last_error = e
                # 检测 429 限流错误
                is_rate_limit = False
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    is_rate_limit = e.response.status_code == 429
                elif '429' in str(e):
                    is_rate_limit = True
                
                if is_rate_limit:
                    if attempt < max_retries:
                        # 优先使用响应头中的 Retry-After 提示
                        retry_after = None
                        try:
                            if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                                retry_after_header = e.response.headers.get("Retry-After")
                                if retry_after_header:
                                    retry_after = int(retry_after_header)
                        except (ValueError, TypeError):
                            pass
                        
                        # 如果响应头没有 Retry-After，使用指数退避，但延迟更长
                        if retry_after:
                            delay = float(retry_after)
                        else:
                            delay = base_delay * (2 ** attempt)  # 指数退避: 5s, 10s, 20s
                        
                        logger.warning(
                            f"智谱 API 限流 (429)，{delay:.1f}秒后重试 (尝试 {attempt + 1}/{max_retries})"
                        )
                        import asyncio
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"智谱 API 限流，已达最大重试次数 ({max_retries})")
                        raise Exception(
                            f"API 请求频率过高 (429 Too Many Requests)，请稍后重试。"
                            f"建议：1) 等待 30-60 秒后再试 2) 减少请求频率 3) 升级 API 配额"
                        ) from e
                # 其他错误直接抛出
                raise
        
        # 所有重试都失败
        raise last_error or Exception("智谱 API 调用失败")
    
    async def _call_openai(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        model: str,
        api_key: str,
        base_url: Optional[str],
        temperature: float,
        max_tokens: int,
        stop_sequences: List[str]
    ) -> SamplingResponse:
        """调用 OpenAI API"""
        url = base_url or "https://api.openai.com/v1"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if stop_sequences:
            payload["stop"] = stop_sequences
        
        response = await client.post(
            f"{url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result["choices"][0]
        message = choice["message"]
        
        finish_reason = choice.get("finish_reason", "stop")
        if finish_reason == "stop":
            stop_reason = SamplingStopReason.END_TURN
        elif finish_reason == "length":
            stop_reason = SamplingStopReason.MAX_TOKENS
        else:
            stop_reason = SamplingStopReason.END_TURN
        
        return SamplingResponse(
            role="assistant",
            content={"type": "text", "text": message.get("content", "")},
            model=model,
            stop_reason=stop_reason
        )
    
    async def _call_anthropic(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        model: str,
        api_key: str,
        base_url: Optional[str],
        temperature: float,
        max_tokens: int,
        stop_sequences: List[str]
    ) -> SamplingResponse:
        """调用 Anthropic API"""
        url = base_url or "https://api.anthropic.com/v1"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # 分离 system 消息
        system_content = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                chat_messages.append(msg)
        
        payload = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        if system_content:
            payload["system"] = system_content.strip()
        
        if stop_sequences:
            payload["stop_sequences"] = stop_sequences
        
        response = await client.post(
            f"{url}/messages",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 提取文本内容
        content_text = ""
        for block in result.get("content", []):
            if block["type"] == "text":
                content_text += block["text"]
        
        stop_reason_str = result.get("stop_reason", "end_turn")
        if stop_reason_str == "end_turn":
            stop_reason = SamplingStopReason.END_TURN
        elif stop_reason_str == "max_tokens":
            stop_reason = SamplingStopReason.MAX_TOKENS
        elif stop_reason_str == "stop_sequence":
            stop_reason = SamplingStopReason.STOP_SEQUENCE
        else:
            stop_reason = SamplingStopReason.END_TURN
        
        return SamplingResponse(
            role="assistant",
            content={"type": "text", "text": content_text},
            model=model,
            stop_reason=stop_reason
        )
    
    # ==================== 审核流程 ====================
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """获取待审核的请求列表"""
        return [req.to_dict() for req in self._pending_requests.values()]
    
    def get_pending_request(self, request_id: str) -> Optional[SamplingRequest]:
        """获取指定的待审核请求"""
        return self._pending_requests.get(request_id)
    
    async def approve_request(
        self,
        request_id: str,
        modified_params: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        批准 Sampling 请求
        
        Args:
            request_id: 请求 ID
            modified_params: 用户修改后的参数（可选）
            llm_config: LLM 配置
            
        Returns:
            MCP 响应结果
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return {
                    "error": {
                        "code": -32602,
                        "message": f"未找到待审核请求: {request_id}"
                    }
                }
            
            # 应用用户修改
            if modified_params:
                if "max_tokens" in modified_params:
                    request.max_tokens = modified_params["max_tokens"]
                if "temperature" in modified_params:
                    request.temperature = modified_params["temperature"]
                if "system_prompt" in modified_params:
                    request.system_prompt = modified_params["system_prompt"]
                request.modified_request = modified_params
            
            request.approval_status = SamplingApprovalStatus.APPROVED
            request.approved_at = datetime.now()
            
            # 从待审核队列移除
            del self._pending_requests[request_id]
        
        # 记录请求
        self._record_request(request.server_key)
        
        # 调用 LLM
        try:
            response = await self._call_llm(request, llm_config)
            logger.info(f"Sampling 请求 {request_id} 已批准并处理完成")
            return {"result": response.to_mcp_result()}
        except Exception as e:
            logger.error(f"Sampling LLM 调用失败: {e}")
            return {
                "error": {
                    "code": -32603,
                    "message": f"LLM 调用失败: {str(e)}"
                }
            }
    
    async def reject_request(
        self,
        request_id: str,
        reason: str = "用户拒绝了此请求"
    ) -> Dict[str, Any]:
        """
        拒绝 Sampling 请求
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return {
                    "error": {
                        "code": -32602,
                        "message": f"未找到待审核请求: {request_id}"
                    }
                }
            
            request.approval_status = SamplingApprovalStatus.REJECTED
            del self._pending_requests[request_id]
        
        logger.info(f"Sampling 请求 {request_id} 已被拒绝: {reason}")
        
        return {
            "error": {
                "code": -1,
                "message": reason
            }
        }
    
    async def cleanup_expired_requests(self):
        """清理过期的待审核请求"""
        now = datetime.now()
        expired_ids = []
        
        async with self._lock:
            for req_id, request in self._pending_requests.items():
                elapsed = (now - request.created_at).total_seconds()
                if elapsed > self.config.approval_timeout_seconds:
                    request.approval_status = SamplingApprovalStatus.EXPIRED
                    expired_ids.append(req_id)
            
            for req_id in expired_ids:
                del self._pending_requests[req_id]
                logger.info(f"Sampling 请求 {req_id} 已过期")
        
        return expired_ids
    
    # ==================== 状态和清理 ====================
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Sampling 服务状态"""
        return {
            "enabled": True,
            "config": self.config.to_dict(),
            "pending_requests_count": len(self._pending_requests),
            "rate_limit": {
                "global_current": len(self._global_rate_tracker),
                "global_limit": self.config.rate_limit_per_minute,
                "per_server": {
                    k: len(v) for k, v in self._rate_limit_tracker.items()
                }
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._pending_requests.clear()
        self._rate_limit_tracker.clear()
        self._global_rate_tracker.clear()
        logger.info("Sampling 服务已清理")


# 创建全局单例
sampling_service = SamplingService()
