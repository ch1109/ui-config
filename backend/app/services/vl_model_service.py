# app/services/vl_model_service.py
"""
VL 模型服务封装
支持 GLM-4V (智谱)、Qwen-VL (阿里云 DashScope) 和 Qwen2.5-VL-7B (本地部署)
对应需求: REQ-M2-007
"""

import httpx
import base64
import json
import aiofiles
import ssl
import os
from typing import Optional, Dict, Any, List, AsyncGenerator
from urllib.parse import urlparse
from app.schemas.vl_response import VLParseResult, ParsedElement, UnrecognizedButton
from app.core.config import settings
from app.core.exceptions import SSRFProtectionError, InvalidFileTypeError
import logging

logger = logging.getLogger(__name__)

# 解决 SSL 证书验证问题
# 使用 True 让 httpx 使用其内置的证书验证（基于 certifi）
def _get_ssl_verify():
    """获取 SSL 验证配置，优先使用 httpx 默认配置"""
    # 检查环境变量，允许用户自定义证书路径
    env_cert = os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')
    if env_cert and os.path.exists(env_cert):
        return env_cert
    
    # 尝试常见的系统证书路径
    possible_paths = [
        "/etc/ssl/cert.pem",  # macOS (Homebrew OpenSSL)
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
        "/usr/local/etc/openssl@3/cert.pem",  # macOS Homebrew OpenSSL 3
        "/usr/local/etc/openssl/cert.pem",  # macOS Homebrew OpenSSL
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 默认使用 httpx 内置验证（基于 certifi 或系统默认）
    return True

SSL_VERIFY = _get_ssl_verify()
logger.info(f"SSL verification config: {SSL_VERIFY}")

# Qwen2.5-VL-7B 本地部署配置
QWEN_LOCAL_ENDPOINT = "http://192.168.3.183:9000/vision/chat"
QWEN_LOCAL_AUTH = "Bearer secret123"


class VLModelService:
    """
    VL 模型服务封装
    
    支持:
    - 智谱 GLM-4V (默认)
    - 阿里云 DashScope Qwen-VL
    - Qwen2.5-VL-7B 本地部署
    
    功能: 语义级解析 - 元素识别 + 交互意图 + 业务含义推断
    """
    
    def __init__(self, selected_model: Optional[str] = None, available_buttons: Optional[List[str]] = None):
        """
        初始化 VL 模型服务
        
        Args:
            selected_model: 指定使用的模型，可选值: "glm-4.6v", "qwen2.5-vl-7b"
                           如果为 None，则使用环境变量配置的默认模型
            available_buttons: 系统中可用的按钮 ID 列表，用于验证 AI 返回的按钮
        """
        self.timeout = settings.VL_TIMEOUT
        self.selected_model = selected_model
        self.available_buttons = set(available_buttons) if available_buttons else None
        
        # 如果指定了模型，优先使用指定的模型
        if selected_model == "qwen2.5-vl-7b":
            self.provider = "qwen_local"
            self.api_key = QWEN_LOCAL_AUTH
            self.model_name = "qwen2.5-vl-7b"
            self.api_endpoint = QWEN_LOCAL_ENDPOINT
        elif selected_model == "glm-4.6v":
            self.provider = "zhipu"
            self.api_key = settings.ZHIPU_API_KEY
            self.model_name = settings.ZHIPU_MODEL_NAME
            self.api_endpoint = settings.ZHIPU_API_ENDPOINT
        else:
            # 使用环境变量配置
            self.provider = settings.VL_PROVIDER.lower()
            
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
        
        logger.info(f"VLModelService initialized with provider: {self.provider}, model: {self.model_name}")
    
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
        logger.info(f"Calling VL model: {self.provider} / {self.model_name}")
        
        # Qwen2.5-VL-7B 本地部署使用特殊的 multipart/form-data 格式
        if self.provider == "qwen_local":
            return await self._parse_image_qwen_local(image_url, system_prompt)
        
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
        
        logger.debug(f"Request body keys: {list(request_body.keys())}, model: {request_body.get('model')}")
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
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
    
    async def _parse_image_qwen_local(
        self, 
        image_url: str, 
        system_prompt: str
    ) -> VLParseResult:
        """
        使用 Qwen2.5-VL-7B 本地部署接口解析图片
        
        该接口使用 multipart/form-data 格式:
        - messages: JSON 字符串 (格式: {"messages":[{"role":"user","content":[...]}]})
        - image_file: 图片文件
        """
        # 读取图片文件
        image_bytes = await self._load_image_bytes(image_url)
        
        # 获取图片的实际类型
        content_type = "image/png"
        filename = "image.png"
        if image_url.lower().endswith(('.jpg', '.jpeg')):
            content_type = "image/jpeg"
            filename = "image.jpg"
        
        # 构建 messages JSON - 严格按照 APIfox 文档格式
        prompt_text = f"{system_prompt}\n\n{self._build_parse_prompt()}"
        messages_data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"uri": ""}}
                    ]
                }
            ]
        }
        
        logger.info(f"Calling Qwen2.5-VL-7B local API: {self.api_endpoint}")
        logger.info(f"Image size: {len(image_bytes)} bytes, content_type: {content_type}")
        logger.debug(f"Messages data: {json.dumps(messages_data, ensure_ascii=False)[:200]}...")
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
            # 使用 multipart/form-data 格式
            files = {
                "image_file": (filename, image_bytes, content_type)
            }
            data = {
                "messages": json.dumps(messages_data, ensure_ascii=False)
            }
            headers = {
                "Authorization": self.api_key
            }
            
            logger.info(f"Sending request with Authorization: {self.api_key[:20]}...")
            
            response = await client.post(
                self.api_endpoint,
                files=files,
                data=data,
                headers=headers
            )
            
            response_text = response.text
            logger.info(f"Qwen local API response status: {response.status_code}")
            logger.info(f"Qwen local API response body: {response_text[:1000] if len(response_text) > 1000 else response_text}")
            
            if response.status_code != 200:
                logger.error(f"Qwen local API error {response.status_code}: {response_text}")
                raise Exception(f"Qwen API 调用失败: {response.status_code} - {response_text}")
            
            try:
                result = response.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {e}, raw: {response_text}")
                raise Exception(f"解析响应失败: {response_text}")
        
        logger.info(f"Qwen local API parsed response type: {type(result)}")
        logger.info(f"Qwen local API parsed response keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        # 解析响应 - Qwen API 返回格式: {"result": {"choices": [...]}, "status": "ok"}
        content = None
        if isinstance(result, dict):
            # 首先检查是否有外层的 result 包装
            actual_result = result
            if "result" in result and isinstance(result["result"], dict):
                actual_result = result["result"]
                logger.info(f"Unwrapped result, inner keys: {actual_result.keys()}")
            
            # 尝试各种可能的响应格式
            if "choices" in actual_result and actual_result["choices"]:
                choice = actual_result["choices"][0]
                if isinstance(choice, dict):
                    if "message" in choice and isinstance(choice["message"], dict):
                        content = choice["message"].get("content", "")
                    elif "text" in choice:
                        content = choice["text"]
            elif "response" in actual_result:
                content = actual_result["response"]
            elif "content" in actual_result:
                content = actual_result["content"]
            elif "text" in actual_result:
                content = actual_result["text"]
            elif "output" in actual_result:
                content = actual_result["output"]
            elif "data" in actual_result:
                data_field = actual_result["data"]
                if isinstance(data_field, str):
                    content = data_field
                elif isinstance(data_field, dict):
                    content = data_field.get("content") or data_field.get("text") or json.dumps(data_field, ensure_ascii=False)
            
            if content is None:
                # 如果还是找不到，把整个结果当作内容
                logger.warning(f"Could not find content field in response, using full response")
                content = json.dumps(actual_result, ensure_ascii=False)
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)
        
        logger.info(f"Extracted content length: {len(content) if content else 0}")
        logger.info(f"Qwen local model response: {content[:500] if content and len(content) > 500 else content}")
        
        if not content or content.strip() == "" or content == "{}":
            logger.error("Qwen API returned empty content!")
            raise Exception("Qwen API 返回了空内容，请检查接口配置或图片是否正确发送")
        
        # 尝试解析 JSON
        messages = [{"role": "user", "content": prompt_text}]
        parsed_data = await self._parse_json_with_retry(messages, content)
        
        return self._build_parse_result(parsed_data)
    
    async def _load_image_bytes(self, image_url: str) -> bytes:
        """加载图片并返回原始字节"""
        if image_url.startswith(("http://", "https://")):
            # REQ-M2-016: SSRF 防护
            if not self._is_safe_url(image_url):
                raise SSRFProtectionError()
            
            async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
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
                
                return image_bytes
        else:
            # 本地文件 (REQ-M2-018: 仅允许 uploads 目录)
            if not image_url.startswith("/uploads/"):
                raise ValueError("仅允许读取 uploads 目录下的文件")
            
            file_path = image_url.lstrip("/")
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
    
    async def _parse_image_stream_qwen_local(
        self, 
        image_url: str, 
        system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        使用 Qwen2.5-VL-7B 本地部署接口流式解析图片
        
        注: 本地接口可能不支持真正的流式输出，这里使用非流式调用并模拟流式返回
        支持两阶段工作流程：分析总结（summary）和最终配置（complete）
        """
        try:
            yield f"data: {json.dumps({'type': 'start', 'message': '正在使用 Qwen2.5-VL-7B 分析图片...'})}\n\n"
            
            # 读取图片文件
            image_bytes = await self._load_image_bytes(image_url)
            
            # 获取图片的实际类型
            content_type = "image/png"
            filename = "image.png"
            if image_url.lower().endswith(('.jpg', '.jpeg')):
                content_type = "image/jpeg"
                filename = "image.jpg"
            
            # 构建 messages JSON
            prompt_text = f"{system_prompt}\n\n{self._build_parse_prompt()}"
            messages_data = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"uri": ""}}
                        ]
                    }
                ]
            }
            
            async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
                files = {
                    "image_file": (filename, image_bytes, content_type)
                }
                data = {
                    "messages": json.dumps(messages_data, ensure_ascii=False)
                }
                headers = {
                    "Authorization": self.api_key
                }
                
                response = await client.post(
                    self.api_endpoint,
                    files=files,
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception(f"Qwen API 调用失败: {response.status_code}")
                
                result = response.json()
            
            # 提取响应内容
            content = self._extract_qwen_response_content(result)
            
            if not content or content.strip() == "":
                raise Exception("Qwen API 返回了空内容")
            
            # 分块输出内容（用于前端流式显示）
            chunk_size = 100
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            # 检测是否为 JSON（两阶段工作流程）
            if self._is_json_content(content):
                # 第二阶段：JSON 配置
                messages = [{"role": "user", "content": prompt_text}]
                parsed_data = await self._parse_json_with_retry(messages, content)
                result_obj = self._build_parse_result(parsed_data)
                yield f"data: {json.dumps({'type': 'complete', 'result': result_obj.model_dump()})}\n\n"
            else:
                # 第一阶段：分析总结
                logger.info("Qwen local: Detected summary output (non-JSON)")
                yield f"data: {json.dumps({'type': 'summary', 'content': content})}\n\n"
            
        except Exception as e:
            logger.error(f"Qwen local stream parsing error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    def _extract_qwen_response_content(self, result: dict) -> str:
        """从 Qwen API 响应中提取内容"""
        content = None
        if isinstance(result, dict):
            actual_result = result
            if "result" in result and isinstance(result["result"], dict):
                actual_result = result["result"]
            
            if "choices" in actual_result and actual_result["choices"]:
                choice = actual_result["choices"][0]
                if isinstance(choice, dict):
                    if "message" in choice and isinstance(choice["message"], dict):
                        content = choice["message"].get("content", "")
                    elif "text" in choice:
                        content = choice["text"]
            elif "response" in actual_result:
                content = actual_result["response"]
            elif "content" in actual_result:
                content = actual_result["content"]
            elif "text" in actual_result:
                content = actual_result["text"]
            elif "output" in actual_result:
                content = actual_result["output"]
            elif "data" in actual_result:
                data_field = actual_result["data"]
                if isinstance(data_field, str):
                    content = data_field
                elif isinstance(data_field, dict):
                    content = data_field.get("content") or data_field.get("text") or json.dumps(data_field, ensure_ascii=False)
            
            if content is None:
                content = json.dumps(actual_result, ensure_ascii=False)
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)
        
        return content or ""
    
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
        logger.info(f"Calling VL model (stream): {self.provider} / {self.model_name}")
        
        # Qwen2.5-VL-7B 本地部署 - 由于接口可能不支持流式，使用非流式模式模拟
        if self.provider == "qwen_local":
            async for chunk in self._parse_image_stream_qwen_local(image_url, system_prompt):
                yield chunk
            return
        
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
            
            accumulated_content = ""
            
            async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
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
            
            # 检测输出是否为 JSON（两阶段工作流程）
            logger.debug(f"Accumulated content length: {len(accumulated_content)}")
            
            # 尝试判断是否为 JSON 格式（第二阶段输出）
            is_json_output = self._is_json_content(accumulated_content)
            
            if is_json_output:
                # 第二阶段：输出是 JSON 配置，发送 complete 事件
                try:
                    parsed_data = await self._parse_accumulated_content(messages, accumulated_content)
                    result = self._build_parse_result(parsed_data)
                    yield f"data: {json.dumps({'type': 'complete', 'result': result.model_dump()})}\n\n"
                except Exception as e:
                    logger.error(f"Failed to parse JSON content: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'解析失败: {str(e)}'})}\n\n"
            else:
                # 第一阶段：输出是分析总结（自然语言），发送 summary 事件
                logger.info("Detected summary output (non-JSON), sending summary event")
                yield f"data: {json.dumps({'type': 'summary', 'content': accumulated_content})}\n\n"
                
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
            "max_tokens": 16384,  # 增加到 16K 以支持复杂页面
            "temperature": 0.1,
            "stream": stream
        }
    
    def _build_dashscope_request(self, messages: list, stream: bool = False) -> dict:
        """构建 DashScope API 请求体"""
        return {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 16384,  # 增加到 16K 以支持复杂页面
            "temperature": 0.1,
            "stream": stream
        }
    
    def _build_openai_request(self, messages: list, stream: bool = False) -> dict:
        """构建 OpenAI 兼容 API 请求体"""
        request = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 16384,  # 增加到 16K 以支持复杂页面
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
            
            async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
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
  "page_id": "4.1face_authorization_page",
  "page_name": {
    "zh-CN": "4.1人脸授权页",
    "en": "4.1 face_authorization_page"
  },
  "page_description": {
    "zh-CN": "页面功能描述，包含：\\n1. 功能概述\\n2. 用户可执行的操作\\n\\n## 行为规则\\nAI 行为约束...\\n\\n## 页面目标\\n用户目标...",
    "en": "Page description with behavior rules and goals"
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
  "overall_confidence": 0.85,
  "clarification_needed": true,
  "clarification_questions": ["如果需要澄清，列出问题"]
}

注意：
1. **page_id 命名规范**：格式为 `{页面编号}{英文名称}`，如 `4.1face_authorization_page`，编号与名称之间不加空格，英文名称中每个单词用下划线 `_` 分隔
2. **page_name.en 命名规范**：格式为 `{页面编号} {英文名称}`，如 `4.1 face_authorization_page`，编号与名称之间需要一个空格
3. element_id 使用 snake_case 格式
4. page_description 应包含完整的上下文信息：功能说明、行为规则和页面目标
5. 如果某些元素的用途不明确，请设置 clarification_needed 为 true，并在 clarification_questions 中提出具体问题
6. confidence 取值 0-1，表示识别的置信度
7. 请只输出 JSON，不要有其他文字
"""
    
    def _build_parse_result(self, data: dict) -> VLParseResult:
        """构建解析结果对象，并验证按钮列表"""
        logger.info(f"_build_parse_result called, available_buttons={self.available_buttons}")
        logger.info(f"Raw button_list from AI: {data.get('button_list', [])}")
        
        # 单词级别的中英文翻译映射（用于组合翻译）
        word_translation = {
            # 动词/操作
            "return": "返回", "go": "前往", "back": "返回", "forward": "前进",
            "confirm": "确认", "cancel": "取消", "submit": "提交", "save": "保存",
            "delete": "删除", "remove": "移除", "edit": "编辑", "add": "添加",
            "clear": "清除", "reset": "重置", "refresh": "刷新", "exit": "退出",
            "close": "关闭", "open": "打开", "start": "开始", "stop": "停止",
            "search": "搜索", "query": "查询", "find": "查找", "filter": "筛选",
            "select": "选择", "check": "勾选", "uncheck": "取消勾选",
            "input": "输入", "enter": "输入", "type": "输入",
            "print": "打印", "scan": "扫描", "upload": "上传", "download": "下载",
            "sign": "签名", "verify": "验证", "authorize": "授权",
            "transfer": "转账", "withdraw": "取款", "deposit": "存款",
            "pay": "支付", "receive": "收款", "send": "发送",
            "take": "拍摄", "retake": "重拍", "capture": "采集",
            "call": "呼叫", "help": "帮助", "assist": "协助",
            "view": "查看", "show": "显示", "hide": "隐藏",
            "enable": "启用", "disable": "禁用",
            "login": "登录", "logout": "登出", "register": "注册",
            "update": "更新", "modify": "修改", "change": "更改",
            "create": "创建", "new": "新建",
            "copy": "复制", "paste": "粘贴", "cut": "剪切",
            "undo": "撤销", "redo": "重做",
            "report": "申报", "apply": "申请",
            # 名词/对象
            "home": "首页", "page": "页面", "screen": "屏幕",
            "button": "按钮", "menu": "菜单", "list": "列表", "form": "表单",
            "account": "账户", "user": "用户", "customer": "客户", "member": "会员",
            "password": "密码", "pin": "密码", "code": "验证码",
            "card": "卡片", "id": "证件", "identity": "身份",
            "photo": "照片", "image": "图片", "picture": "图片",
            "face": "人脸", "fingerprint": "指纹", "signature": "签名",
            "document": "文档", "file": "文件", "record": "记录",
            "transaction": "交易", "order": "订单", "bill": "账单",
            "balance": "余额", "amount": "金额", "fee": "费用",
            "date": "日期", "time": "时间", "period": "期限",
            "name": "姓名", "phone": "电话", "email": "邮箱", "address": "地址",
            "info": "信息", "information": "信息", "detail": "详情", "details": "详情",
            "settings": "设置", "options": "选项", "preferences": "偏好",
            "notification": "通知", "message": "消息", "alert": "提醒",
            "error": "错误", "warning": "警告", "success": "成功",
            "result": "结果", "status": "状态",
            "assistant": "助手", "service": "服务", "support": "支持",
            # 形容词/修饰词
            "normal": "正常", "regular": "普通", "standard": "标准",
            "loss": "挂失", "lost": "遗失", "missing": "丢失",
            "new": "新", "old": "旧", "current": "当前", "previous": "上一", "next": "下一",
            "first": "第一", "last": "最后", "all": "全部", "none": "无",
            "more": "更多", "less": "更少",
            "quick": "快速", "fast": "快速", "slow": "慢速",
            "auto": "自动", "manual": "手动",
            "valid": "有效", "invalid": "无效", "expired": "过期",
            "active": "活跃", "inactive": "非活跃",
            "online": "在线", "offline": "离线",
            "personal": "个人", "business": "企业", "corporate": "公司",
            # 业务专用词
            "closure": "销户", "cancellation": "销户", "termination": "终止",
            "activation": "激活", "deactivation": "停用",
            "authorization": "授权", "authentication": "认证",
            "recognition": "识别", "verification": "验证",
            "registration": "注册", "enrollment": "登记",
            "step": "步骤", "stage": "阶段", "process": "流程",
            # 方位/位置
            "left": "左", "right": "右", "up": "上", "down": "下",
            "top": "顶部", "bottom": "底部", "center": "中心",
            # 符号操作
            "backspace": "退格", "space": "空格", "tab": "制表符",
            "ok": "确定", "yes": "是", "no": "否",
        }
        
        def get_button_names(btn_id: str, label: str = "") -> tuple:
            """根据按钮 ID 获取中英文名称，通过逐词翻译实现"""
            # 标准化 ID
            normalized_id = btn_id.lower().replace("-", "_")
            
            # 生成英文名称：下划线转空格，首字母大写
            en_name = btn_id.replace("_", " ").title()
            
            # 分割单词并逐个翻译生成中文名称
            words = normalized_id.split("_")
            zh_words = []
            for word in words:
                if word in word_translation:
                    zh_words.append(word_translation[word])
                else:
                    # 未知单词保留原样（首字母大写）
                    zh_words.append(word.title())
            
            zh_name = "".join(zh_words)
            
            return (zh_name, en_name)
        
        elements = []
        for elem in data.get("elements", []):
            try:
                elements.append(ParsedElement(**elem))
            except Exception as e:
                logger.warning(f"Failed to parse element: {elem}, error: {e}")
        
        # 解析 AI 返回的未识别按钮
        unrecognized_buttons = []
        for btn in data.get("unrecognized_buttons", []):
            try:
                unrecognized_buttons.append(UnrecognizedButton(**btn))
            except Exception as e:
                logger.warning(f"Failed to parse unrecognized button: {btn}, error: {e}")
        
        # 获取 AI 返回的按钮列表
        raw_button_list = data.get("button_list", [])
        validated_button_list = []
        
        # 验证按钮列表：将系统中不存在的按钮移到 unrecognized_buttons
        if self.available_buttons is not None:
            for btn_id in raw_button_list:
                if btn_id in self.available_buttons:
                    validated_button_list.append(btn_id)
                else:
                    # 按钮不在系统中，添加到 unrecognized_buttons
                    # 从 elements 中尝试找到对应的按钮信息
                    btn_label = btn_id  # 默认使用 ID 作为名称
                    btn_context = ""
                    for elem in elements:
                        if elem.element_id == btn_id or (hasattr(elem, 'label') and elem.label and btn_id in elem.label.lower().replace(' ', '_')):
                            btn_label = elem.label or btn_id
                            btn_context = elem.inferred_intent or ""
                            break
                    
                    # 获取中英文名称
                    name_zh, name_en = get_button_names(btn_id, btn_label)
                    
                    # 检查是否已经在 unrecognized_buttons 中
                    already_exists = any(ub.suggested_id == btn_id for ub in unrecognized_buttons)
                    if not already_exists:
                        unrecognized_buttons.append(UnrecognizedButton(
                            suggested_id=btn_id,
                            suggested_name_zh=name_zh,
                            suggested_name_en=name_en,
                            context=btn_context
                        ))
                        logger.info(f"Button '{btn_id}' not in available buttons, moved to unrecognized_buttons (zh: {name_zh}, en: {name_en})")
        else:
            # 没有可用按钮列表，直接使用 AI 返回的列表
            validated_button_list = raw_button_list
        
        return VLParseResult(
            page_id=data.get("page_id"),
            page_name=data.get("page_name", {"zh-CN": "", "en": ""}),
            page_description=data.get("page_description", {"zh-CN": "", "en": ""}),
            elements=elements,
            button_list=validated_button_list,
            optional_actions=data.get("optional_actions", []),
            unrecognized_buttons=unrecognized_buttons,
            ai_context=data.get("ai_context", {}),
            overall_confidence=data.get("overall_confidence", 0.5),
            clarification_needed=data.get("clarification_needed", False),
            clarification_questions=data.get("clarification_questions")
        )

    def _is_json_content(self, content: str) -> bool:
        """
        检测内容是否为 JSON 格式
        用于两阶段工作流程：判断是分析总结（自然语言）还是最终配置（JSON）
        """
        if not content or not content.strip():
            return False
        
        cleaned = content.strip()
        
        # 去除可能的 markdown 代码块
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        # 检查是否以 JSON 对象或数组开头
        if not (cleaned.startswith("{") or cleaned.startswith("[")):
            return False
        
        # 尝试解析 JSON
        try:
            json.loads(cleaned)
            return True
        except json.JSONDecodeError:
            # 可能是不完整的 JSON 或格式有问题
            # 如果以 { 开头并包含 "page_id" 等关键字，认为是 JSON
            if cleaned.startswith("{") and '"page_id"' in cleaned:
                return True
            return False

    def _clean_json_content(self, content: str) -> str:
        """
        清理 JSON 内容中的非法控制字符和格式问题
        处理模型输出中可能包含的未转义换行符、反斜杠等问题
        """
        import re
        
        # 去除 markdown 代码块
        json_content = content.strip()
        if json_content.startswith("```json"):
            json_content = json_content[7:]
        elif json_content.startswith("```"):
            json_content = json_content[3:]
        if json_content.endswith("```"):
            json_content = json_content[:-3]
        json_content = json_content.strip()
        
        # 先尝试直接解析
        try:
            json.loads(json_content)
            return json_content
        except json.JSONDecodeError:
            pass
        
        # 如果失败，逐字符清理
        result = []
        in_string = False
        i = 0
        
        while i < len(json_content):
            char = json_content[i]
            
            # 处理转义序列
            if char == '\\' and in_string and i + 1 < len(json_content):
                next_char = json_content[i + 1]
                # 合法的转义字符
                if next_char in '"\\bfnrtu/':
                    result.append(char)
                    result.append(next_char)
                    i += 2
                    continue
                else:
                    # 不合法的转义，转义反斜杠本身
                    result.append('\\\\')
                    i += 1
                    continue
            
            # 处理引号（字符串边界）
            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue
            
            if in_string:
                # 在字符串内，处理控制字符
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                elif ord(char) < 32:
                    # 跳过其他控制字符
                    pass
                else:
                    result.append(char)
            else:
                # 在字符串外，保留换行和空白（JSON 允许）
                result.append(char)
            
            i += 1
        
        cleaned = ''.join(result)
        
        # 再次尝试解析，如果仍然失败，尝试更激进的修复
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            # 尝试修复常见的 JSON 问题
            # 1. 移除尾随逗号
            cleaned = re.sub(r',\s*([\]\}])', r'\1', cleaned)
            # 2. 确保属性名使用双引号
            cleaned = re.sub(r"([{,]\s*)'([^']+)'\s*:", r'\1"\2":', cleaned)
            # 3. 修复可能的编码问题
            cleaned = cleaned.encode('utf-8', errors='ignore').decode('utf-8')
            
            return cleaned

    async def _parse_json_with_retry(self, messages: list, content: str) -> dict:
        """
        模型输出 JSON 解析失败时进行一次纠错重试
        对应需求: REQ-M2-021
        """
        # 清理并提取 JSON 内容
        json_content = self._clean_json_content(content)
        
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
            
            # 添加延迟，避免立即重试导致限流
            import asyncio
            await asyncio.sleep(2.0)  # 延迟 2 秒再重试
            
            async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                request_body = {
                    "model": self.model_name,
                    "messages": retry_messages,
                    "max_tokens": 16384,  # 增加到 16K 以支持复杂页面
                    "temperature": 0.1
                }
                
                try:
                    response = await client.post(
                        self.api_endpoint,
                        json=request_body,
                        headers=headers
                    )
                    response.raise_for_status()
                    retry_result = response.json()
                except httpx.HTTPStatusError as e:
                    # 处理 429 限流错误
                    if e.response.status_code == 429:
                        logger.error("JSON 解析重试时遇到 API 限流 (429)，跳过重试")
                        # 如果遇到限流，直接抛出原始 JSON 解析错误，而不是继续重试
                        raise json.JSONDecodeError(
                            f"JSON 解析失败，且重试时遇到 API 限流: {str(e)}",
                            json_content,
                            0
                        ) from e
                    raise
            
            retry_content = retry_result["choices"][0]["message"]["content"].strip()
            
            # 再次清理并解析
            retry_content = self._clean_json_content(retry_content)
            
            return json.loads(retry_content)
    
    async def _parse_accumulated_content(self, messages: list, content: str) -> dict:
        """
        解析流式输出累积的内容
        类似 _parse_json_with_retry，但专门用于流式输出
        """
        # 清理并提取 JSON 内容
        json_content = self._clean_json_content(content)
        
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
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            request_body = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": 16384,  # 增加到 16K 以支持复杂页面
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
            
            async with httpx.AsyncClient(timeout=self.timeout, verify=SSL_VERIFY) as client:
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
