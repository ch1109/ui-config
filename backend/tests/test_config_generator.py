# tests/test_config_generator.py
"""
M4 - JSON Config 生成测试
对应需求: REQ-M4-001 ~ REQ-M4-010
"""

import pytest
from fastapi.testclient import TestClient
from app.services.config_service import ConfigService, UI_CONFIG_SCHEMA
import jsonschema


class TestConfigGeneration:
    """配置生成测试"""
    
    def test_generate_config_missing_data(self, client: TestClient):
        """
        缺少配置数据应返回错误
        """
        response = client.post(
            "/api/v1/config/generate",
            json={}
        )
        
        assert response.status_code == 400
    
    def test_generate_config_with_page_data(self, client: TestClient, sample_page_config):
        """
        REQ-M4-003: 正确生成 JSON Config
        """
        response = client.post(
            "/api/v1/config/generate",
            json={"page_data": sample_page_config}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "config" in data
        assert "pages" in data["config"]
        assert sample_page_config["page_id"] in data["config"]["pages"]
    
    def test_generate_config_structure(self, client: TestClient, sample_page_config):
        """
        REQ-M4-001: JSON 符合 Schema 结构
        """
        response = client.post(
            "/api/v1/config/generate",
            json={"page_data": sample_page_config}
        )
        
        assert response.status_code == 200
        config = response.json()["config"]
        
        # 验证结构
        assert "pages" in config
        page_config = config["pages"][sample_page_config["page_id"]]
        assert "name" in page_config
        assert "zh-CN" in page_config["name"]
        assert "en" in page_config["name"]
        assert "description" in page_config
        assert "buttonList" in page_config
        assert "optionalActions" in page_config
    
    def test_generate_config_empty_button_list_error(self, client: TestClient):
        """
        REQ-M4-009: buttonList 至少 1 项
        空按钮列表应返回验证错误
        """
        page_data = {
            "page_id": "test_page",
            "name": {"zh-CN": "测试", "en": "Test"},
            "description": {"zh-CN": "", "en": ""},
            "button_list": []  # 空列表
        }
        
        response = client.post(
            "/api/v1/config/generate",
            json={"page_data": page_data}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["errors"] is not None
        assert any("buttonList" in e["field"] for e in data["errors"])
    
    def test_generate_config_missing_name_error(self, client: TestClient):
        """
        REQ-M4-008: 必填字段为空时显示提示
        """
        page_data = {
            "page_id": "test_page",
            "name": {"zh-CN": "", "en": ""},  # 空名称
            "description": {"zh-CN": "", "en": ""},
            "button_list": ["btn"]
        }
        
        response = client.post(
            "/api/v1/config/generate",
            json={"page_data": page_data}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert any("name" in e["field"] for e in data["errors"])
    
    def test_generate_config_optional_actions(self, client: TestClient):
        """
        REQ-M4-010: optionalActions 允许任意字符串
        """
        page_data = {
            "page_id": "test_page",
            "name": {"zh-CN": "测试", "en": "Test"},
            "description": {"zh-CN": "", "en": ""},
            "button_list": ["btn"],
            "optional_actions": ["custom_action_1", "任意中文操作", "123"]
        }
        
        response = client.post(
            "/api/v1/config/generate",
            json={"page_data": page_data}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config"]["pages"]["test_page"]["optionalActions"] == page_data["optional_actions"]


class TestConfigValidation:
    """配置验证测试"""
    
    def test_validate_valid_config(self, client: TestClient):
        """
        REQ-M4-007: 验证有效配置
        """
        valid_config = {
            "pages": {
                "test_page": {
                    "name": {"zh-CN": "测试", "en": "Test"},
                    "description": {"zh-CN": "描述", "en": "Desc"},
                    "buttonList": ["btn_1"],
                    "optionalActions": []
                }
            }
        }
        
        response = client.post(
            "/api/v1/config/validate",
            json=valid_config
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
    
    def test_validate_invalid_config_missing_pages(self, client: TestClient):
        """
        验证无效配置 - 缺少 pages
        """
        invalid_config = {}
        
        response = client.post(
            "/api/v1/config/validate",
            json=invalid_config
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
    
    def test_validate_invalid_config_missing_required_field(self, client: TestClient):
        """
        验证无效配置 - 缺少必填字段
        """
        invalid_config = {
            "pages": {
                "test_page": {
                    "name": {"zh-CN": "测试", "en": "Test"},
                    # 缺少 description 和 buttonList
                }
            }
        }
        
        response = client.post(
            "/api/v1/config/validate",
            json=invalid_config
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
    
    def test_validate_empty_button_list(self, client: TestClient):
        """
        验证空按钮列表
        """
        config = {
            "pages": {
                "test_page": {
                    "name": {"zh-CN": "测试", "en": "Test"},
                    "description": {"zh-CN": "", "en": ""},
                    "buttonList": [],  # 空列表
                    "optionalActions": []
                }
            }
        }
        
        response = client.post(
            "/api/v1/config/validate",
            json=config
        )
        
        assert response.status_code == 200
        data = response.json()
        # 根据 schema，minItems: 1 应该导致验证失败
        assert data["valid"] is False


class TestConfigSchema:
    """配置 Schema 测试"""
    
    def test_get_config_schema(self, client: TestClient):
        """
        获取 Schema 定义
        """
        response = client.get("/api/v1/config/schema")
        
        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert "pages" in data["schema"]["properties"]
    
    def test_schema_structure(self):
        """
        验证 Schema 结构正确
        """
        assert UI_CONFIG_SCHEMA["type"] == "object"
        assert "pages" in UI_CONFIG_SCHEMA["required"]
        
        pages_schema = UI_CONFIG_SCHEMA["properties"]["pages"]
        assert pages_schema["type"] == "object"
        
        # 验证页面配置的必填字段
        page_pattern = list(pages_schema["patternProperties"].values())[0]
        assert "name" in page_pattern["required"]
        assert "description" in page_pattern["required"]
        assert "buttonList" in page_pattern["required"]


class TestConfigService:
    """ConfigService 单元测试"""
    
    def test_build_config_basic(self):
        """
        测试基本配置构建
        """
        from unittest.mock import MagicMock
        
        db_mock = MagicMock()
        service = ConfigService(db_mock)
        
        page_data = {
            "page_id": "test",
            "name": {"zh-CN": "测试", "en": "Test"},
            "description": {"zh-CN": "描述", "en": "Desc"},
            "button_list": ["btn"],
            "optional_actions": ["action"]
        }
        
        config = service.build_config(page_data)
        
        assert "pages" in config
        assert "test" in config["pages"]
        assert config["pages"]["test"]["buttonList"] == ["btn"]
        assert config["pages"]["test"]["optionalActions"] == ["action"]
    
    def test_build_config_from_vl_result(self):
        """
        测试从 VL 解析结果构建配置
        """
        from unittest.mock import MagicMock
        
        db_mock = MagicMock()
        service = ConfigService(db_mock)
        
        # VL 解析结果格式
        page_data = {
            "page_id": "test",
            "page_name": {"zh-CN": "VL名称", "en": "VL Name"},
            "page_description": {"zh-CN": "VL描述", "en": "VL Desc"},
            "button_list": ["btn_vl"],
            "optional_actions": []
        }
        
        config = service.build_config(page_data)
        
        assert config["pages"]["test"]["name"]["zh-CN"] == "VL名称"
        assert config["pages"]["test"]["description"]["zh-CN"] == "VL描述"
    
    def test_validate_config_success(self):
        """
        测试配置验证成功
        """
        from unittest.mock import MagicMock
        
        db_mock = MagicMock()
        service = ConfigService(db_mock)
        
        valid_config = {
            "pages": {
                "test": {
                    "name": {"zh-CN": "名称", "en": "Name"},
                    "description": {"zh-CN": "描述", "en": "Desc"},
                    "buttonList": ["btn"],
                    "optionalActions": []
                }
            }
        }
        
        errors = service.validate_config(valid_config)
        
        assert errors == []
    
    def test_validate_config_empty_button_list(self):
        """
        测试空按钮列表验证
        """
        from unittest.mock import MagicMock
        
        db_mock = MagicMock()
        service = ConfigService(db_mock)
        
        config = {
            "pages": {
                "test": {
                    "name": {"zh-CN": "名称", "en": "Name"},
                    "description": {"zh-CN": "描述", "en": "Desc"},
                    "buttonList": [],
                    "optionalActions": []
                }
            }
        }
        
        errors = service.validate_config(config)
        
        assert len(errors) > 0
        assert any("buttonList" in e["field"] for e in errors)
    
    def test_validate_config_empty_name(self):
        """
        测试空名称验证
        """
        from unittest.mock import MagicMock
        
        db_mock = MagicMock()
        service = ConfigService(db_mock)
        
        config = {
            "pages": {
                "test": {
                    "name": {"zh-CN": "", "en": ""},
                    "description": {"zh-CN": "", "en": ""},
                    "buttonList": ["btn"],
                    "optionalActions": []
                }
            }
        }
        
        errors = service.validate_config(config)
        
        assert len(errors) > 0
        assert any("name" in e["field"] for e in errors)


class TestConfigSave:
    """配置保存测试"""
    
    def test_save_config(self, client: TestClient, sample_page_config):
        """
        保存配置
        """
        response = client.post(
            "/api/v1/config/save",
            json={"page_data": sample_page_config}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["page_id"] == sample_page_config["page_id"]
    
    def test_save_config_invalid_data(self, client: TestClient):
        """
        保存无效配置
        """
        invalid_data = {
            "page_id": "test",
            "name": {"zh-CN": "", "en": ""},
            "description": {"zh-CN": "", "en": ""},
            "button_list": []
        }
        
        response = client.post(
            "/api/v1/config/save",
            json={"page_data": invalid_data}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "errors" in data

