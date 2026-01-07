# tests/test_system_prompt.py
"""
M1 - System Prompt 配置管理测试
对应需求: REQ-M1-001 ~ REQ-M1-012
"""

import pytest
from fastapi.testclient import TestClient
from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT


class TestSystemPromptAPI:
    """System Prompt API 测试"""
    
    def test_get_prompt_returns_default_when_empty(self, client: TestClient):
        """
        REQ-M1-004: 无配置时返回默认模板
        首次访问时应返回默认 System Prompt
        """
        response = client.get("/api/v1/system-prompt")
        assert response.status_code == 200
        
        data = response.json()
        assert "prompt_content" in data
        assert "char_count" in data
        assert data["is_active"] is True
    
    def test_get_default_prompt(self, client: TestClient):
        """获取默认模板"""
        response = client.get("/api/v1/system-prompt/default")
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_key"] == "default"
        assert data["prompt_content"] == DEFAULT_UI_CONFIG_PROMPT
        assert data["char_count"] == len(DEFAULT_UI_CONFIG_PROMPT)
    
    def test_update_prompt_success(self, client: TestClient, sample_system_prompt):
        """
        REQ-M1-006: 正常更新 Prompt
        更新内容应成功保存并返回
        """
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": sample_system_prompt}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_content"] == sample_system_prompt
        assert data["char_count"] == len(sample_system_prompt)
    
    def test_update_prompt_too_long(self, client: TestClient, long_system_prompt):
        """
        REQ-M1-008: 超出字符限制
        超过 10000 字符应返回错误
        可能在 Pydantic 层(422)或业务层(400)被拦截
        """
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": long_system_prompt}
        )
        # 400 或 422 都是合理的错误响应
        assert response.status_code in [400, 422]
        
        data = response.json()
        # 检查错误信息中包含相关内容
        data_str = str(data)
        # 可能是 CONTENT_TOO_LONG 或 max_length 验证错误
        assert "CONTENT_TOO_LONG" in data_str or "10000" in data_str or "max" in data_str.lower()
    
    def test_update_prompt_short_allowed(self, client: TestClient):
        """
        REQ-M1-012: 低于推荐字符数仍可保存
        少于 100 字符的内容应允许保存（仅提示建议）
        """
        short_content = "A" * 50
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": short_content}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_content"] == short_content
        assert data["char_count"] == 50
    
    def test_update_prompt_empty_allowed(self, client: TestClient):
        """
        允许保存空内容（虽然不推荐）
        """
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": ""}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_content"] == ""
        assert data["char_count"] == 0
    
    def test_reset_prompt(self, client: TestClient, sample_system_prompt):
        """
        REQ-M1-007: 恢复默认
        恢复默认后应返回默认模板内容
        """
        # 先更新为自定义内容
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": sample_system_prompt}
        )
        
        # 恢复默认
        response = client.post("/api/v1/system-prompt/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_content"] == DEFAULT_UI_CONFIG_PROMPT
        
        # 验证已恢复
        get_response = client.get("/api/v1/system-prompt")
        assert get_response.json()["prompt_content"] == DEFAULT_UI_CONFIG_PROMPT
    
    def test_get_stats(self, client: TestClient):
        """
        REQ-M1-005: 获取统计信息
        应返回正确的统计数据
        """
        response = client.get("/api/v1/system-prompt/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "current_length" in data
        assert "max_length" in data
        assert "recommended_min_length" in data
        assert "is_valid" in data
        assert data["max_length"] == 10000
        assert data["recommended_min_length"] == 100
    
    def test_get_stats_after_update(self, client: TestClient):
        """
        更新后统计信息应更新
        """
        content = "X" * 500
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": content}
        )
        
        response = client.get("/api/v1/system-prompt/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["current_length"] == 500
        assert data["is_valid"] is True
    
    def test_prompt_persistence(self, client: TestClient, sample_system_prompt):
        """
        REQ-M1-001: 配置持久化
        保存的配置应能正确读取
        """
        # 保存
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": sample_system_prompt}
        )
        
        # 读取
        response = client.get("/api/v1/system-prompt")
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_content"] == sample_system_prompt
    
    def test_prompt_key_is_global(self, client: TestClient):
        """
        REQ-M1-001: 全局唯一配置
        prompt_key 应为 global_ui_config
        """
        response = client.get("/api/v1/system-prompt")
        assert response.status_code == 200
        
        data = response.json()
        assert data["prompt_key"] == "global_ui_config"


class TestSystemPromptEdgeCases:
    """System Prompt 边界情况测试"""
    
    def test_update_with_special_characters(self, client: TestClient):
        """包含特殊字符的内容"""
        content = "测试内容\n包含换行\t制表符\r回车\n## Markdown\n```json\n{}\n```"
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": content}
        )
        assert response.status_code == 200
        assert response.json()["prompt_content"] == content
    
    def test_update_with_unicode(self, client: TestClient):
        """包含 Unicode 字符的内容"""
        content = "🎉 Emoji 测试 日本語 العربية 한국어"
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": content}
        )
        assert response.status_code == 200
        assert response.json()["prompt_content"] == content
    
    def test_max_length_exactly(self, client: TestClient):
        """正好 10000 字符应该允许"""
        content = "A" * 10000
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": content}
        )
        assert response.status_code == 200
        assert response.json()["char_count"] == 10000
    
    def test_update_preserves_timestamps(self, client: TestClient):
        """更新应保留创建时间，更新 updated_at"""
        # 首次更新
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": "First content"}
        )
        first_response = client.get("/api/v1/system-prompt")
        first_created_at = first_response.json()["created_at"]
        
        # 再次更新
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": "Second content"}
        )
        second_response = client.get("/api/v1/system-prompt")
        second_created_at = second_response.json()["created_at"]
        
        # created_at 应保持不变
        assert first_created_at == second_created_at

