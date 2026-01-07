# app/services/vl_model_service.py
"""
VL 模型服务封装
支持 GLM-4V (智谱) 和 Qwen-VL (阿里云 DashScope)
对应需求: REQ-M2-007
"""

import httpx
import base64
import json
import aiofiles
from typing import Optional, Dict, Any, List, AsyncGenerator
from urllib.parse import urlparse
from app.schemas.vl_response import VLParseResult, ParsedElement
from app.core.config import settings
from app.core.exceptions import SSRFProtectionError, InvalidFileTypeError
import logging

logger = logging.getLogger(__name__)


class VLModelService:
    """
    VL 模型服务封装
    
    支持:
    - 智谱 GLM-4V (默认)
    - 阿里云 DashScope Qwen-VL
    
    功能: 语义级解析 - 元素识别 + 交互意图 + 业务含义推断
    """
    
    def __init__(self):
        self.provider = settings.VL_PROVIDER.lower()
        self.timeout = settings.VL_TIMEOUT
        
        # 根据 provider 选择配置
        if self.provider == "zhipu":
            self.api_key = settings.ZHIPU_API_KEY
            self.model_name = settings.ZHIPU_MODEL_NAME
            self.api_endpoint = settings.ZHIPU_API_ENDPOINT
        elif self.provider == "dashscope":
            self.api_key = settings.DASHSCOPE_API_KEY
            self.model_name = settings.DASHSCOPE_MODEL_NAME
            self.api_endpoint = settings.DASHSCOPE_API_ENDPOINT
        else:
            # 兼容旧配置
            self.api_key = settings.VL_API_KEY
            self.model_name = settings.VL_MODEL_NAME
            self.api_endpoint = f"{settings.VL_MODEL_ENDPOINT}/v1/chat/completions"
    
    async def parse_image(
        self, 
        image_url: str, 
        system_prompt: str
    ) -> VLParseResult:
        """
        解析页面截图
        
        Args:
            image_url: 图片路径或 URL
            system_prompt: System Prompt 内容
            
        Returns:
            VLParseResult: 结构化解析结果
        """
        # 读取并编码图片
        image_base64 = await self._load_image(image_url)
        
        # 根据 provider 构建不同格式的请求
        if self.provider == "zhipu":
            messages = self._build_zhipu_messages(image_base64, system_prompt)
            request_body = self._build_zhipu_request(messages)
        elif self.provider == "dashscope":
            messages = self._build_dashscope_messages(image_base64, system_prompt)
            request_body = self._build_dashscope_request(messages)
        else:
            messages = self._build_openai_messages(image_base64, system_prompt)
            request_body = self._build_openai_request(messages)
        
        logger.info(f"Calling VL model: {self.provider} / {self.model_name}")
        logger.debug(f"Request body keys: {list(request_body.keys())}, model: {request_body.get('model')}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Content-Type": "application/json"
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = await client.post(
                self.api_endpoint,
                json=request_body,
                headers=headers
            )
            
            # 记录详细的错误信息以便调试
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"VL API error {response.status_code}: {error_text}")
            
            response.raise_for_status()
            result = response.json()
        
        # 解析模型输出
        content = result["choices"][0]["message"]["content"]
        logger.debug(f"VL model response: {content[:500]}...")
        
        # REQ-M2-021: 解析失败自动纠错重试
        parsed_data = await self._parse_json_with_retry(messages, content)
        
        return self._build_parse_result(parsed_data)
    
    async def parse_image_stream(
        self, 
        image_url: str, 
        system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        流式解析页面截图
        
        Args:
            image_url: 图片路径或 URL
            system_prompt: System Prompt 内容
            
        Yields:
            str: SSE 格式的流式数据
        """
        try:
            # 读取并编码图片
            image_base64 = await self._load_image(image_url)
            
            # 根据 provider 构建不同格式的请求
            if self.provider == "zhipu":
                messages = self._build_zhipu_messages(image_base64, system_prompt)
                request_body = self._build_zhipu_request(messages, stream=True)
            elif self.provider == "dashscope":
                messages = self._build_dashscope_messages(image_base64, system_prompt)
                request_body = self._build_dashscope_request(messages, stream=True)
            else:
                messages = self._build_openai_messages(image_base64, system_prompt)
                request_body = self._build_openai_request(messages, stream=True)
            
            logger.info(f"Calling VL model (stream): {self.provider} / {self.model_name}")
            
            accumulated_content = ""
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Content-Type": "application/json"
                }
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                logger.info(f"Stream request to: {self.api_endpoint}")
                logger.info(f"Stream enabled: {request_body.get('stream')}")
                
                async with client.stream(
                    "POST",
                    self.api_endpoint,
                    json=request_body,
                    headers=headers
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"VL API error {response.status_code}: {error_text}")
                        yield f"data: {json.dumps({'error': f'API 错误: {response.status_code}'})}\n\n"
                        return
                    
                    # 发送开始事件
                    logger.info("Stream response started, sending start event")
                    yield f"data: {json.dumps({'type': 'start', 'message': '正在分析图片...'})}\n\n"
                    
                    chunk_count = 0
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        logger.debug(f"Raw stream line: {line[:100]}...")
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            
                            if data_str.strip() == "[DONE]":
                                logger.info(f"Stream completed with {chunk_count} chunks")
                                break
                            
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    chunk_count += 1
                                    accumulated_content += content
                                    # 发送内容片段
                                    logger.debug(f"Chunk {chunk_count}: {content[:50]}...")
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON decode error: {e}, line: {data_str[:100]}")
                                continue
                        else:
                            # 非标准 SSE 格式，可能是直接返回的 JSON
                            logger.warning(f"Non-SSE line: {line[:100]}")
            
            # 尝试解析完整的 JSON
            logger.debug(f"Accumulated content length: {len(accumulated_content)}")
            
            try:
                parsed_data = await self._parse_accumulated_content(messages, accumulated_content)
                result = self._build_parse_result(parsed_data)
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'complete', 'result': result.model_dump()})}\n\n"
                
            except Exception as e:
                logger.error(f"Failed to parse accumulated content: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'解析失败: {str(e)}'})}\n\n"
                
        except Exception as e:
            logger.error(f"Stream parsing error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    def _build_zhipu_messages(self, image_base64: str, system_prompt: str) -> list:
        """构建智谱 GLM-4V 格式的消息"""
        return [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": self._build_parse_prompt()
                    }
                ]
            }
        ]
    
    def _build_dashscope_messages(self, image_base64: str, system_prompt: str) -> list:
        """构建阿里云 DashScope Qwen-VL 格式的消息"""
        return [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": self._build_parse_prompt()
                    }
                ]
            }
        ]
    
    def _build_openai_messages(self, image_base64: str, system_prompt: str) -> list:
        """构建 OpenAI 兼容格式的消息"""
        return [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": self._build_parse_prompt()
                    }
                ]
            }
        ]
    
    def _build_zhipu_request(self, messages: list, stream: bool = False) -> dict:
        """构建智谱 API 请求体"""
        return {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.1,
            "stream": stream
        }
    
    def _build_dashscope_request(self, messages: list, stream: bool = False) -> dict:
        """构建 DashScope API 请求体"""
        return {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.1,
            "stream": stream
        }
    
    def _build_openai_request(self, messages: list, stream: bool = False) -> dict:
        """构建 OpenAI 兼容 API 请求体"""
        request = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.1,
            "stream": stream
        }
        if not stream:
            request["response_format"] = {"type": "json_object"}
        return request
    
    async def _load_image(self, image_url: str) -> str:
        """加载图片并转为 base64"""
        if image_url.startswith(("http://", "https://")):
            # REQ-M2-016: SSRF 防护
            if not self._is_safe_url(image_url):
                raise SSRFProtectionError()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(image_url, follow_redirects=True)
                content_type = resp.headers.get("Content-Type", "")
                
                # REQ-M2-017: 校验图片类型
                if "image/png" not in content_type and "image/jpeg" not in content_type:
                    raise InvalidFileTypeError([".png", ".jpg", ".jpeg"])
                
                image_bytes = resp.content
                
                # REQ-M2-016: 大小限制
                if len(image_bytes) > settings.MAX_UPLOAD_SIZE:
                    from app.core.exceptions import FileTooLargeError
                    raise FileTooLargeError(
                        max_size_mb=settings.MAX_UPLOAD_SIZE // (1024 * 1024),
                        actual_size_mb=len(image_bytes) / (1024 * 1024)
                    )
        else:
            # 本地文件 (REQ-M2-018: 仅允许 uploads 目录)
            if not image_url.startswith("/uploads/"):
                raise ValueError("仅允许读取 uploads 目录下的文件")
            
            file_path = image_url.lstrip("/")
            async with aiofiles.open(file_path, "rb") as f:
                image_bytes = await f.read()
        
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def _build_parse_prompt(self) -> str:
        """构建解析指令"""
        return """请分析这张页面截图，识别所有可交互元素并提取结构化配置。

请按以下 JSON 格式输出：
{
  "page_name": {
    "zh-CN": "页面中文名称",
    "en": "Page English Name"
  },
  "page_description": {
    "zh-CN": "页面功能描述（列出用户可执行的操作）",
    "en": "Page description"
  },
  "elements": [
    {
      "element_id": "snake_case_id",
      "element_type": "button|input|text|link",
      "label": "元素显示文本",
      "inferred_intent": "推断的交互意图",
      "confidence": 0.95
    }
  ],
  "button_list": ["button_id_1", "button_id_2"],
  "optional_actions": ["chat", "knowledge"],
  "ai_context": {
    "behavior_rules": "AI 在此页面的行为规则建议",
    "page_goal": "页面的核心目标"
  },
  "overall_confidence": 0.85,
  "clarification_needed": true,
  "clarification_questions": ["如果需要澄清，列出问题"]
}

注意：
1. element_id 使用 snake_case 格式
2. 如果某些元素的用途不明确，请设置 clarification_needed 为 true，并在 clarification_questions 中提出具体问题
3. confidence 取值 0-1，表示识别的置信度
4. 请只输出 JSON，不要有其他文字
"""
    
    def _build_parse_result(self, data: dict) -> VLParseResult:
        """构建解析结果对象"""
        elements = []
        for elem in data.get("elements", []):
            try:
                elements.append(ParsedElement(**elem))
            except Exception as e:
                logger.warning(f"Failed to parse element: {elem}, error: {e}")
        
        return VLParseResult(
            page_name=data.get("page_name", {"zh-CN": "", "en": ""}),
            page_description=data.get("page_description", {"zh-CN": "", "en": ""}),
            elements=elements,
            button_list=data.get("button_list", []),
            optional_actions=data.get("optional_actions", []),
            ai_context=data.get("ai_context", {}),
            overall_confidence=data.get("overall_confidence", 0.5),
            clarification_needed=data.get("clarification_needed", False),
            clarification_questions=data.get("clarification_questions")
        )

    async def _parse_json_with_retry(self, messages: list, content: str) -> dict:
        """
        模型输出 JSON 解析失败时进行一次纠错重试
        对应需求: REQ-M2-021
        """
        # 尝试提取 JSON (处理可能包含 markdown 代码块的情况)
        json_content = content.strip()
        
        # 去除 markdown 代码块
        if json_content.startswith("```json"):
            json_content = json_content[7:]
        elif json_content.startswith("```"):
            json_content = json_content[3:]
        if json_content.endswith("```"):
            json_content = json_content[:-3]
        json_content = json_content.strip()
        
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed, retrying: {e}")
            
            # 追加纠错提示
            retry_messages = messages + [
                {
                    "role": "assistant",
                    "content": content
                },
                {
                    "role": "user",
                    "content": f"你的输出不是合法的 JSON 格式，解析错误：{str(e)}。请重新输出纯 JSON，不要包含 markdown 代码块或其他文字。"
                }
            ]
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                request_body = {
                    "model": self.model_name,
                    "messages": retry_messages,
                    "max_tokens": 4096,
                    "temperature": 0.1
                }
                
                response = await client.post(
                    self.api_endpoint,
                    json=request_body,
                    headers=headers
                )
                response.raise_for_status()
                retry_result = response.json()
            
            retry_content = retry_result["choices"][0]["message"]["content"].strip()
            
            # 再次尝试去除 markdown
            if retry_content.startswith("```json"):
                retry_content = retry_content[7:]
            elif retry_content.startswith("```"):
                retry_content = retry_content[3:]
            if retry_content.endswith("```"):
                retry_content = retry_content[:-3]
            
            return json.loads(retry_content.strip())
    
    async def _parse_accumulated_content(self, messages: list, content: str) -> dict:
        """
        解析流式输出累积的内容
        类似 _parse_json_with_retry，但专门用于流式输出
        """
        json_content = content.strip()
        
        # 去除 markdown 代码块
        if json_content.startswith("```json"):
            json_content = json_content[7:]
        elif json_content.startswith("```"):
            json_content = json_content[3:]
        if json_content.endswith("```"):
            json_content = json_content[:-3]
        json_content = json_content.strip()
        
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed in stream, retrying: {e}")
            # 对于流式输出，如果解析失败，可以尝试重新请求
            return await self._parse_json_with_retry(messages, content)
    
    def _is_safe_url(self, url: str) -> bool:
        """
        SSRF 防护检查 (Demo 简化版)
        对应需求: REQ-M2-016
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        
        host = parsed.hostname
        if not host:
            return False
        
        # Demo 简化: 拒绝常见内网地址模式
        blocked_patterns = [
            "localhost", "127.", "10.", "192.168.", "172.16.",
            "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
            "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
            "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
            "169.254.", "::1", "0.0.0.0"
        ]
        
        host_lower = host.lower()
        for pattern in blocked_patterns:
            if host_lower.startswith(pattern) or host_lower == pattern:
                return False
        
        return True
    
    async def clarify(
        self,
        image_url: str,
        previous_result: dict,
        clarify_history: list,
        user_response: str,
        system_prompt: str
    ) -> VLParseResult:
        """
        基于用户回答进行澄清并更新配置
        用于模块 M3 的多轮澄清对话
        """
        image_base64 = await self._load_image(image_url)
        
        # 构建包含历史的对话
        if self.provider == "zhipu":
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        {"type": "text", "text": self._build_parse_prompt()}
                    ]
                },
                {"role": "assistant", "content": json.dumps(previous_result, ensure_ascii=False)}
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        {"type": "text", "text": self._build_parse_prompt()}
                    ]
                },
                {"role": "assistant", "content": json.dumps(previous_result, ensure_ascii=False)}
            ]
        
        # 添加澄清历史
        for item in clarify_history:
            messages.append({"role": "user", "content": item.get("question", "")})
            messages.append({"role": "assistant", "content": item.get("answer", "")})
        
        # 添加当前用户回答
        messages.append({
            "role": "user",
            "content": f"用户回答: {user_response}\n\n请基于这个信息更新配置，并判断是否还需要继续澄清。只输出 JSON。"
        })
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            request_body = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.1
            }
            
            response = await client.post(
                self.api_endpoint,
                json=request_body,
                headers=headers
            )
            
            response.raise_for_status()
            result = response.json()
        
        content = result["choices"][0]["message"]["content"]
        parsed_data = await self._parse_json_with_retry(messages, content)
        
        return self._build_parse_result(parsed_data)
    
    async def clarify_stream(
        self,
        image_url: str,
        previous_result: dict,
        clarify_history: list,
        user_response: str,
        system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        基于用户回答进行澄清并更新配置 (流式)
        用于模块 M3 的多轮澄清对话
        """
        try:
            image_base64 = await self._load_image(image_url)
            
            # 构建包含历史的对话
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        {"type": "text", "text": self._build_parse_prompt()}
                    ]
                },
                {"role": "assistant", "content": json.dumps(previous_result, ensure_ascii=False)}
            ]
            
            # 添加澄清历史
            for item in clarify_history:
                messages.append({"role": "user", "content": item.get("question", "")})
                messages.append({"role": "assistant", "content": item.get("answer", "")})
            
            # 添加当前用户回答
            messages.append({
                "role": "user",
                "content": f"用户回答: {user_response}\n\n请基于这个信息更新配置，并判断是否还需要继续澄清。只输出 JSON。"
            })
            
            # 根据 provider 构建请求
            if self.provider == "zhipu":
                request_body = self._build_zhipu_request(messages, stream=True)
            elif self.provider == "dashscope":
                request_body = self._build_dashscope_request(messages, stream=True)
            else:
                request_body = self._build_openai_request(messages, stream=True)
            
            accumulated_content = ""
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                async with client.stream(
                    "POST",
                    self.api_endpoint,
                    json=request_body,
                    headers=headers
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"VL API error {response.status_code}: {error_text}")
                        yield f"data: {json.dumps({'error': f'API 错误: {response.status_code}'})}\n\n"
                        return
                    
                    # 发送开始事件
                    yield f"data: {json.dumps({'type': 'start', 'message': '正在处理您的回答...'})}\n\n"
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            
                            if data_str.strip() == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    accumulated_content += content
                                    # 发送内容片段
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
            
            # 尝试解析完整的 JSON
            try:
                parsed_data = await self._parse_accumulated_content(messages, accumulated_content)
                result = self._build_parse_result(parsed_data)
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'complete', 'result': result.model_dump()})}\n\n"
                
            except Exception as e:
                logger.error(f"Failed to parse accumulated content: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'解析失败: {str(e)}'})}\n\n"
                
        except Exception as e:
            logger.error(f"Stream clarify error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
