#!/usr/bin/env bash
# 启动网站依赖的基础服务：MariaDB / Redis
# 被 restart-dev.sh、ai-eval-service.sh 等 source 使用

_ensure_port_open() {
  local port="$1"
  local py="${PYTHON:-/root/miniconda3/bin/python}"
  "$py" -c "import socket; s=socket.socket(); exit(0 if s.connect_ex(('127.0.0.1',$port))==0 else 1)" 2>/dev/null
}

_ensure_service_start() {
  local name="$1"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl start "$name" 2>/dev/null && return 0
  fi
  if command -v service >/dev/null 2>&1; then
    service "$name" start 2>/dev/null && return 0
  fi
  return 1
}

ensure_mariadb() {
  if _ensure_port_open 3306; then
    return 0
  fi
  echo "=== 启动 MariaDB (:3306) ==="
  _ensure_service_start mariadb || _ensure_service_start mysql || true
  for _ in $(seq 1 20); do
    if _ensure_port_open 3306; then
      echo "MariaDB :3306 -> up"
      return 0
    fi
    sleep 1
  done
  echo "错误: MariaDB 未监听 3306，请检查 DB_HOST/DB_PORT 或手动执行: service mariadb start" >&2
  return 1
}

ensure_redis() {
  if _ensure_port_open 6379; then
    return 0
  fi
  echo "=== 启动 Redis (:6379) ==="
  _ensure_service_start redis-server || _ensure_service_start redis || true
  if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
    echo "Redis :6379 -> up"
    return 0
  fi
  for _ in $(seq 1 10); do
    if _ensure_port_open 6379; then
      echo "Redis :6379 -> up"
      return 0
    fi
    sleep 1
  done
  echo "警告: Redis 未就绪，登录 Session 可能异常（可执行: service redis-server start）" >&2
  return 0
}

ensure_db_infra() {
  ensure_mariadb
  ensure_redis
}
