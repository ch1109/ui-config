# tests/test_roots_service.py
"""
MCP Roots 服务测试
测试工作区目录管理功能
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.roots_service import (
    RootsService,
    Root,
    RootType,
    RootsConfig,
    PathValidationResult,
    ValidationResult,
    roots_service
)


class TestRoot:
    """Root 数据类测试"""
    
    def test_from_path_creates_valid_root(self):
        """从路径创建 Root"""
        path = "/Users/test/project"
        root = Root.from_path(path, "测试项目", RootType.PROJECT)
        
        assert root.uri.startswith("file://")
        assert root.path == path
        assert root.name == "测试项目"
        assert root.root_type == RootType.PROJECT
    
    def test_from_path_with_tilde(self):
        """处理 ~ 路径"""
        home = os.path.expanduser("~")
        root = Root.from_path("~/Documents")
        
        assert root.path == os.path.join(home, "Documents")
    
    def test_from_path_normalizes_path(self):
        """路径规范化"""
        root = Root.from_path("/Users/test/../test/project")
        
        assert ".." not in root.path
        assert root.path == "/Users/test/project"
    
    def test_to_dict_returns_mcp_format(self):
        """转换为 MCP 格式"""
        root = Root.from_path("/test/path", "Test")
        result = root.to_dict()
        
        assert "uri" in result
        assert result["name"] == "Test"
    
    def test_to_dict_without_name(self):
        """无名称时只返回 uri"""
        root = Root(uri="file:///test/path")
        result = root.to_dict()
        
        assert "uri" in result
        assert "name" not in result


class TestRootsServiceGlobal:
    """全局 Roots 管理测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        # 清理
        service._global_roots.clear()
        service._session_roots.clear()
    
    def test_add_global_root(self, service):
        """添加全局根目录"""
        root = service.add_global_root("/test/path", "测试目录")
        
        assert len(service._global_roots) == 1
        assert service._global_roots[0].name == "测试目录"
    
    def test_add_duplicate_global_root(self, service):
        """添加重复的全局根目录返回已存在的"""
        root1 = service.add_global_root("/test/path", "名称1")
        root2 = service.add_global_root("/test/path", "名称2")
        
        assert len(service._global_roots) == 1
        assert root1.uri == root2.uri
    
    def test_remove_global_root_by_path(self, service):
        """通过路径移除全局根目录"""
        service.add_global_root("/test/path", "测试")
        
        result = service.remove_global_root("/test/path")
        
        assert result is True
        assert len(service._global_roots) == 0
    
    def test_remove_nonexistent_global_root(self, service):
        """移除不存在的全局根目录"""
        result = service.remove_global_root("/nonexistent")
        
        assert result is False
    
    def test_get_global_roots(self, service):
        """获取全局根目录列表"""
        service.add_global_root("/path1", "名称1")
        service.add_global_root("/path2", "名称2")
        
        roots = service.get_global_roots()
        
        assert len(roots) == 2
        # 返回副本，不影响原列表
        roots.clear()
        assert len(service._global_roots) == 2
    
    def test_clear_global_roots(self, service):
        """清空全局根目录"""
        service.add_global_root("/path1", "名称1")
        service.add_global_root("/path2", "名称2")
        
        service.clear_global_roots()
        
        assert len(service._global_roots) == 0


