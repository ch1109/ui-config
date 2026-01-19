# app/main.py
"""
FastAPI 应用主入口
UI Config 智能配置系统
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pathlib import Path
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
from app.api.v1 import system_prompt, project, page_config, clarify, config_generator, mcp, mcp_test, mcp_context, mcp_host

# 导入 Host 相关服务
from app.services.human_in_loop import human_in_loop_service
from app.services.react_engine import react_engine
from app.services.sse_mcp_client import sse_mcp_client
from app.services.stdio_mcp_manager import stdio_mcp_manager

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
    
    # 启动 Human-in-the-Loop 服务
    await human_in_loop_service.start()
    logger.info("Human-in-the-Loop service started")
    
    yield
    
    # 关闭时
    # 清理 Host 相关服务
    await human_in_loop_service.stop()
    await react_engine.cleanup()
    await sse_mcp_client.cleanup()
    await stdio_mcp_manager.cleanup()
    logger.info("MCP Host services cleaned up")
    
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
app.include_router(mcp_host.router)  # MCP Host 完整功能


@app.get("/")
async def root():
    """根路径 - 前端入口或健康检查"""
    if FRONTEND_DIST_DIR.exists():
        index_path = FRONTEND_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
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


# ==================== 前端静态文件服务 ====================
# 获取前端 dist 目录路径（从后端 main.py 向上两级到 backend，再向上到项目根目录）
_backend_dir = Path(__file__).parent.parent  # backend/app -> backend
_project_root = _backend_dir.parent  # backend -> UI config
FRONTEND_DIST_DIR = _project_root / "frontend" / "dist"
logger.info(f"Looking for frontend at: {FRONTEND_DIST_DIR}")

if FRONTEND_DIST_DIR.exists():
    # 挂载前端静态资源（assets 目录）
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="frontend_assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """
        SPA 前端路由回退
        所有未匹配的路由都返回 index.html，由前端路由处理
        """
        # 如果请求的是 API 路径，返回 404
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # 检查是否是静态文件请求
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # 其他所有请求返回 index.html（SPA 路由）
        index_path = FRONTEND_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Frontend not found")
    
    logger.info(f"Frontend served from: {FRONTEND_DIST_DIR}")
else:
    logger.warning(f"Frontend dist directory not found: {FRONTEND_DIST_DIR}")

