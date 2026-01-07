# app/models/project.py
"""
项目数据模型
用于管理页面配置的分组
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    """项目表 - 用于对页面配置进行分组管理"""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100), 
        nullable=False,
        comment="项目名称"
    )
    description = Column(
        Text,
        comment="项目描述"
    )
    color = Column(
        String(20),
        default="#6366f1",
        comment="项目标识颜色 (用于前端展示)"
    )
    icon = Column(
        String(50),
        default="folder",
        comment="项目图标标识"
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
    
    # 关联的页面配置
    pages = relationship("PageConfig", back_populates="project", lazy="dynamic")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name})>"

