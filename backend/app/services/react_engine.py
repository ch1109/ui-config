# app/services/react_engine.py
"""
ReAct 循环引擎
实现完整的 推理-行动 循环（Reasoning and Acting）

ReAct 循环流程：
1. 用户输入 → Host 接收
2. 上下文组装 → 工具定义 + 系统提示 + 对话历史
3. 模型推理 → LLM 分析并决定是否调用工具
4. 拦截与路由 → Host 解析工具调用意图
5. MCP 调用 → 通过 MCP Client 执行工具
6. 结果回传 → 将工具结果封装回对话历史
7. 最终生成 → LLM 生成最终回复
"""

import asyncio
import json
import logging
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.services.mcp_host_service import (
    mcp_host_service,
    ToolCallRequest,
    ToolCallResult,
    ConversationMessage,
    ToolRiskLevel
)

logger = logging.getLogger(__name__)


class ReActState(Enum):
    """ReAct 循环状态"""
    IDLE = "idle"
    REASONING = "reasoning"           # LLM 正在推理
    PENDING_CONFIRMATION = "pending"  # 等待用户确认工具调用
    EXECUTING_TOOL = "executing"      # 正在执行工具
    GENERATING = "generating"         # 生成最终回复
    COMPLETED = "completed"           # 完成
    ERROR = "error"                   # 错误


@dataclass
class ReActStep:
    """ReAct 单步记录"""
    step_number: int
    state: ReActState
    thought: Optional[str] = None      # LLM 的思考过程
    action: Optional[str] = None       # 要执行的动作
    action_input: Optional[Dict] = None # 动作输入
    observation: Optional[str] = None  # 执行结果观察
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReActContext:
    """ReAct 上下文"""
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[ReActStep] = field(default_factory=list)
    current_state: ReActState = ReActState.IDLE
    max_iterations: int = 10
    current_iteration: int = 0
    

