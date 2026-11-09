#!/usr/bin/env bash
# 常驻运行（无浏览器），崩溃后 2 秒重启。给手动调试用；
# 登录自启走 install-autostart.sh 装的 systemd 用户单元。
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PORT="${PORT:-8790}"
while true; do
  python3 "$DIR/backend/theme_server.py" --no-browser
  code=$?
  if [ "$code" -eq 3 ]; then
    echo "[run-service] 端口 $PORT 已被占用，视为已有实例，退出。" >&2
    exit 0
  fi
  echo "[run-service] theme_server 退出（code=$code），2 秒后重启…" >&2
  sleep 2
done
