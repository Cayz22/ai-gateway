import pybreaker
import os

# 从环境变量读取配置，提供默认值
FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))   # 连续失败 3 次触发熔断
RECOVERY_TIMEOUT = int(os.getenv("CB_RECOVERY_TIMEOUT", "30"))   # 熔断后 30 秒尝试恢复

# 创建熔断器实例
dify_breaker = pybreaker.CircuitBreaker(
    fail_max=FAILURE_THRESHOLD,
    reset_timeout=RECOVERY_TIMEOUT,
    exclude=[pybreaker.CircuitBreakerError]  # 不把熔断自身状态变化计为失败
)

print(f"[熔断器] 配置: 失败阈值={FAILURE_THRESHOLD}, 恢复超时={RECOVERY_TIMEOUT}s")
