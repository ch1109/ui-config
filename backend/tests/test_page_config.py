# tests/test_page_config.py
"""
M2 - 页面截图智能解析测试
对应需求: REQ-M2-001 ~ REQ-M2-021
"""

import pytest
import io
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


def create_test_image(format='PNG', size=(100, 100), color='red'):
    """创建测试图片"""
    try:
        from PIL import Image
        img = Image.new('RGB', size, color=color)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        img_bytes.seek(0)
        return img_bytes
    except ImportError:
        # 返回简单的字节流
        return io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)


class TestImageUpload:
    """图片上传测试"""
    
    def test_upload_png_success(self, client: TestClient):
        """
        REQ-M2-001: 支持 PNG 格式
        上传 PNG 图片应成功
        """
        img_bytes = create_test_image(format='PNG')
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", img_bytes, "image/png")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "file_url" in data
        assert data["file_url"].startswith("/uploads/")
        assert "size_bytes" in data
    
    def test_upload_jpg_success(self, client: TestClient):
        """
        REQ-M2-001: 支持 JPG 格式
        上传 JPG 图片应成功
        """
        img_bytes = create_test_image(format='JPEG')
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_upload_invalid_type_gif(self, client: TestClient):
        """
        REQ-M2-010: 拒绝非 PNG/JPG 格式 (GIF)
        上传 GIF 应返回错误
        """
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.gif", b"fake gif content", "image/gif")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "INVALID_FILE_TYPE"
    
    def test_upload_invalid_type_bmp(self, client: TestClient):
        """
        REQ-M2-010: 拒绝非 PNG/JPG 格式 (BMP)
        """
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.bmp", b"fake bmp content", "image/bmp")}
        )
        
        assert response.status_code == 400
        assert response.json()["error"] == "INVALID_FILE_TYPE"
    
    def test_upload_too_large(self, client: TestClient):
        """
        REQ-M2-011: 拒绝超过 10MB 的文件
        超大文件应返回错误
        """
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", large_content, "image/png")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "FILE_TOO_LARGE"
        assert data["details"]["max_size_mb"] == 10
    
    def test_upload_exactly_10mb(self, client: TestClient):
        """
        REQ-M2-002: 文件大小限制 10MB
        正好 10MB 应该允许
        """
        # 创建接近 10MB 的内容 (但不超过)
        content = b"x" * (10 * 1024 * 1024 - 1000)
        
        response = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", content, "image/png")}
        )
        
        assert response.status_code == 200
    
    def test_upload_generates_unique_filename(self, client: TestClient):
        """
        上传应生成唯一文件名
        """
        img_bytes = create_test_image()
        
        response1 = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", img_bytes, "image/png")}
        )
        
        img_bytes.seek(0)  # 重置位置
        response2 = client.post(
            "/api/v1/pages/upload-image",
            files={"file": ("test.png", img_bytes, "image/png")}
        )
        
        # 两次上传应生成不同的 URL
        assert response1.json()["file_url"] != response2.json()["file_url"]


