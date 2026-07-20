import httpx
import asyncio
from typing import Dict, Any, Optional

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

    async def chat(self, query: str, inputs: Optional[Dict] = None,
                   user: str = "enterprise_user") -> Dict[str, Any]:
        """带超时重试的 Dify API 调用"""
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

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=self.headers, json=payload)

                    # 打印调试信息（可随时关闭）
                    print(f"[DIFY DEBUG] Status: {resp.status_code}")
                    print(f"[DIFY DEBUG] Response: {resp.text[:200]}...")

                    resp.raise_for_status()
                    return resp.json()

            except httpx.TimeoutException as e:
                last_error = f"超时: {e}"
                print(f"[DIFY] 尝试 {attempt} 超时，{self.retry_delay * attempt}秒后重试...")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)  # 指数退避
                continue

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
                print(f"[DIFY] 尝试 {attempt} 失败: {last_error}")

                # 4xx 错误不重试（参数错误），5xx 错误可重试
                if 400 <= e.response.status_code < 500:
                    raise Exception(f"请求参数错误: {e.response.text}")
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
        raise Exception(f"调用 Dify 失败，已重试 {self.max_retries} 次。最后错误: {last_error}")
