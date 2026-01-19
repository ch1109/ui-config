# app/models/mcp_server.py
"""
MCP 服务器数据模型
对应任务: T6.1.1, T6.1.2

支持的传输类型：
- stdio: 本地进程通信
- http: HTTP REST API
- sse: Server-Sent Events（远程 MCP 服务器）
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class MCPServer(Base):
    """MCP 服务器配置表"""
    
    __tablename__ = "mcp_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    preset_key = Column(
        String(50),
        nullable=True,
        unique=True,
        comment="预置服务器键名（如 context7），自定义为空"
    )
    name = Column(
        String(100), 
        nullable=False,
        comment="服务器名称"
    )
    description = Column(
        Text,
        comment="服务器描述"
    )
    # 传输类型：http、stdio 或 sse
    transport = Column(
        String(20),
        default="http",
        comment="传输类型: http, stdio, sse"
    )
    
    # ========== HTTP/SSE 类型字段 ==========
    server_url = Column(
        String(500), 
        nullable=True,
        comment="服务器 URL（HTTP/SSE 类型）"
    )
    health_check_path = Column(
        String(100),
        default="/health",
        comment="健康检查路径（HTTP 类型）"
    )
    # SSE 特定端点
    sse_endpoint = Column(
        String(100),
        default="/sse",
        comment="SSE 事件流端点路径（SSE 类型）"
    )
    message_endpoint = Column(
        String(100),
        default="/message",
        comment="消息发送端点路径（SSE 类型）"
    )
    # SSE 重连配置
    auto_reconnect = Column(
        Boolean,
        default=True,
        comment="是否自动重连（SSE 类型）"
    )
    max_reconnect_attempts = Column(
        Integer,
        default=5,
        comment="最大重连次数（SSE 类型）"
    )
    
    # ========== STDIO 类型字段 ==========
    command = Column(
        String(200),
        nullable=True,
        comment="启动命令（STDIO 类型），如 npx, node"
    )
    args = Column(
        JSON,
        default=[],
        comment="命令参数（STDIO 类型），如 ['-y', 'wttr-mcp-server@latest']"
    )
    env = Column(
        JSON,
        default={},
        comment="环境变量（STDIO 类型），如 {'API_KEY': 'xxx'}"
    )
    
    # ========== 通用认证字段 ==========
    auth_type = Column(
        String(20),
        default="none",
        comment="认证类型: none, bearer, api_key, custom"
    )
    auth_config = Column(
        JSON,
        comment="认证配置，如 {'token': 'xxx', 'header_name': 'X-API-Key'}"
    )
    custom_headers = Column(
        JSON,
        default={},
        comment="自定义请求头（HTTP/SSE 类型）"
    )
    
    # ========== 工具和能力 ==========
    tools = Column(
        JSON, 
        default=[],
        comment="工具列表"
    )
    resources = Column(
        JSON,
        default=[],
        comment="资源列表"
    )
    prompts = Column(
        JSON,
        default=[],
        comment="提示模板列表"
    )
    server_capabilities = Column(
        JSON,
        default={},
        comment="服务器能力（从 initialize 响应获取）"
    )
    
    # ========== 状态字段 ==========
    status = Column(
        String(20), 
        default="disabled",
        comment="状态: enabled, disabled, error, connecting, connected"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    last_check = Column(
        DateTime(timezone=True),
        comment="最后健康检查时间"
    )
    last_connected = Column(
        DateTime(timezone=True),
        comment="最后成功连接时间"
    )
    
    # ========== 时间戳 ==========
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        onupdate=func.now(),
        comment="更新时间"
    )
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name={self.name}, transport={self.transport}, status={self.status})>"
    
    def is_sse(self) -> bool:
        """是否是 SSE 类型"""
        return self.transport == "sse"
    
    def is_stdio(self) -> bool:
        """是否是 STDIO 类型"""
        return self.transport == "stdio"
    
    def is_http(self) -> bool:
        """是否是 HTTP 类型"""
        return self.transport == "http"
    
    def get_sse_config(self) -> dict:
        """获取 SSE 连接配置"""
        return {
            "base_url": self.server_url,
            "sse_endpoint": self.sse_endpoint or "/sse",
            "message_endpoint": self.message_endpoint or "/message",
            "auth_token": self.auth_config.get("token") if self.auth_config else None,
            "auth_type": self.auth_type or "none",
            "custom_headers": self.custom_headers or {},
            "auto_reconnect": self.auto_reconnect if self.auto_reconnect is not None else True,
            "max_reconnect_attempts": self.max_reconnect_attempts or 5
        }