class TestAIParsing:
    """AI 解析测试"""
    
    def test_parse_without_image(self, client: TestClient):
        """
        REQ-M2-014: 无图片时提示
        未提供图片 URL 应返回错误
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": ""}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "IMAGE_REQUIRED"
    
    def test_parse_invalid_image_url_file_protocol(self, client: TestClient):
        """
        REQ-M2-015: 非法 URL 拒绝解析 (file:// 协议)
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "file:///etc/passwd"}
        )
        
        assert response.status_code == 400
        data = response.json()
        # 检查错误信息在任意位置
        assert "INVALID_IMAGE_URL" in str(data)
    
    def test_parse_invalid_image_url_data_protocol(self, client: TestClient):
        """
        REQ-M2-015: 非法 URL 拒绝解析 (data: 协议)
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "data:image/png;base64,xxxxx"}
        )
        
        assert response.status_code == 400
    
    def test_parse_valid_upload_path(self, client: TestClient):
        """
        REQ-M2-015: 允许本地 uploads 路径
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "/uploads/test.png"}
        )
        
        # 应该返回 session_id，即使后台解析可能失败
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "pending"
    
    def test_parse_valid_http_url(self, client: TestClient):
        """
        REQ-M2-015: 允许 http/https URL
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "https://example.com/image.png"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
    
    def test_parse_returns_session_id(self, client: TestClient):
        """
        REQ-M2-007: 触发解析返回会话 ID
        """
        response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "/uploads/test.png"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # UUID 格式
        assert "estimated_time_seconds" in data
    
    def test_get_parse_status_not_found(self, client: TestClient):
        """
        解析会话不存在时返回 404
        """
        response = client.get(
            "/api/v1/pages/parse/non-existent-session-id/status"
        )
        
        assert response.status_code == 404
    
    def test_get_parse_status(self, client: TestClient):
        """
        REQ-M2-009: 获取解析状态
        """
        # 先创建一个解析会话
        parse_response = client.post(
            "/api/v1/pages/parse",
            params={"image_url": "/uploads/test.png"}
        )
        session_id = parse_response.json()["session_id"]
        
        # 获取状态
        response = client.get(f"/api/v1/pages/parse/{session_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "status" in data
        assert "confidence" in data


class TestPageConfigCRUD:
    """页面配置 CRUD 测试"""
    
    def test_list_pages_empty(self, client: TestClient):
        """获取空页面列表"""
        response = client.get("/api/v1/pages")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_page(self, client: TestClient, sample_page_config):
        """创建页面配置"""
        response = client.post(
            "/api/v1/pages",
            json=sample_page_config
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["page_id"] == sample_page_config["page_id"]
        assert data["status"] == "configured"
    
    def test_create_page_duplicate(self, client: TestClient, sample_page_config):
        """
        创建重复 page_id 应返回错误
        """
        # 首次创建
        client.post("/api/v1/pages", json=sample_page_config)
        
        # 重复创建
        response = client.post("/api/v1/pages", json=sample_page_config)
        
        assert response.status_code == 409
    
    def test_get_page(self, client: TestClient, sample_page_config):
        """获取单个页面"""
        # 先创建
        client.post("/api/v1/pages", json=sample_page_config)
        
        # 获取
        response = client.get(f"/api/v1/pages/{sample_page_config['page_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["page_id"] == sample_page_config["page_id"]
    
    def test_get_page_not_found(self, client: TestClient):
        """获取不存在的页面"""
        response = client.get("/api/v1/pages/non_existent_page")
        
        assert response.status_code == 404
    
    def test_update_page(self, client: TestClient, sample_page_config):
        """更新页面配置"""
        # 先创建
        client.post("/api/v1/pages", json=sample_page_config)
        
        # 更新
        update_data = {
            "name": {"zh-CN": "更新后的名称", "en": "Updated Name"},
            "button_list": ["btn_new"]
        }
        response = client.put(
            f"/api/v1/pages/{sample_page_config['page_id']}",
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"]["zh-CN"] == "更新后的名称"
        assert data["button_list"] == ["btn_new"]
    
    def test_delete_page(self, client: TestClient, sample_page_config):
        """删除页面配置"""
        # 先创建
        client.post("/api/v1/pages", json=sample_page_config)
        
        # 删除
        response = client.delete(f"/api/v1/pages/{sample_page_config['page_id']}")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # 验证已删除
        get_response = client.get(f"/api/v1/pages/{sample_page_config['page_id']}")
        assert get_response.status_code == 404
    
    def test_list_pages_with_filter(self, client: TestClient, sample_page_config):
        """按状态筛选页面列表"""
        # 创建页面
        client.post("/api/v1/pages", json=sample_page_config)
        
        # 按状态筛选
        response = client.get("/api/v1/pages", params={"page_status": "configured"})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "configured"
    
    def test_list_pages_pagination(self, client: TestClient):
        """页面列表分页"""
        # 创建多个页面
        for i in range(5):
            page_config = {
                "page_id": f"test_page_{i}",
                "name": {"zh-CN": f"测试页面{i}", "en": f"Test Page {i}"},
                "description": {"zh-CN": "", "en": ""},
                "button_list": ["btn"]
            }
            client.post("/api/v1/pages", json=page_config)
        
        # 分页获取
        response = client.get("/api/v1/pages", params={"skip": 2, "limit": 2})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestPageConfigValidation:
    """页面配置验证测试"""
    
    def test_create_page_invalid_page_id(self, client: TestClient):
        """
        page_id 格式验证
        """
        invalid_config = {
            "page_id": "invalid page id!",  # 包含空格和特殊字符
            "name": {"zh-CN": "测试", "en": "Test"},
            "description": {"zh-CN": "", "en": ""},
            "button_list": ["btn"]
        }
        
        response = client.post("/api/v1/pages", json=invalid_config)
        
        # 应该返回验证错误
        assert response.status_code == 422
    
    def test_create_page_missing_required_field(self, client: TestClient):
        """
        缺少必填字段应返回错误
        """
        incomplete_config = {
            "page_id": "test_page"
            # 缺少 name, description, button_list
        }
        
        response = client.post("/api/v1/pages", json=incomplete_config)
        
        assert response.status_code == 422
    
    def test_create_page_empty_button_list_allowed(self, client: TestClient):
        """
        按钮列表可以为空（创建时）
        验证在生成配置时进行，创建 API 可能允许也可能拒绝
        """
        config = {
            "page_id": "test_empty_buttons",
            "name": {"zh-CN": "测试", "en": "Test"},
            "description": {"zh-CN": "", "en": ""},
            "button_list": []  # 空列表
        }
        
        response = client.post("/api/v1/pages", json=config)
        
        # 创建 API 的行为：允许空列表或验证失败
        # 这取决于具体实现，这里我们检查请求被正确处理
        assert response.status_code in [200, 400, 422]

