# 智联中枢 — AI 智能体中台

## 项目概述
基于 Dify + FastAPI 构建的 AI 智能体中台...

## 核心功能
多智能体协作、RAG 增强检索、多模型降级、对话记忆、API 认证、可观测性、探针接口

## 快速启动
```bash
# 1. 启动 Dify
cd ~/dify/docker && docker compose up -d

# 2. 启动网关
cd ~/enterprise-ai-gateway && docker compose up -d

# 3. 验证
curl http://localhost:8000/health

# 4. 访问
http://localhost:8000/docs
