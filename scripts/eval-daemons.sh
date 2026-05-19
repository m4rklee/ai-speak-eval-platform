#!/usr/bin/env bash
# MultiPA + APG-MOS 常驻评测服务（独立于网站后端，重启后端不会杀掉它们）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/python-backend"
PYTHON="${PYTHON:-/root/miniconda3/bin/python}"

MULTIPA_PID="/tmp/ai-eval-multipa.pid"
APG_PID="/tmp/ai-eval-apg.pid"
MULTIPA_LOG="/tmp/ai-eval-multipa.log"
APG_LOG="/tmp/ai-eval-apg.log"

# 从 .env 读取路径（若存在）
if [[ -f "$BACKEND/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source <(grep -E '^(MULTIPA_DIR|APG_MOS_DIR|MULTIPA_PYTHON|MULTIPA_DAEMON_PORT|APG_DAEMON_PORT|UNIFIED_EVAL_DIR|REDIS_HOST|REDIS_PORT|REDIS_DB|REDIS_PASSWORD)=' "$BACKEND/.env" | sed 's/\r$//')
  set +a
fi

MULTIPA_DIR="${MULTIPA_DIR:-/root/my_image_files/口语练习评测/MultiPA}"
APG_MOS_DIR="${APG_MOS_DIR:-/root/autodl-tmp/APG-MOS}"
UNIFIED_EVAL_DIR="${UNIFIED_EVAL_DIR:-/root/unified-speech-eval}"
MULTIPA_PORT="${MULTIPA_DAEMON_PORT:-18765}"
APG_PORT="${APG_DAEMON_PORT:-18766}"
MULTIPA_PY="${MULTIPA_PYTHON:-$MULTIPA_DIR/.venv/bin/python}"
APG_PY="${PYTHON}"

export MULTIPA_DIR APG_MOS_DIR MULTIPA_DAEMON_PORT="$MULTIPA_PORT" APG_DAEMON_PORT="$APG_PORT"
export UNI_EVAL_LIVE_DIR="${UNI_EVAL_LIVE_DIR:-/tmp/uni_eval_live}"
export UNIFIED_EVAL_DIR REDIS_HOST="${REDIS_HOST:-localhost}" REDIS_PORT="${REDIS_PORT:-6379}" REDIS_DB="${REDIS_DB:-0}"
export REDIS_PASSWORD="${REDIS_PASSWORD:-}"

health_ok() {
  local port="$1"
  curl -sf --connect-timeout 2 "http://127.0.0.1:${port}/health" 2>/dev/null | grep -q '"ready"[[:space:]]*:[[:space:]]*true'
}

daemon_ready() {
  health_ok "$MULTIPA_PORT" && health_ok "$APG_PORT"
}

is_pid_alive() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  kill -0 "$(cat "$pidfile")" 2>/dev/null
}

start_multipa() {
  if health_ok "$MULTIPA_PORT"; then
    echo "MultiPA 已就绪 (:${MULTIPA_PORT})"
    return 0
  fi
  if is_pid_alive "$MULTIPA_PID"; then
    echo "MultiPA 启动中 (pid $(cat "$MULTIPA_PID"))，等待模型加载..."
    return 0
  fi
  if [[ ! -x "$MULTIPA_PY" ]]; then
    echo "错误: MultiPA Python 不存在: $MULTIPA_PY" >&2
    return 1
  fi
  echo "启动 MultiPA daemon → :${MULTIPA_PORT} (log: $MULTIPA_LOG)"
  nohup "$MULTIPA_PY" "$UNIFIED_EVAL_DIR/multipa_daemon.py" >>"$MULTIPA_LOG" 2>&1 &
  echo $! >"$MULTIPA_PID"
}

start_apg() {
  if health_ok "$APG_PORT"; then
    echo "APG-MOS 已就绪 (:${APG_PORT})"
    return 0
  fi
  if is_pid_alive "$APG_PID"; then
    echo "APG-MOS 启动中 (pid $(cat "$APG_PID"))..."
    return 0
  fi
  echo "启动 APG-MOS daemon → :${APG_PORT} (log: $APG_LOG)"
  nohup "$APG_PY" "$UNIFIED_EVAL_DIR/apg_daemon.py" >>"$APG_LOG" 2>&1 &
  echo $! >"$APG_PID"
}

wait_ready() {
  local timeout="${1:-600}"
  local elapsed=0
  echo "等待评测 daemon 就绪 (最多 ${timeout}s)..."
  while (( elapsed < timeout )); do
    if daemon_ready; then
      echo "MultiPA + APG-MOS 均已就绪"
      return 0
    fi
    if (( elapsed > 0 && elapsed % 30 == 0 )); then
      local m="—" a="—"
      health_ok "$MULTIPA_PORT" && m="OK" || m="loading"
      health_ok "$APG_PORT" && a="OK" || a="loading"
      echo "  [${elapsed}s] MultiPA=${m} APG=${a}"
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "超时: 评测 daemon 未在 ${timeout}s 内就绪" >&2
  echo "  tail -30 $MULTIPA_LOG $APG_LOG" >&2
  return 1
}

cmd_start() {
  local do_wait=false
  if [[ "${1:-}" == "--wait" ]]; then
    do_wait=true
  fi
  # APG 轻、MultiPA 重：并行启动
  start_apg &
  start_multipa &
  wait
  if $do_wait; then
    wait_ready "${EVAL_DAEMON_WAIT_SEC:-600}"
  fi
}

cmd_stop() {
  for pair in "MultiPA:$MULTIPA_PID" "APG:$APG_PID"; do
    local name="${pair%%:*}" pidfile="${pair##*:}"
    if is_pid_alive "$pidfile"; then
      kill "$(cat "$pidfile")" 2>/dev/null || true
      echo "已停止 $name"
    fi
    rm -f "$pidfile"
  done
  # 清理无 pid 文件但仍在占端口的旧进程
  if command -v lsof >/dev/null 2>&1; then
    for port in "$MULTIPA_PORT" "$APG_PORT"; do
      lsof -ti ":$port" 2>/dev/null | xargs -r kill 2>/dev/null || true
    done
  fi
}

cmd_status() {
  echo "MultiPA :${MULTIPA_PORT} → $(health_ok "$MULTIPA_PORT" && echo READY || echo NOT_READY) pid=$(cat "$MULTIPA_PID" 2>/dev/null || echo -)"
  echo "APG-MOS :${APG_PORT} → $(health_ok "$APG_PORT" && echo READY || echo NOT_READY) pid=$(cat "$APG_PID" 2>/dev/null || echo -)"
}

case "${1:-start}" in
  start) shift || true; cmd_start "$@" ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  wait) wait_ready "${2:-600}" ;;
  restart) cmd_stop; sleep 2; cmd_start --wait ;;
  *) echo "用法: $0 {start [--wait]|stop|status|wait [sec]|restart}"; exit 1 ;;
esac
