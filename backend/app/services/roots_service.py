# app/services/roots_service.py
"""
MCP Roots 管理服务
实现 MCP 规范中的 Roots 能力（工作区管理）

Roots 功能说明：
- Roots 是客户端向服务器声明的可操作目录范围
- 服务器应该只在这些根目录范围内进行文件操作
- 这是一种安全机制，限制服务器的文件访问权限

核心能力：
1. roots/list - 返回当前配置的根目录列表
2. roots/list_changed - 通知服务器根目录列表已变更
3. 路径验证 - 验证文件路径是否在允许的根目录范围内
"""

import asyncio
import os
import logging
from typing import Dict, Any, List, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, quote, unquote

logger = logging.getLogger(__name__)


class RootType(Enum):
    """根目录类型"""
    PROJECT = "project"      # 项目根目录
    WORKSPACE = "workspace"  # 工作区目录
    RESOURCE = "resource"    # 资源目录
    CUSTOM = "custom"        # 自定义目录


@dataclass
class Root:
    """
    根目录定义
    
    根据 MCP 规范，每个 Root 包含：
    - uri: 根目录的 URI（通常是 file:// 协议）
    - name: 可选的人类可读名称
    """
    uri: str
    name: Optional[str] = None
    root_type: RootType = RootType.CUSTOM
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def path(self) -> str:
        """从 URI 提取文件系统路径"""
        if self.uri.startswith("file://"):
            # 解析 file:// URI
            parsed = urlparse(self.uri)
            # 处理 URL 编码
            return unquote(parsed.path)
        return self.uri
    
    @classmethod
    def from_path(cls, path: str, name: Optional[str] = None, root_type: RootType = RootType.CUSTOM) -> "Root":
        """从文件系统路径创建 Root"""
        # 规范化路径
        normalized_path = os.path.abspath(os.path.expanduser(path))
        # 转换为 file:// URI，处理 URL 编码
        uri = f"file://{quote(normalized_path, safe='/:')}"
        return cls(uri=uri, name=name or os.path.basename(normalized_path), root_type=root_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 MCP 规范格式的字典"""
        result = {"uri": self.uri}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class RootsConfig:
    """Roots 配置"""
    roots: List[Root] = field(default_factory=list)
    # 是否启用严格模式（启用时，所有文件操作必须在根目录范围内）
    strict_mode: bool = True
    # 允许访问的额外路径模式（正则表达式）
    allowed_patterns: List[str] = field(default_factory=list)
    # 最后更新时间
    updated_at: datetime = field(default_factory=datetime.now)


class PathValidationResult(Enum):
    """路径验证结果"""
    ALLOWED = "allowed"                    # 路径在允许范围内
    DENIED = "denied"                      # 路径不在允许范围内
    INVALID_PATH = "invalid_path"          # 无效路径
    NO_ROOTS_CONFIGURED = "no_roots"       # 未配置根目录


@dataclass
class ValidationResult:
    """路径验证详细结果"""
    status: PathValidationResult
    path: str
    message: str
    matched_root: Optional[Root] = None


class RootsService:
    """
    MCP Roots 管理服务
    
    实现功能：
    1. 管理根目录列表
    2. 验证文件路径权限
    3. 支持 roots/list 和 roots/list_changed 通知
    """
    
    def __init__(self):
        # 每个 MCP 会话的 roots 配置
        self._session_roots: Dict[str, RootsConfig] = {}
        # 全局默认 roots（应用于所有会话）
        self._global_roots: List[Root] = []
        # roots/list_changed 通知回调
        self._change_callbacks: Dict[str, List[Callable[[str, List[Root]], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()
    
    # ==================== 全局 Roots 管理 ====================
    
    def add_global_root(
        self,
        path: str,
        name: Optional[str] = None,
        root_type: RootType = RootType.CUSTOM
    ) -> Root:
        """
        添加全局根目录
        
        全局根目录会应用于所有 MCP 会话
        """
        root = Root.from_path(path, name, root_type)
        
        # 检查是否已存在
        for existing in self._global_roots:
            if existing.uri == root.uri:
                logger.warning(f"根目录已存在: {root.uri}")
                return existing
        
        self._global_roots.append(root)
        logger.info(f"添加全局根目录: {root.name} -> {root.path}")
        return root
    
    def remove_global_root(self, uri_or_path: str) -> bool:
        """移除全局根目录"""
        # 尝试匹配 URI 或路径
        normalized_path = os.path.abspath(os.path.expanduser(uri_or_path))
        
        for i, root in enumerate(self._global_roots):
            if root.uri == uri_or_path or root.path == normalized_path:
                self._global_roots.pop(i)
                logger.info(f"移除全局根目录: {root.name}")
                return True
        return False
    
    def get_global_roots(self) -> List[Root]:
        """获取全局根目录列表"""
        return self._global_roots.copy()
    
    def clear_global_roots(self):
        """清空全局根目录"""
        self._global_roots.clear()
        logger.info("已清空所有全局根目录")
    
    # ==================== 会话级 Roots 管理 ====================
    
    async def configure_session_roots(
        self,
        session_id: str,
        roots: List[Dict[str, Any]],
        strict_mode: bool = True
    ) -> RootsConfig:
        """
        配置会话的根目录
        
        Args:
            session_id: 会话 ID（MCP 服务器标识）
            roots: 根目录配置列表，每个元素包含 path/uri 和可选的 name
            strict_mode: 是否启用严格模式
        """
        async with self._lock:
            root_list = []
            for root_config in roots:
                if "path" in root_config:
                    root = Root.from_path(
                        root_config["path"],
                        root_config.get("name"),
                        RootType(root_config.get("type", "custom"))
                    )
                elif "uri" in root_config:
                    root = Root(
                        uri=root_config["uri"],
                        name=root_config.get("name"),
                        root_type=RootType(root_config.get("type", "custom"))
                    )
                else:
                    continue
                root_list.append(root)
            
            config = RootsConfig(
                roots=root_list,
                strict_mode=strict_mode
            )
            self._session_roots[session_id] = config
            
            logger.info(f"配置会话 {session_id} 的根目录: {len(root_list)} 个")
            
            # 触发变更通知
            await self._notify_roots_changed(session_id)
            
            return config
    
    async def add_session_root(
        self,
        session_id: str,
        path: str,
        name: Optional[str] = None,
        root_type: RootType = RootType.CUSTOM
    ) -> Root:
        """向会话添加根目录"""
        async with self._lock:
            if session_id not in self._session_roots:
                self._session_roots[session_id] = RootsConfig()
            
            config = self._session_roots[session_id]
            root = Root.from_path(path, name, root_type)
            
            # 检查是否已存在
            for existing in config.roots:
                if existing.uri == root.uri:
                    logger.warning(f"会话 {session_id} 的根目录已存在: {root.uri}")
                    return existing
            
            config.roots.append(root)
            config.updated_at = datetime.now()
            
            logger.info(f"会话 {session_id} 添加根目录: {root.name}")
            
            # 触发变更通知
            await self._notify_roots_changed(session_id)
            
            return root
    
    async def remove_session_root(self, session_id: str, uri_or_path: str) -> bool:
        """从会话移除根目录"""
        async with self._lock:
            if session_id not in self._session_roots:
                return False
            
            config = self._session_roots[session_id]
            normalized_path = os.path.abspath(os.path.expanduser(uri_or_path))
            
            for i, root in enumerate(config.roots):
                if root.uri == uri_or_path or root.path == normalized_path:
                    config.roots.pop(i)
                    config.updated_at = datetime.now()
                    logger.info(f"会话 {session_id} 移除根目录: {root.name}")
                    
                    # 触发变更通知
                    await self._notify_roots_changed(session_id)
                    return True
            
            return False
    
    def get_session_roots(self, session_id: str) -> List[Root]:
        """获取会话的根目录列表（包含全局根目录）"""
        roots = self._global_roots.copy()
        
        if session_id in self._session_roots:
            config = self._session_roots[session_id]
            roots.extend(config.roots)
        
        return roots
    
    def get_session_config(self, session_id: str) -> Optional[RootsConfig]:
        """获取会话的 Roots 配置"""
        return self._session_roots.get(session_id)
    
    async def clear_session_roots(self, session_id: str):
        """清空会话的根目录配置"""
        async with self._lock:
            if session_id in self._session_roots:
                del self._session_roots[session_id]
                logger.info(f"清空会话 {session_id} 的根目录配置")
    
    # ==================== MCP 协议接口 ====================
    
    def get_roots_list(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取 MCP roots/list 响应格式的根目录列表
        
        返回格式符合 MCP 规范
        """
        roots = self.get_session_roots(session_id)
        return [root.to_dict() for root in roots]
    
    def get_client_capabilities(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取客户端的 roots 能力声明
        
        用于 MCP initialize 请求中的 capabilities.roots
        """
        # 判断是否启用了 roots 功能
        has_roots = bool(self._global_roots) or (session_id and session_id in self._session_roots)
        
        return {
            "roots": {
                "listChanged": True  # 支持 roots/list_changed 通知
            }
        } if has_roots else {}
    
    # ==================== 变更通知 ====================
    
    def register_change_callback(
        self,
        session_id: str,
        callback: Callable[[str, List[Root]], Awaitable[None]]
    ):
        """注册 roots/list_changed 回调"""
        if session_id not in self._change_callbacks:
            self._change_callbacks[session_id] = []
        self._change_callbacks[session_id].append(callback)
    
    def unregister_change_callback(
        self,
        session_id: str,
        callback: Callable[[str, List[Root]], Awaitable[None]]
    ):
        """注销 roots/list_changed 回调"""
        if session_id in self._change_callbacks:
            try:
                self._change_callbacks[session_id].remove(callback)
            except ValueError:
                pass
    
    async def _notify_roots_changed(self, session_id: str):
        """触发 roots/list_changed 通知"""
        roots = self.get_session_roots(session_id)
        
        if session_id in self._change_callbacks:
            for callback in self._change_callbacks[session_id]:
                try:
                    await callback(session_id, roots)
                except Exception as e:
                    logger.error(f"roots/list_changed 回调执行失败: {e}")
    
    # ==================== 路径验证 ====================
    
    def validate_path(
        self,
        session_id: str,
        file_path: str
    ) -> ValidationResult:
        """
        验证文件路径是否在允许的根目录范围内
        
        Args:
            session_id: 会话 ID
            file_path: 要验证的文件路径
            
        Returns:
            ValidationResult 包含验证状态和详细信息
        """
        # 规范化路径
        try:
            normalized_path = os.path.abspath(os.path.expanduser(file_path))
        except Exception as e:
            return ValidationResult(
                status=PathValidationResult.INVALID_PATH,
                path=file_path,
                message=f"无效路径: {str(e)}"
            )
        
        # 获取根目录列表
        roots = self.get_session_roots(session_id)
        
        # 如果没有配置根目录
        if not roots:
            config = self.get_session_config(session_id)
            if config and config.strict_mode:
                return ValidationResult(
                    status=PathValidationResult.NO_ROOTS_CONFIGURED,
                    path=normalized_path,
                    message="未配置根目录，严格模式下拒绝所有路径"
                )
            else:
                # 非严格模式且无根目录配置，允许所有路径
                return ValidationResult(
                    status=PathValidationResult.ALLOWED,
                    path=normalized_path,
                    message="未配置根目录，非严格模式允许访问"
                )
        
        # 检查路径是否在任一根目录下
        path_obj = Path(normalized_path)
        for root in roots:
            try:
                root_path = Path(root.path)
                # 检查路径是否是根目录或其子路径
                if path_obj == root_path or root_path in path_obj.parents:
                    return ValidationResult(
                        status=PathValidationResult.ALLOWED,
                        path=normalized_path,
                        message=f"路径在根目录 '{root.name}' 范围内",
                        matched_root=root
                    )
            except Exception:
                continue
        
        # 路径不在任何根目录范围内
        return ValidationResult(
            status=PathValidationResult.DENIED,
            path=normalized_path,
            message=f"路径不在任何允许的根目录范围内。配置的根目录: {[r.name for r in roots]}"
        )
    
    def is_path_allowed(self, session_id: str, file_path: str) -> bool:
        """简化的路径验证方法，返回布尔值"""
        result = self.validate_path(session_id, file_path)
        return result.status == PathValidationResult.ALLOWED
    
    # ==================== 工具调用集成 ====================
    
    def extract_paths_from_arguments(self, arguments: Dict[str, Any]) -> List[str]:
        """
        从工具调用参数中提取可能的文件路径
        
        支持常见的路径参数名称：
        - path, file, filepath, filename
        - uri, url
        - source, target, destination
        - input, output
        """
        path_keys = {
            "path", "file", "filepath", "filename", "file_path",
            "uri", "url",
            "source", "target", "destination", "dest",
            "input", "output",
            "directory", "dir", "folder",
            "location", "resource"
        }
        
        paths = []
        
        def extract_recursive(obj: Any, depth: int = 0):
            if depth > 5:  # 防止无限递归
                return
            
            if isinstance(obj, str):
                # 检查是否看起来像路径
                if "/" in obj or "\\" in obj or obj.startswith("~"):
                    paths.append(obj)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = key.lower()
                    if key_lower in path_keys:
                        if isinstance(value, str):
                            paths.append(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, str):
                                    paths.append(item)
                    else:
                        extract_recursive(value, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item, depth + 1)
        
        extract_recursive(arguments)
        return paths
    
    def validate_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> tuple[bool, List[ValidationResult]]:
        """
        验证工具调用中的所有路径参数
        
        Returns:
            (all_allowed, validation_results)
        """
        paths = self.extract_paths_from_arguments(arguments)
        
        if not paths:
            # 没有检测到路径参数，允许调用
            return True, []
        
        results = []
        all_allowed = True
        
        for path in paths:
            result = self.validate_path(session_id, path)
            results.append(result)
            if result.status != PathValidationResult.ALLOWED:
                all_allowed = False
        
        return all_allowed, results
    
    # ==================== 状态和信息 ====================
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Roots 服务状态"""
        return {
            "global_roots": [
                {
                    "uri": root.uri,
                    "name": root.name,
                    "path": root.path,
                    "type": root.root_type.value
                }
                for root in self._global_roots
            ],
            "sessions": {
                session_id: {
                    "roots_count": len(config.roots),
                    "strict_mode": config.strict_mode,
                    "roots": [
                        {
                            "uri": root.uri,
                            "name": root.name,
                            "path": root.path,
                            "type": root.root_type.value
                        }
                        for root in config.roots
                    ],
                    "updated_at": config.updated_at.isoformat()
                }
                for session_id, config in self._session_roots.items()
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        self._session_roots.clear()
        self._change_callbacks.clear()
        logger.info("Roots 服务已清理")


# 创建全局单例
roots_service = RootsService()
