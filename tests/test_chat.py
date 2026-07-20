import pytest
from fastapi.testclient import TestClient

class TestChatAPI:
    """智能体接口测试"""

    def test_health_check(self, client):
        """测试健康检查接口"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_ready_check(self, client):
        """测试就绪检查接口"""
        response = client.get("/ready")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_agent_run_without_auth(self, client):
        """测试无认证时返回401"""
        response = client.post(
            "/api/v1/agent/run",
            json={"query": "请假制度", "user_id": "test"}
        )
        assert response.status_code == 401
        assert response.json()["code"] == 401

    def test_agent_run_with_invalid_auth(self, client):
        """测试无效认证时返回403"""
        response = client.post(
            "/api/v1/agent/run",
            json={"query": "请假制度", "user_id": "test"},
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 403
        assert response.json()["code"] == 403

    def test_agent_run_knowledge(self, client):
        """测试知识库问答（需要认证）"""
        import uuid
        test_user = f"test_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/agent/run",
            json={"query": "请假制度", "user_id": test_user},
            headers={"Authorization": "Bearer admin-secret-key-2026"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "answer" in data["data"]
        # 验证路由到知识库专家
        assert data["data"]["agent"] in ["knowledge_expert", "process_executor"]

    def test_stats_endpoint(self, client):
        """测试统计接口"""
        response = client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer admin-secret-key-2026"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "total_requests" in data["data"]
        assert "by_agent" in data["data"]

    def test_session_view(self, client):
        """测试会话查看接口"""
        # 先发送一个请求创建会话
        client.post(
            "/api/v1/agent/run",
            json={"query": "测试", "user_id": "test_user"},
            headers={"Authorization": "Bearer admin-secret-key-2026"}
        )
        # 查看会话
        response = client.get(
            "/api/v1/session/test_user",
            headers={"Authorization": "Bearer admin-secret-key-2026"}
        )
        # 可能是404（如果没有历史）或200
        assert response.status_code in [200, 404]
