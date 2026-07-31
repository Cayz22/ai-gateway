# 智联中枢 — AI 智能体中台

## 项目概述
基于 Dify + FastAPI 构建的 AI 智能体中台
核心解决两个问题
1. *员工自助查询*：通过 RAG 技术智能问答，减少 HR/行政 30% 的重复咨询
2. *流程自动化*：识别“发起审批”类意图，自动创建工单，减少人工录入错误

## 核心功能
| 功能 | 描述 | 技术实现 |

多智能体协作:意图路由 → 知识库专家/流程执行助手 (Dify Chatflow + FastAPI网关)
RAG 增强检索:上传文档 → 向量化 → 检索增强生成 (Dify 知识库 + 千问Embedding)
多模型降级:主模型失败自动切换备用模型 (Python 网关层实现)
对话记忆:多轮对话上下文无缝衔接 (Redis 持久化会话)
API 认证:统一的 API Key 认证机制 (FastAPI 中间件)
可观测性:全链路追踪 + 实时监控统计 (TraceID + `/stats` 接口)
探针接口:`/health` + `/ready`，支持K8s部署 (FastAPI)
健壮性保障：熔断器 + 降级 + 重试 （pybreaker + 指数退避）
性能优化：连接池复用 + 高频问题缓存 （aiohttp + Redis 缓存）


### 前置条件

- Docker & Docker Compose
- Redis（或使用 Docker Compose 自带）
- 已部署的 Dify 服务（端口 5001）

#快速启动
```bash
# 进入 Dify 的 Docker 目录
cd ~/dify/docker

# 启动 Dify 服务
docker compose up -d

# 等待 30 秒，确认容器运行正常
docker compose ps
# 确保 docker-api-1 状态为 Up

# 验证 Dify API 可访问
curl http://localhost:5001/v1/chat-messages \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' 2>/dev/null | head -c 100
# 预期返回 {"code":"unauthorized"...}（说明 API 服务正常）

# 进入项目目录
cd ~/enterprise-ai-gateway

# 激活虚拟环境（如果未激活）
source venv/bin/activate

# 启动 FastAPI 服务
python3 -m app.main

# 4. 访问
http://localhost:8000/docs

#认证方式
#所有需要认证的接口需在请求头中携带：
Authorization: Bearer admin-secret-key-2026