@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"  # openai, anthropic, ollama, zhipu, qwen
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class ReActEngine:
    """
    ReAct 循环引擎
    
    核心功能：
    1. 管理对话上下文
    2. 调用 LLM 进行推理
    3. 解析工具调用意图
    4. 协调工具执行（含人机回环）
    5. 生成最终回复
    """
    
    def __init__(self):
        self.contexts: Dict[str, ReActContext] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._zhipu_semaphore = asyncio.Semaphore(1)
        self._zhipu_rate_lock = asyncio.Lock()
        self._zhipu_next_ts = 0.0
        self._zhipu_min_interval_seconds = 6.0
        self._zhipu_request_times: List[float] = []
        self._zhipu_max_per_minute = 8
        
    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client
    
    def create_context(
        self,
        session_id: str,
        system_prompt: str = "",
        max_iterations: int = 10
    ) -> ReActContext:
        """创建 ReAct 上下文"""
        context = ReActContext(
            session_id=session_id,
            max_iterations=max_iterations
        )
        
        # 添加系统提示
        if system_prompt:
            context.messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        self.contexts[session_id] = context
        return context
    
    def get_context(self, session_id: str) -> Optional[ReActContext]:
        """获取上下文"""
        return self.contexts.get(session_id)
    
    async def build_system_prompt_with_tools(
        self,
        base_prompt: str = ""
    ) -> str:
        """
        构建包含工具信息的系统提示
        """
        tools = await mcp_host_service.get_aggregated_tools()
        
        prompt_parts = [base_prompt] if base_prompt else []
        
        if tools:
            prompt_parts.append("\n## 可用工具\n")
            prompt_parts.append("你可以使用以下工具来帮助完成任务：\n")
            
            for tool in tools:
                func = tool.get("function", {})
                name = func.get("name", "")
                desc = func.get("description", "")
                params = func.get("parameters", {})
                
                prompt_parts.append(f"\n### {name}")
                prompt_parts.append(f"描述: {desc}")
                
                if params.get("properties"):
                    prompt_parts.append("参数:")
                    for param_name, param_info in params["properties"].items():
                        required = "必填" if param_name in params.get("required", []) else "可选"
                        param_type = param_info.get("type", "any")
                        param_desc = param_info.get("description", "")
                        prompt_parts.append(f"  - {param_name} ({param_type}, {required}): {param_desc}")
            
            prompt_parts.append("\n## 使用说明")
            prompt_parts.append("1. 当你需要使用工具时，请明确指定工具名称和参数")
            prompt_parts.append("2. 高风险操作（如删除、修改数据）需要用户确认")
            prompt_parts.append("3. 工具调用结果会自动回传给你")
        
        return "\n".join(prompt_parts)
    
    async def call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """
        调用 LLM 进行推理
        
        支持 OpenAI 和 Anthropic 格式
        """
        client = await self._get_http_client()
        
        if config.provider == "openai":
            return await self._call_openai(client, messages, tools, config)
        elif config.provider == "anthropic":
            return await self._call_anthropic(client, messages, tools, config)
        elif config.provider == "ollama":
            return await self._call_ollama(client, messages, tools, config)
        elif config.provider == "zhipu":
            return await self._call_zhipu(client, messages, tools, config)
        elif config.provider == "qwen":
            return await self._call_qwen(client, messages, tools, config)
        else:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")
    
    async def _call_openai(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """调用 OpenAI API"""
        base_url = config.base_url or "https://api.openai.com/v1"
        
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result["choices"][0]
        message = choice["message"]
        
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
            "finish_reason": choice.get("finish_reason", "stop"),
            "usage": result.get("usage", {})
        }
    
    async def _call_anthropic(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """调用 Anthropic API"""
        base_url = config.base_url or "https://api.anthropic.com/v1"
        
        headers = {
            "x-api-key": config.api_key,
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
        
        # 转换工具格式
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            })
        
        payload = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": chat_messages
        }
        
        if system_content:
            payload["system"] = system_content.strip()
        
        if anthropic_tools:
            payload["tools"] = anthropic_tools
        
        response = await client.post(
            f"{base_url}/messages",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 解析响应
        content = ""
        tool_calls = []
        
        for block in result.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"])
                    }
                })
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": result.get("stop_reason", "stop"),
            "usage": result.get("usage", {})
        }
    
    async def _call_ollama(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """调用 Ollama API"""
        base_url = config.base_url or "http://localhost:11434"
        
        payload = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens
            }
        }
        
        if tools:
            payload["tools"] = tools
        
        response = await client.post(
            f"{base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        message = result.get("message", {})
        
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
            "finish_reason": "stop" if result.get("done") else "tool_calls",
            "usage": {}
        }
    
    async def _call_zhipu(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """调用智谱 API（兼容 OpenAI 格式），支持 429 限流重试"""
        from app.core.config import settings
        base_url = config.base_url or "https://open.bigmodel.cn/api/paas/v4"
        api_key = config.api_key or settings.ZHIPU_API_KEY or ""
        model = config.model or settings.ZHIPU_MODEL_NAME or "glm-4"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        # 重试配置 - 针对 429 错误使用更长的延迟
        max_retries = 3
        base_delay = 5.0  # 起始延迟增加到 5 秒（429 错误通常需要更长时间）
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                await self._await_zhipu_rate_limit()
                async with self._zhipu_semaphore:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                response.raise_for_status()
                
                result = response.json()
                choice = result["choices"][0]
                message = choice["message"]
                
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", []),
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "usage": result.get("usage", {})
                }
            except httpx.HTTPStatusError as e:
                last_error = e
                # 429 Too Many Requests - 限流错误，需要重试
                if e.response.status_code == 429:
                    if attempt < max_retries:
                        # 优先使用响应头中的 Retry-After 提示
                        retry_after = None
                        try:
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
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"智谱 API 限流，已达最大重试次数 ({max_retries})")
                        raise Exception(
                            f"API 请求频率过高 (429 Too Many Requests)，请稍后重试。"
                            f"建议：1) 等待 30-60 秒后再试 2) 减少请求频率 3) 升级 API 配额"
                        ) from e
                # 其他 HTTP 错误直接抛出
                raise
        
        # 所有重试都失败
        raise last_error or Exception("智谱 API 调用失败")

    async def _call_qwen(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: LLMConfig
    ) -> Dict[str, Any]:
        """调用 Qwen API（支持本地部署和 DashScope）"""
        from app.core.config import settings
        
        # 支持本地部署（如 http://192.168.3.183/v1）或 DashScope
        base_url = config.base_url or "http://192.168.3.183/v1"
        model = config.model or "qwen3-30b"
        
        # 判断是否为本地部署（不包含 dashscope 或 aliyun）
        is_local = "dashscope" not in base_url and "aliyun" not in base_url
        
        # 构建请求头
        headers = {
            "Content-Type": "application/json"
        }
        
        # 本地部署需要 Model header
        if is_local:
            headers["Model"] = model
        
        # 如果有 API Key（DashScope 模式），添加 Authorization
        api_key = config.api_key or settings.DASHSCOPE_API_KEY
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }
        
        # 本地部署的 Qwen 不支持 tools/function calling，只有 DashScope 支持
        if tools and not is_local:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result["choices"][0]
        message = choice["message"]
        
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
            "finish_reason": choice.get("finish_reason", "stop"),
            "usage": result.get("usage", {})
        }

    async def _await_zhipu_rate_limit(self) -> None:
        """智谱请求最小间隔，避免短时间突发限流"""
        async with self._zhipu_rate_lock:
            loop = asyncio.get_running_loop()
            while True:
                now = loop.time()
                self._zhipu_request_times = [
                    t for t in self._zhipu_request_times if now - t < 60.0
                ]
                wait_until = self._zhipu_next_ts
                if len(self._zhipu_request_times) >= self._zhipu_max_per_minute:
                    wait_until = max(wait_until, self._zhipu_request_times[0] + 60.0)
                wait_seconds = wait_until - now
                if wait_seconds <= 0:
                    self._zhipu_next_ts = now + self._zhipu_min_interval_seconds
                    self._zhipu_request_times.append(now)
                    return
                logger.warning(f"智谱请求过密，等待 {wait_seconds:.1f} 秒后继续")
                await asyncio.sleep(wait_seconds)
    
    def parse_tool_calls(
        self,
        llm_response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        解析 LLM 响应中的工具调用
        """
        tool_calls = llm_response.get("tool_calls", [])
        
        parsed_calls = []
        for call in tool_calls:
            func = call.get("function", {})
            name = func.get("name", "")
            
            # 解析参数
            args_str = func.get("arguments", "{}")
            try:
                arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                arguments = {}
            
            parsed_calls.append({
                "id": call.get("id", ""),
                "name": name,
                "arguments": arguments
            })
        
        return parsed_calls
    
    async def run_react_loop(
        self,
        session_id: str,
        user_input: str,
        llm_config: LLMConfig,
        system_prompt: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        运行 ReAct 循环
        
        使用异步生成器，支持流式输出中间状态
        
        Yields:
            步骤状态和结果
        """
        # 获取或创建上下文
        context = self.get_context(session_id)
        if not context:
            # 构建包含工具的系统提示
            full_system_prompt = await self.build_system_prompt_with_tools(system_prompt)
            context = self.create_context(session_id, full_system_prompt)
        
        # 添加用户消息
        context.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 获取可用工具
        context.tools = await mcp_host_service.get_aggregated_tools()
        
        context.current_state = ReActState.REASONING
        
        yield {
            "type": "state",
            "state": "reasoning",
            "message": "正在分析请求..."
        }
        
        # ReAct 循环
        while context.current_iteration < context.max_iterations:
            context.current_iteration += 1
            
            step = ReActStep(
                step_number=context.current_iteration,
                state=context.current_state
            )
            
            try:
                # 1. 调用 LLM
                llm_response = await self.call_llm(
                    context.messages,
                    context.tools,
                    llm_config
                )
                
                content = llm_response.get("content", "")
                tool_calls = self.parse_tool_calls(llm_response)
                
                # 2. 检查是否有工具调用
                if not tool_calls:
                    # 没有工具调用，返回最终回复
                    context.current_state = ReActState.COMPLETED
                    step.thought = content
                    step.state = ReActState.COMPLETED
                    context.steps.append(step)
                    
                    # 添加助手消息
                    context.messages.append({
                        "role": "assistant",
                        "content": content
                    })
                    
                    yield {
                        "type": "final",
                        "content": content,
                        "steps": len(context.steps)
                    }
                    break
                
                # 3. 处理工具调用
                step.thought = content if content else "需要调用工具获取信息"
                step.action = tool_calls[0]["name"] if tool_calls else None
                step.action_input = tool_calls[0]["arguments"] if tool_calls else None
                
                # 添加助手消息（包含工具调用）
                context.messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call["arguments"])
                            }
                        }
                        for call in tool_calls
                    ]
                })
                
                # 4. 执行工具调用
                for call in tool_calls:
                    yield {
                        "type": "tool_call",
                        "tool": call["name"],
                        "arguments": call["arguments"],
                        "state": "preparing"
                    }
                    
                    # 准备工具调用（含风险评估）
                    request = await mcp_host_service.prepare_tool_call(
                        session_id,
                        call["name"],
                        call["arguments"]
                    )
                    
                    # 检查是否需要确认
                    if request.requires_confirmation:
                        context.current_state = ReActState.PENDING_CONFIRMATION
                        
                        yield {
                            "type": "confirmation_required",
                            "request_id": request.id,
                            "tool": call["name"],
                            "arguments": call["arguments"],
                            "risk_level": request.risk_level.value,
                            "message": f"工具 {call['name']} 需要确认（风险级别: {request.risk_level.value}）"
                        }
                        
                        # 等待确认结果
                        # 这里返回，让调用者处理确认
                        return
                    
                    # 执行工具
                    context.current_state = ReActState.EXECUTING_TOOL
                    
                    yield {
                        "type": "tool_call",
                        "tool": call["name"],
                        "state": "executing"
                    }
                    
                    result = await mcp_host_service.execute_tool_call(request, force=True)
                    
                    # 记录观察结果
                    if result.success:
                        observation = json.dumps(result.result, ensure_ascii=False, indent=2)
                    else:
                        observation = f"错误: {result.error}"
                    
                    step.observation = observation
                    
                    yield {
                        "type": "tool_result",
                        "tool": call["name"],
                        "success": result.success,
                        "result": result.result if result.success else None,
                        "error": result.error if not result.success else None,
                        "execution_time_ms": result.execution_time_ms
                    }
                    
                    # 添加工具结果到消息
                    context.messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": observation
                    })
                
                context.steps.append(step)
                context.current_state = ReActState.REASONING
                
            except Exception as e:
                logger.error(f"ReAct loop error: {e}")
                context.current_state = ReActState.ERROR
                
                yield {
                    "type": "error",
                    "error": str(e)
                }
                break
        
        # 超过最大迭代次数
        if context.current_iteration >= context.max_iterations:
            yield {
                "type": "error",
                "error": f"超过最大迭代次数 ({context.max_iterations})"
            }
    
    async def continue_after_confirmation(
        self,
        session_id: str,
        request_id: str,
        approved: bool,
        modified_arguments: Optional[Dict[str, Any]] = None,
        llm_config: Optional[LLMConfig] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        在用户确认后继续 ReAct 循环
        """
        context = self.get_context(session_id)
        if not context:
            yield {
                "type": "error",
                "error": "会话不存在"
            }
            return
        
        # 确认工具调用
        result = await mcp_host_service.confirm_tool_call(
            session_id,
            request_id,
            approved,
            modified_arguments
        )
        
        if result.was_rejected:
            yield {
                "type": "tool_rejected",
                "request_id": request_id,
                "message": "用户拒绝了此操作"
            }
            
            # 添加拒绝消息到上下文
            context.messages.append({
                "role": "tool",
                "tool_call_id": request_id,
                "content": "用户拒绝了此操作"
            })
        else:
            yield {
                "type": "tool_result",
                "request_id": request_id,
                "success": result.success,
                "result": result.result if result.success else None,
                "error": result.error if not result.success else None,
                "execution_time_ms": result.execution_time_ms
            }
            
            # 添加结果到上下文
            observation = json.dumps(result.result, ensure_ascii=False) if result.success else f"错误: {result.error}"
            context.messages.append({
                "role": "tool",
                "tool_call_id": request_id,
                "content": observation
            })
        
        # 如果有 LLM 配置，继续循环
        if llm_config:
            context.current_state = ReActState.REASONING
            
            # 继续 ReAct 循环
            async for event in self.run_react_loop(
                session_id,
                "",  # 不添加新的用户消息
                llm_config
            ):
                yield event
    
    async def cleanup(self):
        """清理资源"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self.contexts.clear()


# 创建全局单例
react_engine = ReActEngine()

