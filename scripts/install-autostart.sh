#!/usr/bin/env bash
# 实例开机自动启动：MariaDB/Redis + 前后端（crontab @reboot）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE="$ROOT/scripts/ai-eval-service.sh"
chmod +x "$SERVICE" "$ROOT/scripts/ensure-infra.sh" "$ROOT/scripts/restart-dev.sh"

# 尽量让 MariaDB / Redis 随系统启动（有 systemd 时）
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable mariadb 2>/dev/null || systemctl enable mysql 2>/dev/null || true
  systemctl enable redis-server 2>/dev/null || systemctl enable redis 2>/dev/null || true
fi

CRON_LINE="@reboot sleep 15 && /bin/bash $SERVICE start >> /root/autodl-tmp/.ai-eval-logs/autostart.log 2>&1"

mkdir -p /root/autodl-tmp/.ai-eval-logs
TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "ai-eval-service.sh" >"$TMP" || true
echo "$CRON_LINE" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "已写入 crontab，实例重启后会自动执行: $SERVICE start"
echo "（含 MariaDB、Redis、评测 daemon、前后端）"
crontab -l | grep ai-eval || true
