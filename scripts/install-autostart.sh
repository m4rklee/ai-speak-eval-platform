#!/usr/bin/env bash
# 实例开机自动启动前后端（crontab @reboot）
set -euo pipefail

SERVICE="/root/autodl-tmp/my_version/scripts/ai-eval-service.sh"
chmod +x "$SERVICE"

CRON_LINE="@reboot sleep 15 && /bin/bash $SERVICE start >> /root/autodl-tmp/.ai-eval-logs/autostart.log 2>&1"

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "ai-eval-service.sh" >"$TMP" || true
echo "$CRON_LINE" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "已写入 crontab，实例重启后会自动执行: $SERVICE start"
crontab -l | grep ai-eval || true
