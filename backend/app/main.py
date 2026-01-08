# app/main.py
"""
FastAPI 应用主入口
UI Config 智能配置系统
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import os
import logging

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler
)
from app.database import init_db, close_db

# 导入路由
from app.api.v1 import system_prompt, project, page_config, clarify, config_generator, mcp, mcp_test, mcp_context

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # 确保上传目录存在 (T0.2.5)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload directory ready: {settings.UPLOAD_DIR}")
    
    # 初始化数据库
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # 关闭时
    await close_db()
    logger.info("Application shutdown complete")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 VL 模型的 UI 配置智能生成系统",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# 配置 CORS (T0.2.4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器 (T0.2.2)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 挂载静态文件目录 (T0.2.5)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 注册 API 路由
app.include_router(system_prompt.router)
app.include_router(project.router)
app.include_router(page_config.router)
app.include_router(clarify.router)
app.include_router(config_generator.router)
app.include_router(mcp.router)
app.include_router(mcp_test.router)
app.include_router(mcp_context.router)


@app.get("/")
async def root():
    """根路径 - 健康检查"""
    return {
        "success": True,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

