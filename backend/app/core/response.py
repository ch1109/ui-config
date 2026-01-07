# app/core/response.py
"""
统一响应格式封装
对应任务: T0.2.3
"""

from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel


T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


def success_response(
    data: Any = None,
    message: str = "操作成功"
) -> dict:
    """
    成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        
    Returns:
        dict: 统一格式的成功响应
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "error": None
    }


def error_response(
    error: str,
    message: str,
    details: dict = None
) -> dict:
    """
    错误响应
    
    Args:
        error: 错误代码
        message: 错误消息
        details: 详细信息
        
    Returns:
        dict: 统一格式的错误响应
    """
    return {
        "success": False,
        "data": None,
        "message": message,
        "error": error,
        "details": details or {}
    }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    success: bool = True
    data: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


def paginated_response(
    items: list,
    total: int,
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    分页响应
    
    Args:
        items: 数据列表
        total: 总数
        page: 当前页码
        page_size: 每页数量
        
    Returns:
        dict: 统一格式的分页响应
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return {
        "success": True,
        "data": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