class TestRootsServiceSession:
    """会话级 Roots 管理测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    @pytest.mark.asyncio
    async def test_configure_session_roots(self, service):
        """配置会话根目录"""
        roots_config = [
            {"path": "/project/src", "name": "源代码"},
            {"path": "/project/docs", "name": "文档"}
        ]
        
        config = await service.configure_session_roots("test_session", roots_config)
        
        assert len(config.roots) == 2
        assert config.strict_mode is True
    
    @pytest.mark.asyncio
    async def test_add_session_root(self, service):
        """向会话添加根目录"""
        root = await service.add_session_root(
            "test_session", 
            "/test/path", 
            "测试目录"
        )
        
        assert root.name == "测试目录"
        assert "test_session" in service._session_roots
    
    @pytest.mark.asyncio
    async def test_remove_session_root(self, service):
        """从会话移除根目录"""
        await service.add_session_root("test_session", "/test/path", "测试")
        
        result = await service.remove_session_root("test_session", "/test/path")
        
        assert result is True
        assert len(service._session_roots["test_session"].roots) == 0
    
    def test_get_session_roots_includes_global(self, service):
        """获取会话根目录时包含全局根目录"""
        service.add_global_root("/global/path", "全局")
        
        # 不需要配置会话，直接获取
        roots = service.get_session_roots("any_session")
        
        assert len(roots) == 1
        assert roots[0].name == "全局"
    
    @pytest.mark.asyncio
    async def test_get_session_roots_combined(self, service):
        """获取会话根目录（全局+会话）"""
        service.add_global_root("/global/path", "全局")
        await service.add_session_root("test_session", "/session/path", "会话")
        
        roots = service.get_session_roots("test_session")
        
        assert len(roots) == 2
    
    @pytest.mark.asyncio
    async def test_clear_session_roots(self, service):
        """清空会话根目录"""
        await service.add_session_root("test_session", "/test/path", "测试")
        
        await service.clear_session_roots("test_session")
        
        assert "test_session" not in service._session_roots


class TestPathValidation:
    """路径验证测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    @pytest.mark.asyncio
    async def test_validate_path_allowed(self, service):
        """验证允许的路径"""
        await service.add_session_root("test", "/Users/project", "项目")
        
        result = service.validate_path("test", "/Users/project/src/main.py")
        
        assert result.status == PathValidationResult.ALLOWED
        assert result.matched_root is not None
    
    @pytest.mark.asyncio
    async def test_validate_path_denied(self, service):
        """验证拒绝的路径"""
        await service.add_session_root("test", "/Users/project", "项目")
        
        result = service.validate_path("test", "/etc/passwd")
        
        assert result.status == PathValidationResult.DENIED
    
    def test_validate_path_no_roots_strict_mode(self, service):
        """严格模式下无根目录配置"""
        # 配置严格模式但无根目录
        service._session_roots["test"] = RootsConfig(roots=[], strict_mode=True)
        
        result = service.validate_path("test", "/any/path")
        
        assert result.status == PathValidationResult.NO_ROOTS_CONFIGURED
    
    def test_validate_path_no_roots_non_strict(self, service):
        """非严格模式下无根目录配置允许所有路径"""
        service._session_roots["test"] = RootsConfig(roots=[], strict_mode=False)
        
        result = service.validate_path("test", "/any/path")
        
        assert result.status == PathValidationResult.ALLOWED
    
    def test_validate_path_invalid_path(self, service):
        """验证无效路径"""
        # 使用无效字符的路径
        result = service.validate_path("test", "\x00invalid")
        
        assert result.status == PathValidationResult.INVALID_PATH
    
    @pytest.mark.asyncio
    async def test_is_path_allowed_helper(self, service):
        """is_path_allowed 辅助方法"""
        await service.add_session_root("test", "/project", "项目")
        
        assert service.is_path_allowed("test", "/project/file.txt") is True
        assert service.is_path_allowed("test", "/other/file.txt") is False


class TestToolCallValidation:
    """工具调用验证测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    def test_extract_paths_from_arguments(self, service):
        """从工具参数中提取路径"""
        arguments = {
            "path": "/test/file.txt",
            "destination": "/output/result.json",
            "name": "test",
            "count": 10
        }
        
        paths = service.extract_paths_from_arguments(arguments)
        
        assert "/test/file.txt" in paths
        assert "/output/result.json" in paths
        assert "test" not in paths  # name 字段不是路径关键字
    
    def test_extract_paths_nested(self, service):
        """从嵌套参数中提取路径"""
        arguments = {
            "options": {
                "source": "/source/path",
                "target": "/target/path"
            }
        }
        
        paths = service.extract_paths_from_arguments(arguments)
        
        assert "/source/path" in paths
        assert "/target/path" in paths
    
    def test_extract_paths_from_list(self, service):
        """从列表参数中提取路径"""
        arguments = {
            "files": ["/path/a.txt", "/path/b.txt"]
        }
        
        paths = service.extract_paths_from_arguments(arguments)
        
        # file 是路径关键词但 files 不是，需要通过值判断
        # 值包含 / 会被识别为可能的路径
        assert len(paths) >= 2
    
    @pytest.mark.asyncio
    async def test_validate_tool_call_all_allowed(self, service):
        """验证工具调用 - 所有路径允许"""
        await service.add_session_root("test", "/project", "项目")
        
        arguments = {"path": "/project/src/main.py"}
        all_allowed, results = service.validate_tool_call("test", "read_file", arguments)
        
        assert all_allowed is True
    
    @pytest.mark.asyncio
    async def test_validate_tool_call_path_denied(self, service):
        """验证工具调用 - 路径被拒绝"""
        await service.add_session_root("test", "/project", "项目")
        
        arguments = {"path": "/etc/passwd"}
        all_allowed, results = service.validate_tool_call("test", "read_file", arguments)
        
        assert all_allowed is False
        assert len(results) == 1
        assert results[0].status == PathValidationResult.DENIED
    
    def test_validate_tool_call_no_paths(self, service):
        """验证工具调用 - 无路径参数"""
        arguments = {"query": "SELECT * FROM users", "limit": 10}
        all_allowed, results = service.validate_tool_call("test", "sql_query", arguments)
        
        assert all_allowed is True
        assert len(results) == 0


class TestMCPProtocol:
    """MCP 协议接口测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    @pytest.mark.asyncio
    async def test_get_roots_list(self, service):
        """获取 MCP roots/list 格式"""
        await service.add_session_root("test", "/project", "项目")
        
        roots_list = service.get_roots_list("test")
        
        assert len(roots_list) == 1
        assert "uri" in roots_list[0]
        assert roots_list[0]["name"] == "项目"
    
    def test_get_client_capabilities_with_roots(self, service):
        """有根目录时返回 roots 能力"""
        service.add_global_root("/test", "测试")
        
        capabilities = service.get_client_capabilities()
        
        assert "roots" in capabilities
        assert capabilities["roots"]["listChanged"] is True
    
    def test_get_client_capabilities_without_roots(self, service):
        """无根目录时不返回 roots 能力"""
        capabilities = service.get_client_capabilities()
        
        assert capabilities == {}


