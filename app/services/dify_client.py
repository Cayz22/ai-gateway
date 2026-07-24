import aiohttp
import asyncio
from typing import Dict, Any, Optional
import hashlib
import json
import redis
import os
from datetime import timedelta
import pybreaker
from app.services.circuit_breaker import dify_breaker
import time

# 初始化 Redis 缓存（复用会话存储的 Redis）
cache_redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=1,  # 使用 db=1 存储缓存，和会话数据隔离
    decode_responses=True
)
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 缓存 5 分钟

class DifyClient:
    def __init__(self, api_key: str, base_url: str = "http://localhost:5001/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 初始延迟（秒）
        self.timeout = 60.0     # 单次请求超时（秒）
        self.session = None

    async def _get_session(self):
        """获取共享的 aiohttp.ClientSession（延迟创建）"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=self.headers
            )
        return self.session

    async def chat(self, query: str, inputs: Optional[Dict] = None,
                   user: str = "enterprise_user") -> Dict[str, Any]:
        print(f"[性能] DifyClient.chat 开始: {time.time()}")
        # 生成缓存 Key（基于 query + inputs）
        cache_key = f"dify_cache:{hashlib.md5(f'{query}{json.dumps(inputs or {})}'.encode()).hexdigest()}"

        # 尝试从缓存读取
        try:
            cached = cache_redis.get(cache_key)
            if cached:
                print(f"[缓存] 命中: {query[:30]}...")
                return json.loads(cached)
        except:
            pass
        """带超时重试的 Dify API 调用"""
        url = f"{self.base_url}/chat-messages"
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",
            "user": user
        }
        # 请求成功后存入缓存
        try:
            cache_redis.setex(cache_key, CACHE_TTL, json.dumps(result, ensure_ascii=False))
            print(f"[缓存] 已缓存: {query[:30]}...")
        except:
            pass

        print(f"[性能] DifyClient.chat 结束: {time.time()}")
        return result

        last_error = None
    async def chat(self, query: str, inputs: Optional[Dict] = None,
                   user: str = "enterprise_user") -> Dict[str, Any]:
        """带超时重试、降级和熔断的 Dify API 调用"""
        url = f"{self.base_url}/chat-messages"
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",
            "user": user
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"[DIFY] 尝试 {attempt}/{self.max_retries} - 请求: {query[:30]}...")
                # 使用熔断器保护实际调用
                result = await dify_breaker.call(
                    self._call_dify_api, url, payload
                )
                # 调用成功，返回结果（没有 fallback 标记）
                return result

            except pybreaker.CircuitBreakerError:
                # 熔断器已打开，快速失败，不重试
                print(f"[熔断] 服务已熔断，快速返回兜底话术")
                return {
                    "answer": "AI 服务当前繁忙，请稍后重试。或联系人工客服：support@company.com",
                    "fallback": True,
                    "circuit_open": True
                }

            except asyncio.TimeoutError:
                last_error = f"超时: {e}"
                print(f"[DIFY] 尝试 {attempt} 超时，{self.retry_delay * attempt}秒后重试...")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                continue

            except aiohttp.ClientResponseError as e:
                last_error = f"HTTP {e.status}: {e.response}"
                print(f"[DIFY] 尝试 {attempt} 失败: {last_error}")
                # 4xx 错误不重试（参数错误），直接返回降级
                if 400 <= e.status< 500:
                    print(f"[降级] 请求参数错误，返回兜底话术")
                    return {
                        "answer": "抱歉，服务暂时不可用，请稍后重试或联系人工客服。",
                        "fallback": True,
                        "error_detail": last_error
                    }
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                continue

            except Exception as e:
                last_error = f"未知错误: {e}"
                print(f"[DIFY] 尝试 {attempt} 失败: {last_error}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                continue

        # 所有重试都失败
        print(f"[降级] Dify 调用失败，返回兜底话术。最后错误: {last_error}")
        return {
            "answer": "AI 服务当前繁忙，请稍后重试。或联系人工客服：support@company.com",
            "fallback": True,
            "error_detail": last_error
        }

        async def _call_dify_api(self, url: str, payload: dict) -> dict:
            import time
            print(f"[性能-http] 发送请求前: {time.time()}")
            async with self.session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise aiohttp.ClientResponseError(
                        status=resp.status,
                        message=text,
                        headers=resp.headers
                    )
                result = await resp.json()
                print(f"[性能-http] 收到响应: {time.time()}")
                return result
