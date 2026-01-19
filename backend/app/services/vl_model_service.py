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
from app.schemas.vl_response import VLParseResult, ParsedElement
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
    
    def __init__(self, selected_model: Optional[str] = None):
        """
        初始化 VL 模型服务
        
        Args:
            selected_model: 指定使用的模型，可选值: "glm-4.6v", "qwen2.5-vl-7b"
                           如果为 None，则使用环境变量配置的默认模型
        """
        self.timeout = settings.VL_TIMEOUT
        self.selected_model = selected_model
        
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
        """
        try:
            yield f"data: {json.dumps({'type': 'start', 'message': '正在使用 Qwen2.5-VL-7B 分析图片...'})}\n\n"
            
            # 调用非流式接口
            result = await self._parse_image_qwen_local(image_url, system_prompt)
            
            # 模拟流式输出完整的 JSON 响应
            result_json = json.dumps(result.model_dump(), ensure_ascii=False)
            
            # 分块输出内容
            chunk_size = 100
            for i in range(0, len(result_json), chunk_size):
                chunk = result_json[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({'type': 'complete', 'result': result.model_dump()})}\n\n"
            
        except Exception as e:
            logger.error(f"Qwen local stream parsing error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
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
        """构建解析结果对象"""
        elements = []
        for elem in data.get("elements", []):
            try:
                elements.append(ParsedElement(**elem))
            except Exception as e:
                logger.warning(f"Failed to parse element: {elem}, error: {e}")
        
        return VLParseResult(
            page_id=data.get("page_id"),
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

    def _clean_json_content(self, content: str) -> str:
        """
        清理 JSON 内容中的非法控制字符
        处理模型输出中可能包含的未转义换行符等问题
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
        
        # 清理字符串值中的非法控制字符
        # 这个正则表达式匹配 JSON 字符串值并替换其中的控制字符
        def clean_string_value(match):
            value = match.group(0)
            # 替换未转义的控制字符
            value = value.replace('\n', '\\n')
            value = value.replace('\r', '\\r')
            value = value.replace('\t', '\\t')
            # 移除其他控制字符 (ASCII 0-31 除了已转义的)
            cleaned = ''
            i = 0
            while i < len(value):
                char = value[i]
                if char == '\\' and i + 1 < len(value):
                    # 保留合法的转义序列
                    cleaned += char + value[i + 1]
                    i += 2
                elif ord(char) < 32 and char not in '\n\r\t':
                    # 跳过非法控制字符
                    i += 1
                else:
                    cleaned += char
                    i += 1
            return cleaned
        
        # 使用更简单的方法：直接替换字符串中的非法字符
        # 先尝试直接解析
        try:
            json.loads(json_content)
            return json_content
        except json.JSONDecodeError:
            pass
        
        # 如果失败，清理控制字符
        # 替换字符串值内的裸换行符为转义版本
        # 这个正则匹配 "..." 字符串，处理其中的控制字符
        result = []
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_content):
            if escape_next:
                result.append(char)
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                result.append(char)
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                result.append(char)
                continue
            
            if in_string:
                # 在字符串内，替换控制字符
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                elif ord(char) < 32:
                    # 跳过其他控制字符
                    continue
                else:
                    result.append(char)
            else:
                # 在字符串外，保留换行和空白（JSON 允许）
                result.append(char)
        
        return ''.join(result)
    
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
                
                response = await client.post(
                    self.api_endpoint,
                    json=request_body,
                    headers=headers
                )
                response.raise_for_status()
                retry_result = response.json()
            
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
