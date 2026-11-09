#!/usr/bin/env python3
"""统一配色与字体管理（127.0.0.1:8790）。

- 固定端口 8790，被占用即退出码 3（不漂移，书签和自启地址不会错）；
- 预设 + 少量微调，应用后逐条回读校验，报告里只有真的写进去并读回一致的才标 ok；
- 应用前自动备份原始配置，还原按备份逐键写回（未设置过的键 gsettings reset）；
- 只做用户态配置，不动显示器/亮度/shell 配置，不需要 root。

只用 Python 标准库。
"""

import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import theme_core

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(os.path.dirname(ROOT), "web")
DEFAULT_PORT = 8790
_LOCK = threading.Lock()


def snapshot():
    state = theme_core.load_state()
    return {
        "ok": True,
        "now": time.time(),
        "presets": theme_core.PRESETS,
        "presets_resolved": [theme_core.resolve_preset(p["id"]) for p in theme_core.PRESETS],
        "current": theme_core.current_summary(),
        "capabilities": theme_core.capabilities(),
        "backups": theme_core.list_backups(),
        "original_backup": (theme_core.original_backup() or {}).get("name", ""),
        "state": {
            "preset": state.get("preset"),
            "overrides": state.get("overrides") or {},
            "updated_text": state.get("updated_text", ""),
            "restored_from": state.get("restored_from"),
        },
        "last_apply": state.get("last_apply"),
        "last_restore": state.get("last_restore"),
        "drift": theme_core.drift_report(),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 65536:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_POST(self):
        path = self.path.split("?")[0]
        if path not in ("/api/apply", "/api/restore"):
            self._json({"ok": False, "error": "not found"}, 404)
            return
        body = self._read_json()
        if not isinstance(body, dict):
            body = {}
        with _LOCK:
            try:
                if path == "/api/apply":
                    preset = str(body.get("preset") or "")
                    if preset not in theme_core.PRESET_BY_ID:
                        self._json({"ok": False, "error": "没有这个预设: %s" % preset}, 400)
                        return
                    ov = body.get("overrides") or {}
                    if not isinstance(ov, dict):
                        ov = {}
                    result = theme_core.apply_theme(preset, ov)
                else:
                    result = theme_core.restore_backup(
                        str(body.get("backup") or "") or None)
            except Exception as e:  # noqa: BLE001 —— 失败必须回给前端，不能静默
                self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)
                return
        print("[theme] %s -> %s" % (path, "ok" if result.get("ok") else "partial/fail"),
              file=sys.stderr)
        payload = snapshot()
        payload["result"] = result
        self._json(payload)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/api/state", "/api/status"):
            try:
                self._json(snapshot())
            except Exception as e:  # noqa: BLE001
                self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)
            return
        if path == "/api/health":
            self._json({"ok": True, "service": "theme-manager"})
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path in ("/", "/theme-manager.html"):
            self.path = "/theme-manager.html"
        super().do_GET()


def _cli(argv):
    if "--list" in argv:
        print("预设：")
        for p in theme_core.PRESETS:
            print("  %-16s %-8s %s  bg=%s fg=%s" % (p["id"], p["name"], p["desc"],
                                                    p["bg"], p["fg"]))
        return 0
    if "--status" in argv:
        print(json.dumps(theme_core.current_summary(), ensure_ascii=False, indent=2))
        return 0
    if "--backups" in argv:
        for b in theme_core.list_backups():
            print("%s  触发=%-22s 预设=%-14s bg=%s fg=%s"
                  % (b["name"], b["trigger"], b["preset"], b["bg"], b["fg"]))
        return 0
    if "--apply" in argv:
        i = argv.index("--apply")
        if i + 1 >= len(argv):
            print("用法: --apply <预设id>", file=sys.stderr)
            return 2
        res = theme_core.apply_theme(argv[i + 1])
        _print_report(res)
        return 0 if res.get("ok") else 1
    if "--restore" in argv:
        i = argv.index("--restore")
        name = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else None
        res = theme_core.restore_backup(name)
        _print_report(res, restore=True)
        return 0 if res.get("ok") else 1
    print(__doc__)
    return 0


def _print_report(res, restore=False):
    if res.get("error"):
        print("失败：%s" % res["error"], file=sys.stderr)
        return
    if restore:
        print("已按备份 %s 还原" % res.get("restored_from"))
    else:
        p = res.get("preset", {})
        print("预设 %s（%s） 备份: %s" % (p.get("name"), p.get("id"),
                                         res.get("backup", {}).get("dir", "—")))
    for it in res.get("items", []):
        print("  %s %-10s %-22s %-34s %s" % ("✓" if it["ok"] else "✗", it["app"],
                                             it["item"], it["value"], it.get("note", "")))
    for n in res.get("notes") or []:
        print("  注: %s" % n)
    print("回读一致 %d/%d" % (res.get("ok_count", 0), res.get("total", 0)))


def serve(argv):
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    open_browser = True
    if "--list" in argv or "--status" in argv or "--backups" in argv \
            or "--apply" in argv or "--restore" in argv:
        return _cli(argv)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--port", "-p") and i + 1 < len(argv):
            port = int(argv[i + 1])
            i += 2
            continue
        if a == "--no-browser":
            open_browser = False
        i += 1

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print("端口 %d 无法监听（%s）。可能已有一个实例在跑，"
              "用 `ss -lntp | grep %d` 确认。" % (port, e, port), file=sys.stderr)
        return 3

    url = "http://127.0.0.1:%d/" % port
    print("统一配色与字体管理: %s（pid=%d）" % (url, os.getpid()))
    print("备份目录: %s" % theme_core.BACKUP_ROOT)
    print("按 Ctrl-C 退出（不会回滚已应用的主题）")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(serve(sys.argv[1:]))
