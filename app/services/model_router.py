import os
import httpx
from typing import Dict, Any

class ModelRouter:
    """多模型降级熔断（JD第3.3条核心能力）"""
    
    def __init__(self):
        self.primary = os.getenv("PRIMARY_MODEL", "qwen-plus")
        self.fallback = os.getenv("FALLBACK_MODEL", "qwen-max")
    
    async def chat_with_fallback(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        # 模拟：实际生产环境这里会调不同模型的API
        # 这里模拟主模型失败后自动切换备选
        try:
            # 模拟调用主模型（qwen-plus）
            result = f"[{self.primary}] 处理结果: {prompt[:50]}..."
            return {"model": self.primary, "result": result, "fallback": False}
        except Exception as e:
            print(f"[WARN] 主模型降级: {e}")
            # 自动切换备选模型
            result = f"[{self.fallback}] 降级处理: {prompt[:50]}..."
            return {"model": self.fallback, "result": result, "fallback": True}
