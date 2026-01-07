# tests/test_mcp.py
"""
M6 - MCP 服务器管理测试
对应需求: REQ-M6-001 ~ REQ-M6-015
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.api.v1.mcp import PRESET_MCP_SERVERS


class TestMCPServerList:
    """MCP 服务器列表测试"""
    
    def test_list_mcp_servers_includes_preset(self, client: TestClient):
        """
        REQ-M6-001: Context7 预制配置可用
        列表应包含预制服务器
        """
        response = client.get("/api/v1/mcp")
        
        assert response.status_code == 200
        data = response.json()
        
        # 应该包含 Context7 预制服务器
        preset_names = [s["name"] for s in data if s["is_preset"]]
        assert "Context7" in preset_names
    
    def test_list_mcp_servers_structure(self, client: TestClient):
        """
        REQ-M6-004: 列表正确展示预制和自定义
        """
        response = client.get("/api/v1/mcp")
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证返回结构
        for server in data:
            assert "id" in server
            assert "name" in server
            assert "server_url" in server
            assert "status" in server
            assert "tools" in server
            assert "is_preset" in server
    
    def test_preset_server_default_disabled(self, client: TestClient):
        """
        预制服务器默认应为禁用状态
        """
        response = client.get("/api/v1/mcp")
        
        assert response.status_code == 200
        data = response.json()
        
        preset_servers = [s for s in data if s["is_preset"]]
        for server in preset_servers:
            # 如果没有手动启用，应该是 disabled
            assert server["status"] == "disabled"


class TestPresetServerToggle:
    """预制服务器开关测试"""
    
    def test_toggle_preset_enable(self, client: TestClient):
        """
        REQ-M6-005: 启用预制服务器
        """
        response = client.post(
            "/api/v1/mcp/context7/toggle",
            params={"enable": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "enabled"
    
    def test_toggle_preset_disable(self, client: TestClient):
        """
        REQ-M6-005: 禁用预制服务器
        """
        # 先启用
        client.post("/api/v1/mcp/context7/toggle", params={"enable": True})
        
        # 再禁用
        response = client.post(
            "/api/v1/mcp/context7/toggle",
            params={"enable": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "disabled"
    
    def test_toggle_nonexistent_preset(self, client: TestClient):
        """
        切换不存在的预制服务器应返回 404
        """
        response = client.post(
            "/api/v1/mcp/nonexistent/toggle",
            params={"enable": True}
        )
        
        assert response.status_code == 404


class TestMCPConfigUpload:
    """MCP 配置上传测试"""
    
    def test_upload_valid_json(self, client: TestClient, sample_mcp_config):
        """
        REQ-M6-006, REQ-M6-007: 上传有效 JSON 配置
        """
        config_json = json.dumps(sample_mcp_config)
        
        with patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock) as mock_test:
            mock_test.return_value = True
            
            response = client.post(
                "/api/v1/mcp/upload",
                files={"file": ("config.json", config_json.encode(), "application/json")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "id" in data
    
    def test_upload_invalid_json(self, client: TestClient):
        """
        REQ-M6-011: 非法 JSON 拒绝上传
        """
        invalid_json = "{ invalid json content"
        
        response = client.post(
            "/api/v1/mcp/upload",
            files={"file": ("config.json", invalid_json.encode(), "application/json")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "INVALID_JSON"
    
    def test_upload_too_large(self, client: TestClient):
        """
        REQ-M6-003: 文件大小限制 1MB
        """
        large_content = json.dumps({"data": "x" * (2 * 1024 * 1024)})  # > 1MB
        
        response = client.post(
            "/api/v1/mcp/upload",
            files={"file": ("config.json", large_content.encode(), "application/json")}
        )
        
        assert response.status_code == 400
    
    def test_upload_missing_server_url(self, client: TestClient):
        """
        上传缺少 server_url 字段的配置
        """
        config = {"name": "Test", "tools": ["search"]}  # 缺少 server_url
        
        response = client.post(
            "/api/v1/mcp/upload",
            files={"file": ("config.json", json.dumps(config).encode(), "application/json")}
        )
        
        assert response.status_code == 400
    
    def test_upload_missing_tools(self, client: TestClient):
        """
        上传缺少 tools 字段的配置
        """
        config = {"name": "Test", "server_url": "https://example.com"}  # 缺少 tools
        
        response = client.post(
            "/api/v1/mcp/upload",
            files={"file": ("config.json", json.dumps(config).encode(), "application/json")}
        )
        
        assert response.status_code == 400
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_upload_connectivity_warning(self, mock_test, client: TestClient, sample_mcp_config):
        """
        REQ-M6-012: 连通性测试失败时显示警告
        """
        mock_test.return_value = False  # 模拟连接失败
        
        config_json = json.dumps(sample_mcp_config)
        
        response = client.post(
            "/api/v1/mcp/upload",
            files={"file": ("config.json", config_json.encode(), "application/json")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connectivity"] is False
        assert "warning" in data


class TestMCPConfigAPI:
    """MCP 配置 API 测试"""
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_add_config_via_api(self, mock_test, client: TestClient, sample_mcp_config):
        """
        REQ-M6-008: 通过代码编辑器方式添加
        """
        mock_test.return_value = True
        
        response = client.post(
            "/api/v1/mcp/config",
            json=sample_mcp_config
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "id" in data
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_duplicate_server_warning(self, mock_test, client: TestClient, sample_mcp_config):
        """
        REQ-M6-013: 重复服务器提示覆盖
        """
        mock_test.return_value = True
        
        # 第一次添加
        client.post("/api/v1/mcp/config", json=sample_mcp_config)
        
        # 第二次添加相同 URL
        response = client.post("/api/v1/mcp/config", json=sample_mcp_config)
        
        assert response.status_code == 200
        data = response.json()
        assert data["warning"] == "duplicate"
        assert "existing_id" in data


class TestMCPServerCRUD:
    """MCP 服务器 CRUD 测试"""
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_update_custom_server(self, mock_test, client: TestClient, sample_mcp_config):
        """
        REQ-M6-009: 更新自定义服务器
        """
        mock_test.return_value = True
        
        # 创建服务器
        create_response = client.post("/api/v1/mcp/config", json=sample_mcp_config)
        server_id = create_response.json()["id"]
        
        # 更新服务器
        updated_config = sample_mcp_config.copy()
        updated_config["name"] = "Updated Name"
        
        response = client.put(
            f"/api/v1/mcp/{server_id}",
            json=updated_config
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_delete_custom_server(self, mock_test, client: TestClient, sample_mcp_config):
        """
        REQ-M6-010: 删除自定义服务器
        """
        mock_test.return_value = True
        
        # 创建服务器
        create_response = client.post("/api/v1/mcp/config", json=sample_mcp_config)
        server_id = create_response.json()["id"]
        
        # 删除服务器
        response = client.delete(f"/api/v1/mcp/{server_id}")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_delete_nonexistent_server(self, client: TestClient):
        """
        删除不存在的服务器返回 404
        """
        response = client.delete("/api/v1/mcp/9999")
        
        assert response.status_code == 404
    
    def test_cannot_delete_preset_server(self, client: TestClient):
        """
        不能删除预制服务器
        """
        # 先启用预制服务器（创建记录）
        client.post("/api/v1/mcp/context7/toggle", params={"enable": True})
        
        # 获取服务器 ID
        list_response = client.get("/api/v1/mcp")
        preset_server = next(s for s in list_response.json() if s["is_preset"])
        
        if preset_server["id"] != 0:  # 如果有实际的数据库记录
            response = client.delete(f"/api/v1/mcp/{preset_server['id']}")
            assert response.status_code == 400
    
    def test_cannot_update_preset_server(self, client: TestClient, sample_mcp_config):
        """
        不能修改预制服务器配置
        """
        # 先启用预制服务器（创建记录）
        client.post("/api/v1/mcp/context7/toggle", params={"enable": True})
        
        # 获取服务器 ID
        list_response = client.get("/api/v1/mcp")
        preset_server = next(s for s in list_response.json() if s["is_preset"])
        
        if preset_server["id"] != 0:
            response = client.put(
                f"/api/v1/mcp/{preset_server['id']}",
                json=sample_mcp_config
            )
            assert response.status_code == 400


class TestMCPConnectivityTest:
    """MCP 连通性测试"""
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_connectivity_test_success(self, mock_test, client: TestClient, sample_mcp_config):
        """
        连通性测试成功
        """
        mock_test.return_value = True
        
        # 创建服务器
        create_response = client.post("/api/v1/mcp/config", json=sample_mcp_config)
        server_id = create_response.json()["id"]
        
        # 测试连通性
        response = client.post(f"/api/v1/mcp/{server_id}/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connectivity"] is True
    
    @patch('app.api.v1.mcp.test_server_connectivity', new_callable=AsyncMock)
    def test_connectivity_test_failure(self, mock_test, client: TestClient, sample_mcp_config):
        """
        连通性测试失败
        """
        # 创建时成功，测试时失败
        mock_test.side_effect = [True, False]
        
        # 创建服务器
        create_response = client.post("/api/v1/mcp/config", json=sample_mcp_config)
        server_id = create_response.json()["id"]
        
        # 测试连通性
        response = client.post(f"/api/v1/mcp/{server_id}/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["connectivity"] is False
    
    def test_connectivity_test_nonexistent(self, client: TestClient):
        """
        测试不存在的服务器
        """
        response = client.post("/api/v1/mcp/9999/test")
        
        assert response.status_code == 404


class TestPresetMCPServers:
    """预制 MCP 服务器配置测试"""
    
    def test_context7_preset_config(self):
        """
        REQ-M6-001: Context7 预制配置正确
        """
        assert "context7" in PRESET_MCP_SERVERS
        
        context7 = PRESET_MCP_SERVERS["context7"]
        assert context7["name"] == "Context7"
        assert context7["server_url"] == "https://mcp.context7.io"
        assert "search" in context7["tools"]
        assert "retrieve" in context7["tools"]
        assert context7["is_preset"] is True

