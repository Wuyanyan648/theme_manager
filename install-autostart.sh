#!/usr/bin/env bash
# 安装并启用用户级 systemd 单元 theme-manager.service（127.0.0.1:8790，登录自启）。
# 本服务只写用户态配置（gsettings / dconf / Trae 的 settings.json），不需要 root，
# 也不需要 X11（GTK 主题与终端配色都是 gsettings 生效），所以直接 enable 即可。
set -eu
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
chmod +x "$DIR/start.sh" "$DIR/run-service.sh" 2>/dev/null || true

# 先在跑的老实例（前台 / wrapper 方式）会让端口被占用，先停
pkill -f "[t]heme_server.py" 2>/dev/null || true
systemctl --user stop theme-manager.service 2>/dev/null || true
sleep 0.5

sed "s|@DIR@|$DIR|g" "$DIR/systemd/theme-manager.service" > "$UNIT_DIR/theme-manager.service"
chmod 644 "$UNIT_DIR/theme-manager.service"
systemctl --user daemon-reload
systemctl --user enable theme-manager.service >/dev/null
systemctl --user restart theme-manager.service

sleep 1
echo "已安装用户单元: $UNIT_DIR/theme-manager.service"
echo "界面:   http://127.0.0.1:8790/"
echo "状态:   systemctl --user status theme-manager"
echo "日志:   journalctl --user -u theme-manager -n 50 --no-pager"
echo "卸载:   $DIR/uninstall-autostart.sh"
echo
echo "备份目录: $HOME/.local/share/theme-manager-backup/（还原不会删它）"
