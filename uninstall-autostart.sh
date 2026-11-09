#!/usr/bin/env bash
# 卸载用户级 systemd 单元。不会还原配色（配色请用界面上的「还原本机原始配置」），
# 也不会删备份目录。
set -u
UNIT_DIR="$HOME/.config/systemd/user"

systemctl --user disable --now theme-manager.service 2>/dev/null || true
rm -f "$UNIT_DIR/theme-manager.service"
systemctl --user daemon-reload 2>/dev/null || true
pkill -f "[t]heme_server.py" 2>/dev/null || true

echo "已卸载 theme-manager 用户单元。"
echo "当前配色未被改动；还原请打开界面点「还原本机原始配置」，或命令行："
echo "  python3 $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backend/theme_server.py --restore"
echo "备份目录保留在: $HOME/.local/share/theme-manager-backup/"
