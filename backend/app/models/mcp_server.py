# app/models/mcp_server.py
"""
MCP 服务器数据模型
对应任务: T6.1.1, T6.1.2
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
    server_url = Column(
        String(500), 
        nullable=False,
        comment="服务器 URL"
    )
    health_check_path = Column(
        String(100),
        default="/health",
        comment="健康检查路径 (REQ-M6-015)"
    )
    auth_type = Column(
        String(20),
        default="none",
        comment="认证类型: none, api_key, oauth"
    )
    auth_config = Column(
        JSON,
        comment="认证配置"
    )
    tools = Column(
        JSON, 
        default=[],
        comment="工具列表"
    )
    status = Column(
        String(20), 
        default="disabled",
        comment="状态: enabled, disabled, error"
    )
    last_check = Column(
        DateTime(timezone=True),
        comment="最后健康检查时间"
    )
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
        return f"<MCPServer(id={self.id}, name={self.name}, status={self.status})>"

