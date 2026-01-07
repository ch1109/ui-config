# app/core/exceptions.py
"""
统一异常处理
对应任务: T0.2.2
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用自定义异常基类"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ContentTooLongError(AppException):
    """内容超长错误 (REQ-M1-008)"""
    
    def __init__(self, max_length: int, current_length: int):
        super().__init__(
            error_code="CONTENT_TOO_LONG",
            message="已达到最大字符限制",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "max_length": max_length,
                "current_length": current_length
            }
        )


class InvalidFileTypeError(AppException):
    """文件类型错误 (REQ-M2-010)"""
    
    def __init__(self, allowed_types: list):
        super().__init__(
            error_code="INVALID_FILE_TYPE",
            message="仅支持 PNG、JPG 格式的图片",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"allowed_types": allowed_types}
        )


class FileTooLargeError(AppException):
    """文件过大错误 (REQ-M2-011)"""
    
    def __init__(self, max_size_mb: int, actual_size_mb: float):
        super().__init__(
            error_code="FILE_TOO_LARGE",
            message=f"图片大小不能超过 {max_size_mb}MB",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "max_size_mb": max_size_mb,
                "actual_size_mb": actual_size_mb
            }
        )


class ImageRequiredError(AppException):
    """缺少图片错误 (REQ-M2-014)"""
    
    def __init__(self):
        super().__init__(
            error_code="IMAGE_REQUIRED",
            message="请先上传页面截图",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class ParseTimeoutError(AppException):
    """解析超时错误 (REQ-M2-012)"""
    
    def __init__(self):
        super().__init__(
            error_code="PARSE_TIMEOUT",
            message="解析超时，请重试或尝试上传更清晰的截图",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )


class ClarifyTimeoutError(AppException):
    """澄清超时错误 (REQ-M3-010)"""
    
    def __init__(self, retried: bool = False):
        super().__init__(
            error_code="CLARIFY_TIMEOUT",
            message="请手动完善配置或稍后重试" if retried else "AI 响应超时，正在重试...",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"retry": not retried}
        )


class SessionNotFoundError(AppException):
    """会话不存在错误"""
    
    def __init__(self, session_id: str):
        super().__init__(
            error_code="SESSION_NOT_FOUND",
            message="解析会话不存在",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id}
        )


class SaveFailedError(AppException):
    """保存失败错误 (REQ-M1-009)"""
    
    def __init__(self):
        super().__init__(
            error_code="SAVE_FAILED",
            message="保存失败，请检查网络后重试",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"retry": True}
        )


class InvalidJsonError(AppException):
    """无效 JSON 格式错误 (REQ-M6-011)"""
    
    def __init__(self):
        super().__init__(
            error_code="INVALID_JSON",
            message="文件格式错误，请上传有效的 JSON 文件",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class SSRFProtectionError(AppException):
    """SSRF 防护错误 (REQ-M2-016)"""
    
    def __init__(self):
        super().__init__(
            error_code="SSRF_BLOCKED",
            message="禁止访问内网/本地/保留地址",
            status_code=status.HTTP_403_FORBIDDEN
        )


# 异常处理器
async def app_exception_handler(request: Request, exc: AppException):
    """统一处理应用异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "请求参数验证失败",
            "details": {"errors": errors}
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP_ERROR",
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": exc.detail if isinstance(exc.detail, dict) else {}
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "details": {}
        }
    )

