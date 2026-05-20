#!/usr/bin/env bash
# 开发环境启动/重启
#   ./restart-dev.sh              确保评测 daemon + 重启前端；后端仅在未运行时启动
#   ./restart-dev.sh frontend     仅重启前端（改 Vue/TS 时用）
#   ./restart-dev.sh backend      重启后端（改 Python API 时用）
#   ./restart-dev.sh daemons      仅管理评测 daemon
#   ./restart-dev.sh all          全部重启（含后端）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/python-backend"
FRONTEND="$ROOT/frontend"
PYTHON="${PYTHON:-/root/miniconda3/bin/python}"
NPM="${NPM:-/root/miniconda3/bin/npm}"
DAEMON_SCRIPT="$ROOT/scripts/eval-daemons.sh"
# shellcheck source=ensure-infra.sh
source "$ROOT/scripts/ensure-infra.sh"

TARGET="${1:-default}"

stop_one() {
  local name="$1" pidfile="$2" port="$3"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
}

port_open() {
  "$PYTHON" -c "import socket; s=socket.socket(); exit(0 if s.connect_ex(('127.0.0.1',$1))==0 else 1)" 2>/dev/null
}

ensure_deps() {
  if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
    "$PYTHON" -m pip install -r "$BACKEND/requirements.txt" -q
  fi
  if [[ ! -x "$NPM" ]]; then
    echo "错误: 未找到 npm ($NPM)" >&2
    exit 1
  fi
  if [[ ! -d "$FRONTEND/node_modules" ]]; then
    (cd "$FRONTEND" && "$NPM" install --ignore-engines)
  fi
}

ensure_daemons() {
  echo "=== 2/4 评测 daemon (MultiPA + APG-MOS) ==="
  bash "$DAEMON_SCRIPT" start --wait
}

start_backend() {
  local force="${1:-false}"
  if [[ "$force" != "true" ]] && port_open 6008; then
    echo "后端已在运行 (6008)，跳过重启"
    return 0
  fi
  stop_one backend /tmp/ai-eval-backend.pid 6008
  pkill -f "uvicorn app.main:app.*6008" 2>/dev/null || true
  sleep 1
  ensure_deps
  echo "=== 3/4 启动后端 :6008 ==="
  cd "$BACKEND"
  nohup "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 6008 \
    >> /tmp/ai-eval-backend.log 2>&1 &
  echo $! >/tmp/ai-eval-backend.pid
  for _ in $(seq 1 30); do
    port_open 6008 && break
    sleep 1
  done
  port_open 6008 && echo "backend :6008 -> up" || { echo "backend 启动失败"; exit 1; }
}

start_frontend() {
  local force="${1:-true}"
  if [[ "$force" != "true" ]] && port_open 6006; then
    echo "前端已在运行 (6006)，跳过重启"
    return 0
  fi
  stop_one frontend /tmp/ai-eval-frontend.pid 6006
  pkill -f "vite.*6006" 2>/dev/null || true
  sleep 1
  ensure_deps
  echo "=== 4/4 启动前端 :6006 ==="
  cd "$FRONTEND"
  nohup "$NPM" run dev -- --host 0.0.0.0 --port 6006 \
    >> /tmp/ai-eval-frontend.log 2>&1 &
  echo $! >/tmp/ai-eval-frontend.pid
  for _ in $(seq 1 30); do
    port_open 6006 && break
    sleep 1
  done
  port_open 6006 && echo "frontend :6006 -> up" || { echo "frontend 启动失败"; exit 1; }
}

# 任意启动网站相关进程前，先拉起数据库与 Redis
bootstrap_infra() {
  echo "=== 1/4 基础服务 (MariaDB + Redis) ==="
  ensure_db_infra
}

case "$TARGET" in
  daemons)
    bash "$DAEMON_SCRIPT" "${2:-start}" "${3:-}"
    ;;
  frontend)
    bootstrap_infra
    ensure_daemons
    start_frontend true
    ;;
  backend)
    bootstrap_infra
    ensure_daemons
    start_backend true
    ;;
  all)
    bootstrap_infra
    bash "$DAEMON_SCRIPT" stop 2>/dev/null || true
    stop_one backend /tmp/ai-eval-backend.pid 6008
    stop_one frontend /tmp/ai-eval-frontend.pid 6006
    pkill -f "uvicorn app.main:app.*6008" 2>/dev/null || true
    pkill -f "vite.*6006" 2>/dev/null || true
    sleep 1
    ensure_daemons
    start_backend true
    start_frontend true
    ;;
  default|web|start|"")
    bootstrap_infra
    ensure_daemons
    start_backend false
    start_frontend false
    ;;
  *)
    echo "用法: $0 [start|frontend|backend|daemons|all]"
    exit 1
    ;;
esac

echo ""
echo "日志: tail -f /tmp/ai-eval-multipa.log /tmp/ai-eval-apg.log /tmp/ai-eval-backend.log /tmp/ai-eval-frontend.log"
