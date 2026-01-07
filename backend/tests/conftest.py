# tests/conftest.py
"""
测试配置和 fixtures
统一配置测试环境和数据库
"""

import pytest
import asyncio
import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import io

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.config import settings


# 使用内存数据库进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def override_get_db(test_db_session):
    """覆盖数据库依赖注入"""
    async def _override_get_db():
        yield test_db_session
    
    return _override_get_db


@pytest.fixture(scope="function")
def client(override_get_db) -> TestClient:
    """创建测试客户端"""
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """创建异步测试客户端"""
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


# ============ 测试数据 fixtures ============

@pytest.fixture
def sample_system_prompt():
    """示例 System Prompt"""
    return "你是一个专业的 UI 页面分析助手。" * 10


@pytest.fixture
def long_system_prompt():
    """超长 System Prompt (超过 10000 字符)"""
    return "A" * 10001


@pytest.fixture
def sample_page_config():
    """示例页面配置"""
    return {
        "page_id": "test_page",
        "name": {"zh-CN": "测试页面", "en": "Test Page"},
        "description": {"zh-CN": "这是一个测试页面", "en": "This is a test page"},
        "button_list": ["btn_submit", "btn_cancel"],
        "optional_actions": ["chat", "help"],
        "ai_context": {
            "behavior_rules": "友好回答",
            "page_goal": "完成测试"
        }
    }


@pytest.fixture
def sample_parse_result():
    """示例 VL 解析结果"""
    return {
        "page_name": {"zh-CN": "登录页面", "en": "Login Page"},
        "page_description": {"zh-CN": "用户登录页面", "en": "User login page"},
        "elements": [
            {
                "element_id": "input_username",
                "element_type": "input",
                "label": "用户名",
                "inferred_intent": "输入用户名",
                "confidence": 0.95
            },
            {
                "element_id": "btn_login",
                "element_type": "button",
                "label": "登录",
                "inferred_intent": "提交登录表单",
                "confidence": 0.98
            }
        ],
        "button_list": ["btn_login", "btn_register"],
        "optional_actions": ["forgot_password"],
        "ai_context": {
            "behavior_rules": "引导用户登录",
            "page_goal": "完成用户认证"
        },
        "overall_confidence": 0.92,
        "clarification_needed": False,
        "clarification_questions": []
    }


@pytest.fixture
def sample_parse_result_needs_clarify():
    """需要澄清的 VL 解析结果"""
    return {
        "page_name": {"zh-CN": "未知页面", "en": "Unknown Page"},
        "page_description": {"zh-CN": "", "en": ""},
        "elements": [],
        "button_list": ["btn_1"],
        "optional_actions": [],
        "ai_context": {},
        "overall_confidence": 0.65,
        "clarification_needed": True,
        "clarification_questions": [
            {
                "question_id": "q1",
                "question_text": "这个按钮的用途是什么？",
                "context": "button_list",
                "options": ["提交", "取消", "其他"]
            }
        ]
    }


@pytest.fixture
def mock_vl_service():
    """Mock VL 模型服务"""
    with patch("app.services.vl_model_service.VLModelService") as mock:
        service_instance = MagicMock()
        mock.return_value = service_instance
        yield service_instance


@pytest.fixture
def test_image_bytes():
    """创建测试图片字节"""
    # 创建一个简单的 PNG 图片
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return img_bytes.read()
    except ImportError:
        # 如果没有 PIL，使用简单的字节
        return b'\x89PNG\r\n\x1a\n' + b'\x00' * 100


@pytest.fixture
def sample_mcp_config():
    """示例 MCP 配置"""
    return {
        "name": "Test MCP Server",
        "server_url": "https://test-mcp.example.com",
        "health_check_path": "/health",
        "tools": ["search", "retrieve"],
        "auth_type": "none",
        "description": "测试用 MCP 服务器"
    }


# ============ 辅助函数 ============

def create_test_image(format='PNG', size=(100, 100), color='red'):
    """创建测试图片"""
    try:
        from PIL import Image
        img = Image.new('RGB', size, color=color)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        img_bytes.seek(0)
        return img_bytes
    except ImportError:
        # 返回简单的字节流
        return io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

