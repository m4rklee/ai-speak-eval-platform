#!/usr/bin/env bash
# AI 评测平台进程管理（AutoDL：前端 6006，后端 6008）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/python-backend"
FRONTEND="$ROOT/frontend"
PYTHON="${PYTHON:-/root/miniconda3/bin/python}"
NPM="${NPM:-/root/miniconda3/bin/npm}"
NODE="${NODE:-/root/miniconda3/bin/node}"

PID_DIR="/root/autodl-tmp/.ai-eval-pids"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"
BACKEND_LOG="/root/autodl-tmp/.ai-eval-logs/backend.log"
FRONTEND_LOG="/root/autodl-tmp/.ai-eval-logs/frontend.log"

mkdir -p "$PID_DIR" "$(dirname "$BACKEND_LOG")"

# shellcheck source=ensure-infra.sh
source "$(dirname "$0")/ensure-infra.sh"

port_open() {
  "$PYTHON" -c "import socket; s=socket.socket(); exit(0 if s.connect_ex(('127.0.0.1',$1))==0 else 1)" 2>/dev/null
}

is_running() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(cat "$pidfile")"
  kill -0 "$pid" 2>/dev/null
}

stop_one() {
  local name="$1" pidfile="$2"
  if is_running "$pidfile"; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    sleep 1
    kill -9 "$(cat "$pidfile")" 2>/dev/null || true
    echo "已停止 $name (pid $(cat "$pidfile"))"
  fi
  rm -f "$pidfile"
}

cmd_stop() {
  stop_one "backend" "$BACKEND_PID"
  stop_one "frontend" "$FRONTEND_PID"
}

ensure_deps() {
  if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
    echo "安装后端依赖..."
    "$PYTHON" -m pip install -r "$BACKEND/requirements.txt" -q
  fi
  if [[ ! -d "$FRONTEND/node_modules" ]]; then
    echo "安装前端依赖..."
    (cd "$FRONTEND" && "$NPM" install --ignore-engines)
  fi
}

start_backend() {
  if is_running "$BACKEND_PID" || port_open 6008; then
    echo "后端已在运行 (6008)"
    return 0
  fi
  ensure_deps
  cd "$BACKEND"
  nohup "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 6008 >>"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID"
  for _ in $(seq 1 30); do
    port_open 6008 && break
    sleep 1
  done
  if port_open 6008; then
    echo "后端已启动 pid=$(cat "$BACKEND_PID") log=$BACKEND_LOG"
  else
    echo "后端启动失败，见 $BACKEND_LOG" >&2
    tail -20 "$BACKEND_LOG" >&2 || true
    return 1
  fi
}

start_frontend() {
  if is_running "$FRONTEND_PID" || port_open 6006; then
    echo "前端已在运行 (6006)"
    return 0
  fi
  ensure_deps
  cd "$FRONTEND"
  nohup "$NPM" run dev -- --host 0.0.0.0 --port 6006 >>"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID"
  for _ in $(seq 1 60); do
    port_open 6006 && break
    sleep 1
  done
  if port_open 6006; then
    echo "前端已启动 pid=$(cat "$FRONTEND_PID") log=$FRONTEND_LOG"
  else
    echo "前端启动失败，见 $FRONTEND_LOG" >&2
    tail -20 "$FRONTEND_LOG" >&2 || true
    return 1
  fi
}

cmd_start() {
  echo "=== 基础服务 (MariaDB + Redis) ==="
  ensure_db_infra
  echo "=== 评测 daemon ==="
  bash "$(dirname "$0")/eval-daemons.sh" start --wait
  start_backend
  start_frontend
  echo ""
  echo "浏览器打开 AutoDL 控制台「6006」对应的 https 公网地址即可。"
}

cmd_status() {
  echo "后端 6008: $(port_open 6008 && echo UP || echo DOWN) pid=$(cat "$BACKEND_PID" 2>/dev/null || echo -)"
  echo "前端 6006: $(port_open 6006 && echo UP || echo DOWN) pid=$(cat "$FRONTEND_PID" 2>/dev/null || echo -)"
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  *) echo "用法: $0 {start|stop|restart|status}"; exit 1 ;;
esac
