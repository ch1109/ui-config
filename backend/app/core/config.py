# app/core/config.py
"""
应用配置模块
支持从环境变量加载配置
"""

from pydantic_settings import BaseSettings
from typing import Optional, Literal
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用信息
    APP_NAME: str = "UI Config 智能配置系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 数据库配置 (SQLite 开发环境)
    DATABASE_URL: str = "sqlite+aiosqlite:///./ui_config.db"
    
    # ============================================
    # VL 模型配置
    # 支持的模型: glm-4v, qwen-vl-max, qwen-vl-plus
    # ============================================
    
    # 当前使用的 VL 模型提供商: "zhipu" (智谱 GLM-4V) 或 "dashscope" (阿里 Qwen)
    VL_PROVIDER: str = "zhipu"
    
    # 智谱 GLM-4V 配置 (默认)
    ZHIPU_API_KEY: Optional[str] = None
    ZHIPU_MODEL_NAME: str = "glm-4.6v"  # GLM-4.6V 模型
    ZHIPU_API_ENDPOINT: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    # 阿里云 DashScope Qwen-VL 配置
    DASHSCOPE_API_KEY: Optional[str] = None
    DASHSCOPE_MODEL_NAME: str = "qwen-vl-max"  # qwen-vl-max, qwen-vl-plus
    DASHSCOPE_API_ENDPOINT: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    # 通用 VL 配置
    VL_TIMEOUT: float = 60.0  # 超时时间
    
    # 兼容旧配置 (deprecated, 保留向后兼容)
    VL_MODEL_ENDPOINT: str = "http://localhost:8080"
    VL_API_KEY: Optional[str] = None
    VL_MODEL_NAME: str = "Qwen3-VL-8B-Instruct"
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_TYPES: list = [".png", ".jpg", ".jpeg"]
    
    # CORS 配置
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
    
    # 澄清对话配置
    CLARIFY_CONFIDENCE_THRESHOLD: float = 0.85
    CLARIFY_MAX_ROUNDS: int = 5
    CLARIFY_TIMEOUT: float = 15.0
    
    # 临时文件清理
    TEMP_FILE_EXPIRE_HOURS: int = 24
    
    class Config:
        env_file = "API.env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()