class TestChangeNotification:
    """变更通知测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
        service._change_callbacks.clear()
    
    @pytest.mark.asyncio
    async def test_register_change_callback(self, service):
        """注册变更回调"""
        callback_called = []
        
        async def callback(session_id, roots):
            callback_called.append((session_id, len(roots)))
        
        service.register_change_callback("test", callback)
        
        # 添加根目录应触发回调
        await service.add_session_root("test", "/path", "测试")
        
        assert len(callback_called) == 1
        assert callback_called[0][0] == "test"
    
    @pytest.mark.asyncio
    async def test_unregister_change_callback(self, service):
        """注销变更回调"""
        callback_called = []
        
        async def callback(session_id, roots):
            callback_called.append(session_id)
        
        service.register_change_callback("test", callback)
        service.unregister_change_callback("test", callback)
        
        await service.add_session_root("test", "/path", "测试")
        
        # 回调不应被调用
        assert len(callback_called) == 0


class TestServiceStatus:
    """服务状态测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    @pytest.mark.asyncio
    async def test_get_status(self, service):
        """获取服务状态"""
        service.add_global_root("/global", "全局")
        await service.add_session_root("session1", "/project", "项目")
        
        status = service.get_status()
        
        assert len(status["global_roots"]) == 1
        assert "session1" in status["sessions"]
        assert status["sessions"]["session1"]["roots_count"] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        """清理服务"""
        service.add_global_root("/global", "全局")
        await service.add_session_root("session1", "/project", "项目")
        
        await service.cleanup()
        
        assert len(service._session_roots) == 0
        assert len(service._change_callbacks) == 0
        # 注意：全局根目录不被 cleanup 清理


class TestIntegrationScenarios:
    """集成场景测试"""
    
    @pytest.fixture
    def service(self):
        """创建干净的服务实例"""
        service = RootsService()
        yield service
        service._global_roots.clear()
        service._session_roots.clear()
    
    @pytest.mark.asyncio
    async def test_file_server_scenario(self, service):
        """文件服务器场景：只允许访问指定目录"""
        # 配置工作区
        await service.configure_session_roots("file_server", [
            {"path": "/workspace/project", "name": "项目目录"},
            {"path": "/workspace/uploads", "name": "上传目录"}
        ])
        
        # 允许的操作
        assert service.is_path_allowed("file_server", "/workspace/project/src/main.py")
        assert service.is_path_allowed("file_server", "/workspace/uploads/image.png")
        
        # 拒绝的操作
        assert not service.is_path_allowed("file_server", "/etc/passwd")
        assert not service.is_path_allowed("file_server", "/workspace/secrets/key.pem")
    
    @pytest.mark.asyncio
    async def test_multi_server_isolation(self, service):
        """多服务器隔离场景"""
        # 服务器 A 只能访问 /project_a
        await service.configure_session_roots("server_a", [
            {"path": "/project_a", "name": "项目A"}
        ])
        
        # 服务器 B 只能访问 /project_b
        await service.configure_session_roots("server_b", [
            {"path": "/project_b", "name": "项目B"}
        ])
        
        # 验证隔离
        assert service.is_path_allowed("server_a", "/project_a/file.txt")
        assert not service.is_path_allowed("server_a", "/project_b/file.txt")
        
        assert service.is_path_allowed("server_b", "/project_b/file.txt")
        assert not service.is_path_allowed("server_b", "/project_a/file.txt")
    
    @pytest.mark.asyncio
    async def test_global_plus_session_roots(self, service):
        """全局+会话根目录组合场景"""
        # 全局共享目录
        service.add_global_root("/shared/libs", "共享库")
        
        # 会话特定目录
        await service.add_session_root("server_x", "/project_x", "项目X")
        
        # server_x 可以访问两者
        assert service.is_path_allowed("server_x", "/shared/libs/utils.py")
        assert service.is_path_allowed("server_x", "/project_x/main.py")
        
        # 其他会话只能访问全局
        assert service.is_path_allowed("server_y", "/shared/libs/utils.py")
        # server_y 无配置，无严格模式，应允许所有
        # （因为 server_y 没有自己的 RootsConfig）
