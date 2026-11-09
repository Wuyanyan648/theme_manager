#!/usr/bin/env bash
# 前台启动（会顺手打开浏览器），Ctrl-C 结束。
# 常驻请用 ./run-service.sh 或 ./install-autostart.sh（systemd 用户单元）。
# 换端口: PORT=9000 ./start.sh      只看命令行: ./start.sh --status
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PORT="${PORT:-8790}"
exec python3 "$DIR/backend/theme_server.py" "$@"
