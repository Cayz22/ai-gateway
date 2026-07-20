import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class TraceMiddleware(BaseHTTPMiddleware):
    """
    链路追踪中间件
    - 生成 TraceID
    - 记录请求耗时
    - 慢请求告警（>3秒）
    """
    
    async def dispatch(self, request: Request, call_next):
        # 生成 TraceID
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # 记录请求信息
        logger.info(f"[{trace_id}] → {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常
            duration = (time.time() - start_time) * 1000
            logger.error(f"[{trace_id}] ✗ {request.method} {request.url.path} | {duration:.0f}ms | ERROR: {str(e)}")
            raise
        
        # 计算耗时（毫秒）
        duration = (time.time() - start_time) * 1000
        
        # 根据状态码分类记录
        if response.status_code >= 500:
            log_level = logger.error
            emoji = "✗"
        elif response.status_code >= 400:
            log_level = logger.warning
            emoji = "⚠"
        else:
            log_level = logger.info
            emoji = "✓"
        
        # 慢请求告警（> 3000ms）
        if duration > 3000:
            log_level = logger.warning
            emoji = "🐢"
            log_level(f"[{trace_id}] {emoji} {request.method} {request.url.path} | {duration:.0f}ms | SLOW")
        else:
            log_level(f"[{trace_id}] {emoji} {request.method} {request.url.path} | {duration:.0f}ms | {response.status_code}")
        
        # 将 TraceID 写入响应头（面试时重点展示）
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(int(duration))
        
        return response
