from fastapi import APIRouter
from pydantic import BaseModel
import uuid
import os
from app.services.dify_client import DifyClient
from app.services.model_router import ModelRouter
import time
import asyncio
from collections import defaultdict
import httpx
from fastapi.responses import StreamingResponse, HTMLResponse
from typing import Optional
import json
from app.services.session_manager import SessionManager
import asyncio

# 请求统计（用于监控面板）
request_stats = {
    "total_requests": 0,
    "by_agent": defaultdict(int),
    "errors": defaultdict(int),
    "total_time_ms": 0,
    "max_time_ms": 0,
}

router = APIRouter(prefix="/api/v1", tags=["chat"])

# 会话存储
session_manager = SessionManager()
MAX_HISTORY_LENGTH = 5  # 保留最近 5 轮对话

dify_base = os.getenv("DIFY_BASE_URL", "http://localhost:5001/v1")
intent_client = DifyClient(os.getenv("INTENT_API_KEY", ""), dify_base)
knowledge_client = DifyClient(os.getenv("KNOWLEDGE_API_KEY", ""), dify_base)
process_client = DifyClient(os.getenv("PROCESS_API_KEY", ""), dify_base)
model_router = ModelRouter()

class ChatRequest(BaseModel):
    query: str
    user_id: str = "enterprise_user"
    session_id: Optional[str] = None

@router.post("/agent/run")
async def run_agent(req: ChatRequest):
    print(f"[性能] 请求开始: {time.time()}")
    start_time = time.time()
    trace_id = str(uuid.uuid4())[:8]
    request_stats["total_requests"] += 1

    session_id = req.session_id or req.user_id
    history = session_manager.get_history(session_id)
    if history:
        print(f"[会话] session_id={session_id}, 历史长度={len(history)}")
    else:
        print(f"[会话] 新会话，无历史")

    history_text = ""
    if history:
        history_text = "\n".join([
            f"{'用户' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
            for msg in history
        ])
        if len(history_text) > 200:
            history_text = history_text[:200] + "..."
            print(f"[会话] history_text已截断: {len(history_text)}字符")

    inputs = {"history": history_text or ""}
    # 初始化 result 和 agent
    result = None
    agent = "unknown"

    try:
        # 只调用知识库专家（内部已包含意图判断）
        result = await knowledge_client.chat(req.query, inputs=inputs, user=req.user_id)

        if result.get("fallback"):
            return {
                "code": 200,
                "data": {
                    "answer": result.get("answer", "服务繁忙，请稍后重试"),
                    "agent": "fallback",
                    "trace_id": trace_id,
                    "session_id": session_id
                }
            }

        # 检查回答中是否包含流程标记
        answer = result.get("answer", "")
        if "【PROCESS】" in answer:
            agent = "process_executor"

        # 更新统计
        request_stats["by_agent"][agent] += 1
        request_stats["total_time_ms"] += (time.time() - start_time) * 1000
        request_stats["max_time_ms"] = max(
            request_stats["max_time_ms"],
            (time.time() - start_time) * 1000
        )

        # 保存历史
        if session_id:
            session_manager.append_message(session_id, "user", req.query)
            ai_answer = result.get("answer", "")
            session_manager.append_message(session_id, "ai", ai_answer)
            print(f"[会话] 已保存历史，当前长度: {len(session_manager.get_history(session_id))}")

        return {
            "code": 200,
            "data": {
                "answer": result.get("answer", ""),
                "agent": agent,
                "trace_id": trace_id,
                "session_id": session_id
            }
        }

    except Exception as e:
        import traceback
        request_stats["errors"][str(type(e).__name__)] = request_stats["errors"].get(str(type(e).__name__), 0) + 1
        print(f"[错误] {trace_id}: {str(e)}")
        print(f"[详细堆栈] {traceback.format_exc()}")
        return {
            "code": 500,
            "data": {
                "error": str(e),
                "trace_id": trace_id,
                "session_id": session_id
            }
        }

@router.post("/model/chat")
async def model_chat(req: ChatRequest):
    trace_id = str(uuid.uuid4())[:8]
    result = await model_router.chat_with_fallback(req.query)
    return {"code": 200, "data": {**result, "trace_id": trace_id}}
@router.post("/ticket")
async def create_ticket(request: dict):
    """
    创建工单接口
    """
    import uuid
    ticket_id = str(uuid.uuid4())[:8]
    print(f"[工单] 收到请求: {request}")
    return {
        "code": 200,
        "message": "工单已创建",
        "ticket_id": f"TICKET-{ticket_id}"
    }
@router.get("/stats")
async def get_stats():
    """
    获取请求统计信息
    """
    total = request_stats["total_requests"]
    if total == 0:
        avg_time = 0
    else:
        avg_time = request_stats["total_time_ms"] / total
    
    return {
        "code": 200,
        "data": {
            "total_requests": total,
            "by_agent": dict(request_stats["by_agent"]),
            "errors": dict(request_stats["errors"]),
            "avg_response_time_ms": round(avg_time, 2),
            "max_response_time_ms": round(request_stats["max_time_ms"], 2),
        }
    }
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    流式对话接口（Server-Sent Events）
    实现 AI 逐字输出，提升用户体验
    """
    trace_id = str(uuid.uuid4())[:8]
    
    async def generate():
        try:
            # 先调用意图识别（阻塞）
            print(f"[性能] 开始意图识别: {time.time()}")
            intent_res = await intent_client.chat(req.query, user=req.user_id)
            print(f"[性能] 意图识别完成: {time.time()}")
            answer = intent_res.get("answer", "")
            
            # 根据意图选择工作流
            if "process" in answer.lower() or "流程" in answer:
                client = process_client
                agent = "process_executor"
            else:
                client = knowledge_client
                agent = "knowledge_expert"
            
            # 调用 Dify 流式接口
            url = f"{client.base_url}/chat-messages"
            payload = {
                "inputs": {},
                "query": req.query,
                "response_mode": "streaming",
                "user": req.user_id
            }
            
            # 发送元数据（TraceID、Agent信息）
            yield f"data: {json.dumps({'type': 'meta', 'trace_id': trace_id, 'agent': agent})}\n\n"
            
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                async with http_client.stream(
                    "POST", url, 
                    headers=client.headers, 
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    # 解析 SSE 流
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip():
                                try:
                                    data = json.loads(data_str)
                                    # 提取 answer 内容
                                    if "answer" in data and data["answer"]:
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': data['answer'], 'done': False})}\n\n"
                                    # 检查是否结束
                                    if data.get("event") == "message_end":
                                        yield f"data: {json.dumps({'type': 'done', 'done': True})}\n\n"
                                        break
                                except json.JSONDecodeError:
                                    continue
            
            # 发送结束标记
            yield f"data: {json.dumps({'type': 'done', 'done': True})}\n\n"
            
        except Exception as e:
            # 发送错误信息
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'trace_id': trace_id})}\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Trace-ID": trace_id
        }
    )
# 清楚会话接口
@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    if session_manager.clear_session(session_id):
        return {"code": 200, "message": f"Session {session_id} cleared"}
    return {"code": 404, "message": "Session not found"}

# 查看会话接口
@router.get("/session/{session_id}")
async def get_session(session_id: str):
    history = session_manager.get_history(session_id)
    if history:
        return {
            "code": 200,
            "session_id": session_id,
            "history": history,
            "total_messages": len(history)
        }
    return {"code": 404, "message": f"Session '{session_id}' not found"}
