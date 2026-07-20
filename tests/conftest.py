import pytest
import os
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from app.main import app
from app.routers.chat import session_manager

@pytest.fixture(scope="function")
def client():
    """创建测试客户端，并清理 Redis 会话"""
    # 清理所有会话（避免测试间干扰）
    # 注意：这需要 Redis 连接，如果 Redis 未启动，测试会失败
    try:
        session_manager.redis.flushdb()
    except:
        pass
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """认证头"""
    return {"Authorization": "Bearer admin-secret-key-2026"}
