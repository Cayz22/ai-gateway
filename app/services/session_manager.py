import redis
import json
import os
from typing import List, Dict, Optional

class SessionManager:
    """基于 Redis 的会话管理（支持多实例共享）"""
    
    def __init__(self):
        # 从环境变量读取 Redis 配置
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.db = int(os.getenv("REDIS_DB", "0"))
        self.ttl = int(os.getenv("REDIS_TTL", "3600"))
        
        print(f"[Redis] 连接配置: host={self.host}, port={self.port}, db={self.db}")
        
        self.redis = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True
        )

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取指定会话的历史消息"""
        key = f"session:{session_id}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return []
    
    def save_history(self, session_id: str, messages: List[Dict[str, str]]) -> None:
        """保存会话历史"""
        key = f"session:{session_id}"
        self.redis.set(key, json.dumps(messages, ensure_ascii=False), ex=self.ttl)

    def append_message(self, session_id: str, role: str, content: str) -> None:
        """追加单条消息到会话"""
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        # 限制最大长度（保留最近 10 条消息，即 5 轮对话）
        if len(history) > 10:
            history = history[-10:]
        self.save_history(session_id, history)
    
    def clear_session(self, session_id: str) -> bool:
        """清除指定会话"""
        key = f"session:{session_id}"
        return bool(self.redis.delete(key))
    
    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        key = f"session:{session_id}"
        return self.redis.exists(key) > 0
