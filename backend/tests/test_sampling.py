# tests/test_sampling.py
"""
Sampling 服务单元测试

测试 MCP Sampling 功能的核心逻辑：
1. 请求验证和安全策略
2. 速率限制
3. 内容过滤
4. 审核流程
5. LLM 调用（Mock）
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.sampling_service import (
    SamplingService,
    SamplingRequest,
    SamplingResponse,
    SamplingMessage,
    SamplingSecurityConfig,
    SamplingApprovalStatus,
    SamplingStopReason,
    ModelPreferences
)


class TestSamplingMessage:
    """测试 SamplingMessage 数据类"""
    
    def test_from_dict_text_content(self):
        """测试从字典创建文本消息"""
        data = {
            "role": "user",
            "content": {"type": "text", "text": "你好"}
        }
        msg = SamplingMessage.from_dict(data)
        
        assert msg.role == "user"
        assert msg.content["type"] == "text"
        assert msg.get_text() == "你好"
    
    def test_from_dict_image_content(self):
        """测试从字典创建图片消息"""
        data = {
            "role": "assistant",
            "content": {"type": "image", "data": "base64..."}
        }
        msg = SamplingMessage.from_dict(data)
        
        assert msg.role == "assistant"
        assert msg.content["type"] == "image"
        assert msg.get_text() == ""  # 图片消息返回空文本
    
    def test_to_dict(self):
        """测试转换为字典"""
        msg = SamplingMessage(
            role="user",
            content={"type": "text", "text": "测试"}
        )
        data = msg.to_dict()
        
        assert data["role"] == "user"
        assert data["content"]["text"] == "测试"


class TestModelPreferences:
    """测试 ModelPreferences 数据类"""
    
    def test_from_dict_with_hints(self):
        """测试从字典创建模型偏好（含提示）"""
        data = {
            "hints": [{"name": "gpt-4"}],
            "intelligencePriority": 0.8,
            "speedPriority": 0.2
        }
        prefs = ModelPreferences.from_dict(data)
        
        assert len(prefs.hints) == 1
        assert prefs.hints[0]["name"] == "gpt-4"
        assert prefs.intelligence_priority == 0.8
        assert prefs.speed_priority == 0.2
    
    def test_from_dict_none(self):
        """测试从 None 创建默认偏好"""
        prefs = ModelPreferences.from_dict(None)
        
        assert prefs.hints == []
        assert prefs.intelligence_priority == 0.5
        assert prefs.speed_priority == 0.5


class TestSamplingRequest:
    """测试 SamplingRequest 数据类"""
    
    def test_from_mcp_params(self):
        """测试从 MCP 参数创建请求"""
        params = {
            "messages": [
                {"role": "user", "content": {"type": "text", "text": "你好"}}
            ],
            "maxTokens": 100,
            "systemPrompt": "你是助手",
            "temperature": 0.7
        }
        
        request = SamplingRequest.from_mcp_params("req_1", "server_a", params)
        
        assert request.id == "req_1"
        assert request.server_key == "server_a"
        assert len(request.messages) == 1
        assert request.max_tokens == 100
        assert request.system_prompt == "你是助手"
        assert request.temperature == 0.7
    
    def test_to_dict(self):
        """测试转换为字典"""
        request = SamplingRequest(
            id="req_1",
            server_key="server_a",
            messages=[SamplingMessage("user", {"type": "text", "text": "hi"})],
            max_tokens=100
        )
        data = request.to_dict()
        
        assert data["id"] == "req_1"
        assert data["server_key"] == "server_a"
        assert data["max_tokens"] == 100


class TestSamplingSecurityConfig:
    """测试 SamplingSecurityConfig"""
    
    def test_default_values(self):
        """测试默认配置值"""
        config = SamplingSecurityConfig()
        
        assert config.max_tokens_limit == 4096
        assert config.rate_limit_per_minute == 60
        assert config.enable_content_filter == True
        assert config.require_approval == False
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = SamplingSecurityConfig(
            max_tokens_limit=2048,
            blocked_keywords=["敏感词"]
        )
        data = config.to_dict()
        
        assert data["max_tokens_limit"] == 2048
        assert "敏感词" in data["blocked_keywords"]


class TestSamplingService:
    """测试 SamplingService 核心功能"""
    
    @pytest.fixture
    def service(self):
        """创建测试用的 SamplingService 实例"""
        return SamplingService()
    
    @pytest.fixture
    def sample_request(self):
        """创建示例请求"""
        return SamplingRequest(
            id="test_req_1",
            server_key="test_server",
            messages=[
                SamplingMessage("user", {"type": "text", "text": "你好"})
            ],
            max_tokens=100
        )
    
    def test_update_config(self, service):
        """测试更新配置"""
        service.update_config({
            "max_tokens_limit": 2048,
            "blocked_keywords": ["禁止词"]
        })
        
        assert service.config.max_tokens_limit == 2048
        assert "禁止词" in service.config.blocked_keywords
    
    def test_check_server_permission_blocked(self, service):
        """测试 Server 权限检查 - 黑名单"""
        service.config.blocked_servers = ["bad_server"]
        
        ok, msg = service._check_server_permission("bad_server")
        
        assert ok == False
        assert "已被阻止" in msg
    
    def test_check_server_permission_whitelist(self, service):
        """测试 Server 权限检查 - 白名单"""
        service.config.allowed_servers = ["good_server"]
        
        ok, _ = service._check_server_permission("good_server")
        assert ok == True
        
        ok, msg = service._check_server_permission("other_server")
        assert ok == False
        assert "不在" in msg
    
    def test_check_rate_limit_global(self, service):
        """测试全局速率限制"""
        service.config.rate_limit_per_minute = 2
        
        # 记录两个请求
        service._record_request("server_a")
        service._record_request("server_b")
        
        # 第三个请求应该被限制
        ok, msg = service._check_rate_limit("server_c")
        
        assert ok == False
        assert "全局速率限制" in msg
    
    def test_check_rate_limit_per_server(self, service):
        """测试 Server 级速率限制"""
        service.config.rate_limit_per_server = 2
        
        # 同一个 server 记录两个请求
        service._record_request("server_a")
        service._record_request("server_a")
        
        # 第三个请求应该被限制
        ok, msg = service._check_rate_limit("server_a")
        
        assert ok == False
        assert "server_a" in msg
    
    def test_check_token_limit_exceed(self, service):
        """测试 Token 限制 - 超出限制"""
        service.config.max_tokens_limit = 1000
        
        ok, adjusted, msg = service._check_token_limit(2000)
        
        assert ok == True
        assert adjusted == 1000  # 调整为上限
        assert "调整" in msg
    
    def test_check_token_limit_default(self, service):
        """测试 Token 限制 - 使用默认值"""
        service.config.default_max_tokens = 512
        
        ok, adjusted, _ = service._check_token_limit(0)
        
        assert adjusted == 512
    
    def test_filter_content_blocked(self, service):
        """测试内容过滤 - 包含禁止词"""
        service.config.blocked_keywords = ["敏感"]
        
        messages = [
            SamplingMessage("user", {"type": "text", "text": "这是敏感内容"})
        ]
        
        ok, msg = service._filter_content(messages)
        
        assert ok == False
        assert "敏感" in msg
    
    def test_filter_content_disabled(self, service):
        """测试内容过滤 - 禁用过滤"""
        service.config.enable_content_filter = False
        service.config.blocked_keywords = ["敏感"]
        
        messages = [
            SamplingMessage("user", {"type": "text", "text": "这是敏感内容"})
        ]
        
        ok, _ = service._filter_content(messages)
        
        assert ok == True  # 禁用过滤后不检查
    
    def test_should_auto_approve_low_tokens(self, service):
        """测试自动批准 - 低 token 请求"""
        service.config.require_approval = True
        service.config.auto_approve_threshold = 100
        
        request = SamplingRequest(
            id="r1",
            server_key="s1",
            messages=[],
            max_tokens=50  # 低于阈值
        )
        
        assert service._should_auto_approve(request) == True
    
    def test_should_auto_approve_high_tokens(self, service):
        """测试自动批准 - 高 token 请求"""
        service.config.require_approval = True
        service.config.auto_approve_threshold = 100
        
        request = SamplingRequest(
            id="r1",
            server_key="s1",
            messages=[],
            max_tokens=200  # 高于阈值
        )
        
        assert service._should_auto_approve(request) == False
    
    @pytest.mark.asyncio
    async def test_validate_request_success(self, service, sample_request):
        """测试请求验证 - 成功"""
        is_valid, error, request = await service.validate_request(sample_request)
        
        assert is_valid == True
        assert error == ""
    
    @pytest.mark.asyncio
    async def test_validate_request_blocked_server(self, service, sample_request):
        """测试请求验证 - Server 被阻止"""
        service.config.blocked_servers = ["test_server"]
        
        is_valid, error, _ = await service.validate_request(sample_request)
        
        assert is_valid == False
        assert "阻止" in error
    
    @pytest.mark.asyncio
    async def test_reject_request(self, service, sample_request):
        """测试拒绝请求"""
        # 将请求加入待审核队列
        service._pending_requests[sample_request.id] = sample_request
        
        result = await service.reject_request(sample_request.id, "不允许")
        
        assert "error" in result
        assert result["error"]["message"] == "不允许"
        assert sample_request.id not in service._pending_requests
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_requests(self, service):
        """测试清理过期请求"""
        service.config.approval_timeout_seconds = 1
        
        # 创建一个"过期"的请求
        old_request = SamplingRequest(
            id="old_req",
            server_key="s1",
            messages=[],
            max_tokens=100,
            created_at=datetime.now() - timedelta(seconds=10)
        )
        service._pending_requests["old_req"] = old_request
        
        expired = await service.cleanup_expired_requests()
        
        assert "old_req" in expired
        assert "old_req" not in service._pending_requests
    
    def test_get_status(self, service):
        """测试获取状态"""
        service._pending_requests["r1"] = MagicMock()
        service._record_request("s1")
        
        status = service.get_status()
        
        assert status["enabled"] == True
        assert status["pending_requests_count"] == 1
        assert "rate_limit" in status


class TestSamplingServiceLLMCalls:
    """测试 SamplingService LLM 调用（需要 Mock）"""
    
    @pytest.fixture
    def service(self):
        return SamplingService()
    
    @pytest.mark.asyncio
    async def test_call_llm_openai(self, service):
        """测试调用 OpenAI API（Mock）"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "你好！"},
                "finish_reason": "stop"
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(service, '_get_http_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_client.return_value = mock_http
            
            result = await service._call_openai(
                mock_http,
                [{"role": "user", "content": "hi"}],
                "gpt-4",
                "fake_key",
                None,
                0.7,
                100,
                []
            )
            
            assert result.content["text"] == "你好！"
            assert result.stop_reason == SamplingStopReason.END_TURN
    
    @pytest.mark.asyncio
    async def test_handle_sampling_request_auto_approve(self, service):
        """测试处理自动批准的请求（Mock LLM）"""
        service.config.require_approval = False
        
        params = {
            "messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}],
            "maxTokens": 50
        }
        
        # Mock _call_llm
        with patch.object(service, '_call_llm') as mock_llm:
            mock_llm.return_value = SamplingResponse(
                role="assistant",
                content={"type": "text", "text": "Hello!"},
                model="gpt-4",
                stop_reason=SamplingStopReason.END_TURN
            )
            
            result = await service.handle_sampling_request(
                "test_server",
                1,
                params,
                {"provider": "openai", "api_key": "fake"}
            )
            
            assert "result" in result
            assert result["result"]["content"]["text"] == "Hello!"


class TestSamplingResponse:
    """测试 SamplingResponse"""
    
    def test_to_mcp_result(self):
        """测试转换为 MCP 响应格式"""
        response = SamplingResponse(
            role="assistant",
            content={"type": "text", "text": "回复内容"},
            model="gpt-4",
            stop_reason=SamplingStopReason.END_TURN
        )
        
        result = response.to_mcp_result()
        
        assert result["role"] == "assistant"
        assert result["content"]["text"] == "回复内容"
        assert result["model"] == "gpt-4"
        assert result["stopReason"] == "endTurn"
    
    def test_stop_reason_max_tokens(self):
        """测试 max_tokens 停止原因"""
        response = SamplingResponse(
            stop_reason=SamplingStopReason.MAX_TOKENS
        )
        
        result = response.to_mcp_result()
        
        assert result["stopReason"] == "maxTokens"
