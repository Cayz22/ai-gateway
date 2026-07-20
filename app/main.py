from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers.chat import router
from app.utils.logger import TraceMiddleware
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import os
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security
from fastapi import Depends

load_dotenv()
app = FastAPI(title="智联中枢 - 企业级AI网关", version="1.0.0")
# ==================== Swagger Authorize 按钮配置 ====================
security_scheme = HTTPBearer()
# 安全依赖（用于 Swagger 显示 Authorize 按钮）
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    token = credentials.credentials
    VALID_API_KEY = os.getenv("API_KEY", "admin-secret-key-2026")
    if token != VALID_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return token

app.swagger_ui_parameters = {"persistAuthorization": True}
app.add_middleware(TraceMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, dependencies=[Security(verify_token)])

# ==================== API Key 认证 ====================
VALID_API_KEY = os.getenv("API_KEY", "admin-secret-key-2026")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 公开路径白名单（不需要认证）
    public_paths = ["/", "/health", "/ready", "/docs", "/openapi.json"]
    # 检查路径是否在白名单中，或者以 /docs 或 /openapi.json 开头
    if request.url.path in public_paths or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
        return await call_next(request)
    
    # 检查 Authorization 头
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": "Missing Authorization header"}
        )
    
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": "Invalid Authorization format, must be 'Bearer <token>'"}
        )
    
    token = auth_header.split(" ")[1]
    if token != VALID_API_KEY:
        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": "Invalid API Key"}
        )
    
    return await call_next(request)
# =====================================================

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/openapi.json")
async def get_openapi():
    return app.openapi()

import httpx

@app.get("/ready")
async def ready():
    """
    就绪探针（Readiness Probe）
    检查依赖服务（Dify）是否可访问
    用于 K8s 判断服务是否已准备好接收流量
    """
    try:
        # 尝试访问 Dify API 的健康检查端点（或任意轻量接口）
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 访问 Dify 的 /v1 根路径，快速判断可达性
            resp = await client.get("http://localhost:5001/v1")
            if resp.status_code < 500:
                return {"status": "ready", "dify": "connected"}
            else:
                return {"status": "not_ready", "dify": "unreachable"}
    except Exception as e:
        return {"status": "not_ready", "dify": "unreachable", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
