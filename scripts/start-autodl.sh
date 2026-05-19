#!/usr/bin/env bash
# AutoDL 公网测试：前端 6006，后端 6008
# 在控制台打开「自定义服务」映射的 https 地址（6006 对应前端页面）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/python-backend"
FRONTEND="$ROOT/frontend"
PYTHON="${PYTHON:-/root/miniconda3/bin/python}"

export APP_PORT=6008

echo "=== AI 评测平台 AutoDL 启动 ==="
echo "前端（浏览器请开控制台里 6006 对应的公网 URL）: http://127.0.0.1:6006"
echo "后端 API: http://127.0.0.1:6008  (文档 /api/docs)"
echo ""

if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
  echo "安装后端依赖..."
  "$PYTHON" -m pip install -r "$BACKEND/requirements.txt" -q
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "安装前端依赖..."
  (cd "$FRONTEND" && npm install --ignore-engines)
fi

# 可选：检查 Redis / MySQL
if ! "$PYTHON" -c "import redis; redis.Redis().ping()" 2>/dev/null; then
  echo "警告: Redis 未连接 (localhost:6379)，登录/Session 可能失败，请先在 AutoDL 启动 Redis"
fi

cd "$BACKEND"
echo "启动后端 (0.0.0.0:6008)..."
nohup "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 6008 > /tmp/ai-eval-backend.log 2>&1 &
echo $! > /tmp/ai-eval-backend.pid
sleep 2

cd "$FRONTEND"
echo "启动前端 (0.0.0.0:6006)..."
nohup npm run dev -- --host 0.0.0.0 --port 6006 >> /tmp/ai-eval-frontend.log 2>&1 &
echo $! > /tmp/ai-eval-frontend.pid

echo ""
echo "日志: tail -f /tmp/ai-eval-backend.log /tmp/ai-eval-frontend.log"
echo "停止: kill \$(cat /tmp/ai-eval-backend.pid) \$(cat /tmp/ai-eval-frontend.pid)"
