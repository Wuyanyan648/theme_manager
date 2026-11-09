#!/usr/bin/env python3
"""统一配色与字体管理：预设、应用、备份、还原。

覆盖范围（全部通过用户态命令完成，不需要 root）：
- GNOME Terminal：16 色盘、前景/背景、光标/选区、字体、字号、行高（cell-height-scale）
- GNOME 桌面：GTK 主题、color-scheme、界面字体、等宽字体（gsettings）
- gedit：GtkSourceView 配色方案 + 编辑器字体
- Trae CN（VS Code 系）：settings.json 的 workbench.colorTheme 与编辑器字体

刻意不碰：显示器输出/分辨率/缩放/亮度/色温（那是 screen 服务的事）、
org.gnome.desktop.wm.preferences 里的窗口管理器键、shell 的 .bashrc / .zshrc。

所有写入前都会把「涉及到的键/文件」的原始值备份到
~/.local/share/theme-manager-backup/<时间戳>/，还原时按备份逐键写回
（原本没有显式设置的键会 gsettings reset，回到 schema 默认值）。

只用 Python 标准库 + 系统自带 gsettings / dconf。
"""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime

GSETTINGS = shutil.which("gsettings") or "/usr/bin/gsettings"
DCONF = shutil.which("dconf") or "/usr/bin/dconf"
FC_LIST = shutil.which("fc-list") or "/usr/bin/fc-list"

HOME = os.path.expanduser("~")
BACKUP_ROOT = os.path.join(HOME, ".local/share/theme-manager-backup")
STATE_DIR = os.path.join(HOME, ".local/share/theme-manager")
STATE_PATH = os.path.join(STATE_DIR, "state.json")

TERMINAL_LIST_SCHEMA = "org.gnome.Terminal.ProfilesList"
TERMINAL_PROFILE_SCHEMA = "org.gnome.Terminal.Legacy.Profile"
TERMINAL_BASE_PATH = "/org/gnome/terminal/legacy/profiles:/"
INTERFACE_SCHEMA = "org.gnome.desktop.interface"
GEDIT_SCHEMA = "org.gnome.gedit.preferences.editor"

TERMINAL_KEYS = [
    "use-theme-colors", "use-system-font", "font", "cell-height-scale",
    "background-color", "foreground-color", "bold-color", "palette",
    "cursor-colors-set", "cursor-background-color", "cursor-foreground-color",
    "highlight-colors-set", "highlight-background-color", "highlight-foreground-color",
]
INTERFACE_KEYS = ["gtk-theme", "color-scheme", "font-name", "monospace-font-name"]
GEDIT_KEYS = ["scheme", "editor-font"]

# Trae / VS Code 系编辑器
EDITOR_SETTINGS_CANDIDATES = [
    os.path.join(HOME, ".config/Trae CN/User/settings.json"),
    os.path.join(HOME, ".config/Trae/User/settings.json"),
]
EDITOR_STATE_DB_CANDIDATES = [
    os.path.join(HOME, ".config/Trae CN/User/globalStorage/state.vscdb"),
    os.path.join(HOME, ".config/Trae/User/globalStorage/state.vscdb"),
]
TRAE_EXT_DIRS = [
    "/usr/share/trae-cn/resources/app/extensions",
    os.path.join(HOME, ".trae-cn/extensions"),
]

UI_FONT_FAMILY = "Ubuntu Sans"
MONO_FONT_FAMILY = "Ubuntu Sans Mono"

# ── 预设 ────────────────────────────────────────────────────────────────────
# 每个预设同时给出：终端 16 色 + 前景/背景/强调、GTK 主题取向、编辑器主题、
# gedit 配色方案、字体与行高。gtk_theme / gedit_scheme / editor_theme 都是
# 「候选列表」，按顺序取本机真实存在的第一个，取不到就在报告里说明。
PRESETS = [
    {
        "id": "warm-gray",
        "name": "暖灰浅色",
        "desc": "纸感暖灰底，对比度约 9:1，白天和强光下不刺眼。",
        "mode": "light",
        "fg": "#3E3934",
        "bg": "#F0ECE5",
        "accent": "#8C6E4A",
        "palette": [
            "#3E3934", "#A8422E", "#5E7B45", "#96742B",
            "#3C6E8F", "#87587A", "#3F7D77", "#CFC7BA",
            "#6E675E", "#C05B3F", "#75935A", "#B08C3C",
            "#4F82A6", "#9E6F92", "#549B94", "#FBF9F5",
        ],
        "gtk_theme": ["Yaru-bark", "Yaru-sage", "Adwaita"],
        "color_scheme": "default",
        "gedit_scheme": ["Yaru", "tango", "classic"],
        "editor_theme": ["Quiet Light", "Default Light Modern", "Light+", "Light"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "graphite",
        "name": "石墨深色",
        "desc": "中性石墨灰，无彩色偏色，长时间盯代码最稳。",
        "mode": "dark",
        "fg": "#CDD1D6",
        "bg": "#21242A",
        "accent": "#7FA8CC",
        "palette": [
            "#21242A", "#C96A62", "#6FA36B", "#C2A055",
            "#6A93B8", "#A87EA8", "#5EA0A0", "#BFC5CC",
            "#6B7280", "#DA8078", "#83B57F", "#D2B26A",
            "#7FA8CC", "#BC93BC", "#74B4B4", "#EDF0F3",
        ],
        "gtk_theme": ["Adwaita-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["Adwaita-dark", "Yaru-dark", "oblivion"],
        "editor_theme": ["Default Dark Modern", "Dark+", "Dark"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "gruvbox-dark",
        "name": "Gruvbox 深色",
        "desc": "暖褐底 + 复古高饱和色，对比度低但色相分明。",
        "mode": "dark",
        "fg": "#EBDBB2",
        "bg": "#282828",
        "accent": "#D79921",
        "palette": [
            "#282828", "#CC241D", "#98971A", "#D79921",
            "#458588", "#B16286", "#689D6A", "#A89984",
            "#928374", "#FB4934", "#B8BB26", "#FABD2F",
            "#83A598", "#D3869B", "#8EC07C", "#EBDBB2",
        ],
        "gtk_theme": ["Yaru-bark-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["oblivion", "Adwaita-dark"],
        "editor_theme": ["Kimbie Dark", "Default Dark Modern"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "nord",
        "name": "Nord",
        "desc": "冷蓝灰极地色，蓝青为主，亮度低于常规深色。",
        "mode": "dark",
        "fg": "#D8DEE9",
        "bg": "#2E3440",
        "accent": "#88C0D0",
        "palette": [
            "#3B4252", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#88C0D0", "#E5E9F0",
            "#4C566A", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#8FBCBB", "#ECEFF4",
        ],
        "gtk_theme": ["Yaru-blue-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["Adwaita-dark", "solarized-dark"],
        "editor_theme": ["Default Dark Modern", "Dark+"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "one-dark",
        "name": "One Dark",
        "desc": "Atom 经典深色，蓝灰底 + 柔和多彩语法色。",
        "mode": "dark",
        "fg": "#ABB2BF",
        "bg": "#282C34",
        "accent": "#61AFEF",
        "palette": [
            "#282C34", "#E06C75", "#98C379", "#E5C07B",
            "#61AFEF", "#C678DD", "#56B6C2", "#ABB2BF",
            "#5C6370", "#E06C75", "#98C379", "#E5C07B",
            "#61AFEF", "#C678DD", "#56B6C2", "#FFFFFF",
        ],
        "gtk_theme": ["Yaru-dark", "Adwaita-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["Adwaita-dark", "oblivion"],
        "editor_theme": ["Default Dark Modern", "Dark+"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "solarized-light",
        "name": "Solarized 浅沙",
        "desc": "经典低对比浅沙底，环境光偏强时容易发灰。",
        "mode": "light",
        "fg": "#657B83",
        "bg": "#FDF6E3",
        "accent": "#268BD2",
        "palette": [
            "#073642", "#DC322F", "#859900", "#B58900",
            "#268BD2", "#D33682", "#2AA198", "#EEE8D5",
            "#002B36", "#CB4B16", "#586E75", "#657B83",
            "#839496", "#6C71C4", "#93A1A1", "#FDF6E3",
        ],
        "gtk_theme": ["Yaru-sage", "Adwaita"],
        "color_scheme": "default",
        "gedit_scheme": ["solarized-light", "tango"],
        "editor_theme": ["Solarized (light)", "Default Light Modern"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    # ── 追加的深色方案：按「取向」拉开差异，亮度整体低于原 graphite / one-dark ──
    {
        "id": "everforest-dark",
        "name": "Everforest 深色",
        "desc": "低饱和暖绿，亮色全部压暗，夜间长时间阅读不抢眼。",
        "mode": "dark",
        "fg": "#D3C6AA",
        "bg": "#2F383E",
        "accent": "#A7C080",
        "palette": [
            "#2F383E", "#E67E80", "#A7C080", "#DBBC7F",
            "#7FBBB3", "#D699B6", "#83C092", "#D3C6AA",
            "#7A8478", "#E67E80", "#A7C080", "#DBBC7F",
            "#7FBBB3", "#D699B6", "#83C092", "#F2EFDF",
        ],
        "gtk_theme": ["Yaru-olive-dark", "Yaru-sage-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["oblivion", "Adwaita-dark"],
        "editor_theme": ["Monokai Dimmed", "Kimbie Dark"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "kanagawa",
        "name": "Kanagawa 墨色",
        "desc": "墨黑底 + 低饱和青蓝，冷而不冰，接近和纸墨色。",
        "mode": "dark",
        "fg": "#DCD7BA",
        "bg": "#1F1F28",
        "accent": "#7E9CD8",
        "palette": [
            "#16161D", "#C34043", "#76946A", "#C0A36E",
            "#7E9CD8", "#957FB8", "#6A9589", "#C8C093",
            "#727169", "#E82424", "#98BB6C", "#E6C384",
            "#7FB4CA", "#938AA9", "#7AA89F", "#DCD7BA",
        ],
        "gtk_theme": ["Yaru-prussiangreen-dark", "Yaru-blue-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["solarized-dark", "oblivion"],
        "editor_theme": ["Tomorrow Night Blue", "Default Dark Modern"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "tokyo-night",
        "name": "Tokyo Night",
        "desc": "深靛蓝夜色，冷调，语法色偏蓝紫，适合夜间编码。",
        "mode": "dark",
        "fg": "#A9B1D6",
        "bg": "#1A1B26",
        "accent": "#7AA2F7",
        "palette": [
            "#15161E", "#F7768E", "#9ECE6A", "#E0AF68",
            "#7AA2F7", "#BB9AF7", "#7DCFFF", "#A9B1D6",
            "#414868", "#F7768E", "#9ECE6A", "#E0AF68",
            "#7AA2F7", "#BB9AF7", "#7DCFFF", "#C0CAF5",
        ],
        "gtk_theme": ["Yaru-purple-dark", "Yaru-blue-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["oblivion", "Adwaita-dark"],
        "editor_theme": ["Default Dark Modern", "Tomorrow Night Blue"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "catppuccin-mocha",
        "name": "Catppuccin Mocha",
        "desc": "柔和粉彩深色，色相多但饱和度低，灰紫底不偏纯黑。",
        "mode": "dark",
        "fg": "#CDD6F4",
        "bg": "#1E1E2E",
        "accent": "#89B4FA",
        "palette": [
            "#313244", "#F38BA8", "#A6E3A1", "#F9E2AF",
            "#89B4FA", "#F5C2E7", "#94E2D5", "#BAC2DE",
            "#585B70", "#F38BA8", "#A6E3A1", "#F9E2AF",
            "#89B4FA", "#F5C2E7", "#94E2D5", "#CDD6F4",
        ],
        "gtk_theme": ["Yaru-magenta-dark", "Yaru-purple-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["Adwaita-dark", "oblivion"],
        "editor_theme": ["Monokai Dimmed", "Default Dark Modern"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "dracula",
        "name": "Dracula",
        "desc": "高对比深色，亮色鲜亮；光线充足或白天用更合适。",
        "mode": "dark",
        "fg": "#F8F8F2",
        "bg": "#282A36",
        "accent": "#BD93F9",
        "palette": [
            "#21222C", "#FF5555", "#50FA7B", "#F1FA8C",
            "#BD93F9", "#FF79C6", "#8BE9FD", "#F8F8F2",
            "#6272A4", "#FF6E6E", "#69FF94", "#FFFFA5",
            "#D6ACFF", "#FF92DF", "#A4FFFF", "#F8F8F2",
        ],
        "gtk_theme": ["Yaru-purple-dark", "Adwaita-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["oblivion", "Adwaita-dark"],
        "editor_theme": ["Monokai", "Dark+"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
    {
        "id": "zenburn",
        "name": "Zenburn",
        "desc": "极低对比的暗橄榄灰，无纯黑纯白，亮色比常规深色再暗一档。",
        "mode": "dark",
        "fg": "#DCDCCC",
        "bg": "#3F3F3F",
        "accent": "#F0DFAF",
        "palette": [
            "#3F3F3F", "#CC9393", "#7F9F7F", "#F0DFAF",
            "#7CB8BB", "#DC8CC3", "#93E0E3", "#DCDCCC",
            "#709080", "#DCA3A3", "#BFEBBF", "#E0CF9F",
            "#94BFF3", "#EC93D3", "#93E0E3", "#E8E8D8",
        ],
        "gtk_theme": ["Yaru-sage-dark", "Yaru-olive-dark", "Yaru-dark"],
        "color_scheme": "prefer-dark",
        "gedit_scheme": ["oblivion", "solarized-dark"],
        "editor_theme": ["Solarized (dark)", "Monokai Dimmed"],
        "mono_size": 12,
        "ui_size": 11,
        "cell_height": 1.12,
    },
]

PRESET_BY_ID = {p["id"]: p for p in PRESETS}
TERMINAL_APP = "终端"
DESKTOP_APP = "桌面"
GEDIT_APP = "gedit"
EDITOR_APP = "Trae"


class CommandError(RuntimeError):
    pass


# ── 命令与 gsettings 基础 ───────────────────────────────────────────────────
def _run(cmd, timeout=6):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def dconf_read(path):
    """读原始存储值；未显式设置时返回空串（用于区分「默认」与「被设过」）。"""
    r = _run([DCONF, "read", path])
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def gs_get(schema, key, path=None):
    target = "%s:%s" % (schema, path) if path else schema
    r = _run([GSETTINGS, "get", target, key])
    if r.returncode != 0:
        raise CommandError((r.stderr or r.stdout).strip() or "gsettings get 失败")
    return (r.stdout or "").strip()


def gs_set(schema, key, value, path=None):
    target = "%s:%s" % (schema, path) if path else schema
    r = _run([GSETTINGS, "set", target, key, value])
    if r.returncode != 0:
        raise CommandError((r.stderr or r.stdout).strip() or "gsettings set 失败")


def gs_reset(schema, key, path=None):
    target = "%s:%s" % (schema, path) if path else schema
    r = _run([GSETTINGS, "reset", target, key])
    if r.returncode != 0:
        raise CommandError((r.stderr or r.stdout).strip() or "gsettings reset 失败")


def unquote(raw):
    if raw is None:
        return ""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1].replace("\\'", "'")
    return raw


def parse_string_list(raw):
    return [unquote(x) for x in re.findall(r"'((?:[^'\\]|\\.)*)'", raw or "")]


def norm_color(value):
    value = (value or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return "#" + "".join(c * 2 for c in value[1:])
    return value


def color_arg(value):
    return "'%s'" % norm_color(value)


# ── 终端 profile ────────────────────────────────────────────────────────────
def terminal_profile_uuid(create=True):
    """取当前默认 profile；没有就建一个（GNOME Terminal 不能没有 profile）。"""
    raw = gs_get(TERMINAL_LIST_SCHEMA, "default")
    uuid = unquote(raw)
    if uuid:
        return uuid
    lst = parse_string_list(gs_get(TERMINAL_LIST_SCHEMA, "list"))
    if lst:
        return lst[0]
    if not create:
        return ""
    import uuid as _uuid
    uuid = str(_uuid.uuid4())
    gs_set(TERMINAL_LIST_SCHEMA, "list", "['%s']" % uuid)
    gs_set(TERMINAL_LIST_SCHEMA, "default", "'%s'" % uuid)
    return uuid


def terminal_path(uuid=None):
    return "%s:%s/" % (TERMINAL_BASE_PATH, uuid or terminal_profile_uuid())


# ── 可用性探测 ──────────────────────────────────────────────────────────────
def _theme_dirs():
    dirs = [os.path.join(HOME, ".themes"), os.path.join(HOME, ".local/share/themes")]
    for base in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if base:
            dirs.append(os.path.join(base, "themes"))
    return dirs


def gtk_theme_exists(name):
    return any(os.path.isfile(os.path.join(d, name, "index.theme")) for d in _theme_dirs())


def gsv_style_exists(name):
    for base in ("/usr/share/gtksourceview-5/styles",
                 "/usr/share/gtksourceview-4/styles",
                 os.path.join(HOME, ".local/share/gtksourceview-5/styles"),
                 os.path.join(HOME, ".local/share/gtksourceview-4/styles")):
        if os.path.isfile(os.path.join(base, "%s.xml" % name)):
            return True
    return False


def list_gtk_themes():
    names = set()
    for d in _theme_dirs():
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if os.path.isfile(os.path.join(d, n, "index.theme")):
                names.add(n)
    return sorted(names)


def installed_font_families():
    try:
        r = _run([FC_LIST, ":spacing=mono", "family"], timeout=8)
        mono = set()
        for line in (r.stdout or "").splitlines():
            for part in line.split(","):
                if part.strip():
                    mono.add(part.strip())
        r = _run([FC_LIST, ":spacing=proportional", "family"], timeout=8)
        prop = set()
        for line in (r.stdout or "").splitlines():
            for part in line.split(","):
                if part.strip():
                    prop.add(part.strip())
        return {"mono": mono, "prop": prop}
    except Exception:  # noqa: BLE001
        return {"mono": set(), "prop": set()}


def pick_family(kind, preferred):
    fams = installed_font_families()[kind]
    if not fams:
        return preferred
    for name in (preferred, "Noto Sans Mono" if kind == "mono" else "Noto Sans",
                 "DejaVu Sans Mono" if kind == "mono" else "DejaVu Sans"):
        if name in fams:
            return name
    return preferred


def _resolve_nls(ext_dir):
    """主题扩展的 label 是 %xxxLabel% 占位符，用 package.nls.json 还原成真实名字。"""
    for fn in ("package.nls.json", "package.nls.en.json"):
        p = os.path.join(ext_dir, fn)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                continue
    return {}


def editor_theme_names():
    """返回 Trae 实际可用的 colorTheme 值（即主题文件里的 name / settingsId）。"""
    names = []
    for root in TRAE_EXT_DIRS:
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            ext_dir = os.path.join(root, entry)
            pkg_path = os.path.join(ext_dir, "package.json")
            if not os.path.isfile(pkg_path):
                continue
            try:
                with open(pkg_path, encoding="utf-8") as f:
                    pkg = json.load(f)
            except (OSError, ValueError):
                continue
            themes = ((pkg.get("contributes") or {}).get("themes") or [])
            if not themes:
                continue
            nls = _resolve_nls(ext_dir)
            for t in themes:
                label = str(t.get("label") or "")
                if label.startswith("%") and label.endswith("%"):
                    label = str(nls.get(label.strip("%"), "") or "")
                # 优先用主题文件里的 name（VS Code 写进 settings.json 的就是它）
                rel = str(t.get("path") or "").lstrip("./")
                name = ""
                theme_file = os.path.join(ext_dir, rel)
                if rel and os.path.isfile(theme_file):
                    try:
                        with open(theme_file, encoding="utf-8") as f:
                            name = str(json.load(f).get("name") or "")
                    except (OSError, ValueError):
                        name = ""
                for candidate in (name, label, str(t.get("id") or "")):
                    if candidate:
                        names.append(candidate)
                        break
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def resolve_first(candidates, exists):
    for c in candidates:
        if exists(c):
            return c, True
    return (candidates[0] if candidates else ""), False


# ── 编辑器（Trae）配置 ──────────────────────────────────────────────────────
def editor_settings_path():
    for p in EDITOR_SETTINGS_CANDIDATES:
        if os.path.isfile(p):
            return p
    return ""


def read_editor_settings():
    path = editor_settings_path()
    if not path:
        return "", None, "找不到 Trae 的 settings.json"
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return path, json.loads(text), ""
    except ValueError as e:
        return path, None, "settings.json 不是合法 JSON（可能含注释），未改动：%s" % e
    except OSError as e:
        return path, None, "读不到 settings.json：%s" % e


def write_editor_settings(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".theme-manager.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def editor_active_theme():
    """从 Trae 的 state.vscdb 读它实际渲染的主题（settingsId 就是 settings.json 的值）。"""
    import sqlite3
    for p in EDITOR_STATE_DB_CANDIDATES:
        if not os.path.isfile(p):
            continue
        try:
            con = sqlite3.connect("file:%s?mode=ro" % p, uri=True, timeout=1.5)
            try:
                row = con.execute(
                    "select value from ItemTable where key='colorThemeData'").fetchone()
            finally:
                con.close()
            if row:
                data = json.loads(row[0])
                return {
                    "settings_id": data.get("settingsId") or "",
                    "label": data.get("label") or "",
                }
        except Exception:  # noqa: BLE001
            continue
    return None


# ── 备份 ────────────────────────────────────────────────────────────────────
def _now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect_state():
    """把「我们要改的东西」的当前原始值抓一份快照。"""
    uuid = terminal_profile_uuid(create=False)
    tpath = "%s:%s/" % (TERMINAL_BASE_PATH, uuid) if uuid else ""
    keys = {}
    if tpath:
        keys[TERMINAL_APP] = {k: dconf_read(tpath + k) for k in TERMINAL_KEYS}
    keys[DESKTOP_APP] = {k: dconf_read("/org/gnome/desktop/interface/%s" % k)
                         for k in INTERFACE_KEYS}
    keys[GEDIT_APP] = {k: dconf_read("/org/gnome/gedit/preferences/editor/%s" % k)
                       for k in GEDIT_KEYS}
    path, data, err = read_editor_settings()
    editor = {"path": path, "keys": {}, "content": None, "error": err}
    if data is not None:
        for k in ("workbench.colorTheme", "editor.fontFamily",
                  "editor.fontSize", "editor.lineHeight"):
            editor["keys"][k] = data.get(k)
        with open(path, encoding="utf-8") as f:
            editor["content"] = f.read()
    snapshot = {
        "terminal_profile": uuid,
        "terminal": keys.get(TERMINAL_APP, {}),
        "desktop": keys[DESKTOP_APP],
        "gedit": keys[GEDIT_APP],
        "editor": editor,
        "gtk_theme": unquote(gs_get(INTERFACE_SCHEMA, "gtk-theme")),
        "color_scheme": unquote(gs_get(INTERFACE_SCHEMA, "color-scheme")),
    }
    return snapshot


def _state_hash(snapshot):
    import hashlib
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def create_backup(trigger, preset_id, snapshot):
    stamp = _now_ts()
    dir_path = os.path.join(BACKUP_ROOT, stamp)
    n = 1
    while os.path.exists(dir_path):
        dir_path = os.path.join(BACKUP_ROOT, "%s_%d" % (stamp, n))
        n += 1
    os.makedirs(os.path.join(dir_path, "dconf"), exist_ok=True)
    os.makedirs(os.path.join(dir_path, "files"), exist_ok=True)

    manifest = {
        "created_at": time.time(),
        "created_text": _now_text(),
        "trigger": trigger,
        "preset": preset_id,
        "state_hash": _state_hash(snapshot),
        "terminal_profile": snapshot.get("terminal_profile", ""),
        "keys": {
            TERMINAL_APP: snapshot.get("terminal", {}),
            DESKTOP_APP: snapshot.get("desktop", {}),
            GEDIT_APP: snapshot.get("gedit", {}),
        },
        "editor": {
            "path": snapshot["editor"]["path"],
            "keys": snapshot["editor"]["keys"],
            "saved_file": "",
        },
    }

    # 另存一份 dconf dump 方便人工核对（还原用的是上面的精确键值）
    uuid = snapshot.get("terminal_profile") or ""
    dumps = {
        "terminal.ini": "%s:%s/" % (TERMINAL_BASE_PATH, uuid) if uuid else "",
        "interface.ini": "/org/gnome/desktop/interface/",
        "gedit.ini": "/org/gnome/gedit/preferences/editor/",
    }
    for fn, path in dumps.items():
        if not path:
            continue
        try:
            r = _run([DCONF, "dump", path], timeout=8)
            if r.returncode == 0:
                with open(os.path.join(dir_path, "dconf", fn), "w", encoding="utf-8") as f:
                    f.write(r.stdout or "")
        except Exception:  # noqa: BLE001
            pass

    content = snapshot["editor"].get("content")
    if content is not None:
        saved = os.path.join(dir_path, "files", "trae-settings.json")
        with open(saved, "w", encoding="utf-8") as f:
            f.write(content)
        manifest["editor"]["saved_file"] = "files/trae-settings.json"

    with open(os.path.join(dir_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return dir_path, manifest


def list_backups():
    out = []
    if not os.path.isdir(BACKUP_ROOT):
        return out
    for name in sorted(os.listdir(BACKUP_ROOT)):
        d = os.path.join(BACKUP_ROOT, name)
        mf = os.path.join(d, "manifest.json")
        if not os.path.isfile(mf):
            continue
        try:
            with open(mf, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            m = {}
        out.append({
            "name": name,
            "dir": d,
            "created_text": m.get("created_text", ""),
            "trigger": m.get("trigger", ""),
            "preset": m.get("preset", ""),
            "has_editor": bool((m.get("editor") or {}).get("saved_file")),
            "gtk_theme": unquote(m.get("keys", {}).get(DESKTOP_APP, {}).get("gtk-theme", "")),
            "bg": unquote(m.get("keys", {}).get(TERMINAL_APP, {}).get("background-color", "")),
            "fg": unquote(m.get("keys", {}).get(TERMINAL_APP, {}).get("foreground-color", "")),
        })
    return out


def original_backup():
    backups = list_backups()
    return backups[0] if backups else None


# ── 应用 ────────────────────────────────────────────────────────────────────
def _blend(fg_hex, bg_hex, alpha):
    """把 fg 按 alpha 叠在 bg 上（用于选区/光标底色）。"""
    def rgb(h):
        h = norm_color(h).lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    a, b = rgb(fg_hex), rgb(bg_hex)
    out = [int(round(a[i] * alpha + b[i] * (1 - alpha))) for i in range(3)]
    return "#" + "".join("%02X" % v for v in out)


def resolve_preset(preset_id, overrides=None):
    """预设 + 微调 → 最终要写入的值。"""
    preset = PRESET_BY_ID.get(preset_id) or PRESETS[0]
    ov = overrides or {}
    bg = norm_color(ov.get("bg") or preset["bg"])
    fg = norm_color(ov.get("fg") or preset["fg"])
    mono_size = int(ov.get("mono_size") or preset["mono_size"])
    ui_size = int(ov.get("ui_size") or preset["ui_size"])
    cell_height = float(ov.get("cell_height") or preset["cell_height"])
    mono_size = max(8, min(24, mono_size))
    ui_size = max(8, min(18, ui_size))
    cell_height = max(1.0, min(1.4, round(cell_height, 2)))
    return {
        "id": preset["id"],
        "name": preset["name"],
        "mode": preset["mode"],
        "bg": bg,
        "fg": fg,
        "accent": preset["accent"],
        "palette": preset["palette"],
        "mono_size": mono_size,
        "ui_size": ui_size,
        "cell_height": cell_height,
        "editor_line_height": round(cell_height * 1.35, 2),
        "selection_bg": _blend(preset["accent"], bg, 0.28),
        "cursor_fg": bg,
        "gtk_theme_candidates": preset["gtk_theme"],
        "color_scheme": preset["color_scheme"],
        "gedit_scheme_candidates": preset["gedit_scheme"],
        "editor_theme_candidates": preset["editor_theme"],
    }


def _write_and_verify(items):
    """items = [(app, item, key, gs_args, value, verify_fn)]，逐条写入并回读校验。"""
    report = []
    for app, item, key, spec, value, verify in items:
        rec = {"app": app, "item": item, "key": key, "value": value,
               "ok": False, "note": ""}
        try:
            _apply_spec(spec, value)
            rec["ok"] = bool(verify())
            if not rec["ok"]:
                rec["note"] = "写入后回读不一致"
        except CommandError as e:
            rec["note"] = str(e)
        except Exception as e:  # noqa: BLE001
            rec["note"] = "%s: %s" % (type(e).__name__, e)
        report.append(rec)
    return report


def _apply_spec(spec, value):
    kind = spec[0]
    if kind == "set":
        _, schema, key, path = spec
        gs_set(schema, key, value, path)
    elif kind == "file":
        raise CommandError("文件型配置不走这里")


def find_backup_by_hash(state_hash):
    """按状态哈希找已有备份（从新到旧）：来回切同一套配色时不重复堆目录。"""
    for b in reversed(list_backups()):
        try:
            with open(os.path.join(b["dir"], "manifest.json"), encoding="utf-8") as f:
                if json.load(f).get("state_hash") == state_hash:
                    return b
        except (OSError, ValueError):
            continue
    return None


def apply_theme(preset_id, overrides=None, skip_backup=False):
    want = resolve_preset(preset_id, overrides)
    snapshot = collect_state()
    backup = {"dir": "", "created": False, "reused": False, "reason": ""}

    if not skip_backup:
        hit = find_backup_by_hash(_state_hash(snapshot))
        if hit:
            backup.update({"dir": hit["dir"], "reused": True,
                           "reason": "当前配置与备份 %s 完全一致，直接复用它（不重复占空间）"
                                     % hit["name"]})
        else:
            d, _ = create_backup("apply:%s" % want["id"], want["id"], snapshot)
            backup.update({"dir": d, "created": True})

    mono_family = pick_family("mono", MONO_FONT_FAMILY)
    ui_family = pick_family("prop", UI_FONT_FAMILY)
    uuid = terminal_profile_uuid()
    tpath = terminal_path(uuid)
    items = []
    notes = []

    # ── GNOME Terminal ──
    T = TERMINAL_APP
    def t(k):
        return ("set", TERMINAL_PROFILE_SCHEMA, k, tpath)

    def tverify(key, expected, numeric=False):
        def _v():
            raw = gs_get(TERMINAL_PROFILE_SCHEMA, key, tpath)
            if numeric:
                try:
                    return abs(float(unquote(raw)) - float(expected)) < 1e-6
                except ValueError:
                    return False
            return unquote(raw).lower() == unquote(expected).lower()
        return _v

    items.append((T, "配色不要跟随 GTK 主题", "use-theme-colors", t("use-theme-colors"),
                  "false", tverify("use-theme-colors", "false")))
    items.append((T, "字体不使用系统默认", "use-system-font", t("use-system-font"),
                  "false", tverify("use-system-font", "false")))
    term_font = "%s %d" % (mono_family, want["mono_size"])
    items.append((T, "字体与字号", "font", t("font"), "'%s'" % term_font,
                  tverify("font", term_font)))
    items.append((T, "行高 cell-height-scale", "cell-height-scale", t("cell-height-scale"),
                  str(want["cell_height"]),
                  tverify("cell-height-scale", want["cell_height"], numeric=True)))
    items.append((T, "背景色", "background-color", t("background-color"),
                  color_arg(want["bg"]), tverify("background-color", want["bg"])))
    items.append((T, "前景色", "foreground-color", t("foreground-color"),
                  color_arg(want["fg"]), tverify("foreground-color", want["fg"])))
    items.append((T, "加粗色", "bold-color", t("bold-color"),
                  color_arg(want["accent"]), tverify("bold-color", want["accent"])))
    palette_arg = "[" + ", ".join("'%s'" % c for c in want["palette"]) + "]"
    items.append((T, "16 色盘", "palette", t("palette"), palette_arg,
                  lambda: [norm_color(c) for c in
                           parse_string_list(gs_get(TERMINAL_PROFILE_SCHEMA, "palette", tpath))]
                  == [norm_color(c) for c in want["palette"]]))
    items.append((T, "光标颜色", "cursor-colors-set", t("cursor-colors-set"), "true",
                  tverify("cursor-colors-set", "true")))
    items.append((T, "光标底色", "cursor-background-color", t("cursor-background-color"),
                  color_arg(want["accent"]), tverify("cursor-background-color", want["accent"])))
    items.append((T, "光标字色", "cursor-foreground-color", t("cursor-foreground-color"),
                  color_arg(want["cursor_fg"]), tverify("cursor-foreground-color", want["cursor_fg"])))
    items.append((T, "选区开关", "highlight-colors-set", t("highlight-colors-set"), "true",
                  tverify("highlight-colors-set", "true")))
    items.append((T, "选区底色", "highlight-background-color", t("highlight-background-color"),
                  color_arg(want["selection_bg"]),
                  tverify("highlight-background-color", want["selection_bg"])))
    items.append((T, "选区字色", "highlight-foreground-color", t("highlight-foreground-color"),
                  color_arg(want["fg"]), tverify("highlight-foreground-color", want["fg"])))

    # ── 桌面 GTK / 字体 ──
    D = DESKTOP_APP
    gtk, gtk_ok = resolve_first(want["gtk_theme_candidates"], gtk_theme_exists)
    if not gtk_ok:
        notes.append("预设想要的 GTK 主题 %s 本机都没装，桌面主题未改（终端/编辑器不受影响）"
                     % " / ".join(want["gtk_theme_candidates"]))
    else:
        if gtk != want["gtk_theme_candidates"][0]:
            notes.append("GTK 主题 %s 未安装，桌面改用最接近的 %s（桌面配色与终端色盘不完全一致）"
                         % (want["gtk_theme_candidates"][0], gtk))
        items.append((D, "GTK 主题", "gtk-theme", ("set", INTERFACE_SCHEMA, "gtk-theme", None),
                      "'%s'" % gtk,
                      lambda: unquote(gs_get(INTERFACE_SCHEMA, "gtk-theme")) == gtk))
    items.append((D, "深色/浅色偏好", "color-scheme", ("set", INTERFACE_SCHEMA, "color-scheme", None),
                  "'%s'" % want["color_scheme"],
                  lambda: unquote(gs_get(INTERFACE_SCHEMA, "color-scheme")) == want["color_scheme"]))
    ui_font = "%s %d" % (ui_family, want["ui_size"])
    items.append((D, "界面字体", "font-name", ("set", INTERFACE_SCHEMA, "font-name", None),
                  "'%s'" % ui_font,
                  lambda: unquote(gs_get(INTERFACE_SCHEMA, "font-name")) == ui_font))
    mono_font = "%s %d" % (mono_family, want["mono_size"])
    items.append((D, "等宽字体", "monospace-font-name",
                  ("set", INTERFACE_SCHEMA, "monospace-font-name", None),
                  "'%s'" % mono_font,
                  lambda: unquote(gs_get(INTERFACE_SCHEMA, "monospace-font-name")) == mono_font))

    # ── gedit ──
    G = GEDIT_APP
    scheme, scheme_ok = resolve_first(want["gedit_scheme_candidates"], gsv_style_exists)
    if not scheme_ok:
        notes.append("本机没有可用的 gedit 配色方案（%s 都不存在），gedit 只改了字体"
                     % " / ".join(want["gedit_scheme_candidates"]))
    else:
        if scheme != want["gedit_scheme_candidates"][0]:
            notes.append("gedit 配色方案 %s 本机没有，改用 %s"
                         % (want["gedit_scheme_candidates"][0], scheme))
        items.append((G, "配色方案", "scheme", ("set", GEDIT_SCHEMA, "scheme", None),
                      "'%s'" % scheme,
                      lambda: unquote(gs_get(GEDIT_SCHEMA, "scheme")) == scheme))
    items.append((G, "编辑器字体", "editor-font", ("set", GEDIT_SCHEMA, "editor-font", None),
                  "'%s'" % term_font,
                  lambda: unquote(gs_get(GEDIT_SCHEMA, "editor-font")) == term_font))

    report = _write_and_verify(items)

    # ── Trae（settings.json 是文件，单独处理）──
    editor_rec = apply_editor(want, mono_family)
    report.extend(editor_rec["items"])
    notes.extend(editor_rec["notes"])
    if editor_rec.get("applied_theme"):
        want["editor_theme_applied"] = editor_rec["applied_theme"]

    ok_count = sum(1 for r in report if r["ok"])
    result = {
        "ok": ok_count == len(report),
        "preset": want,
        "overrides": overrides or {},
        "backup": backup,
        "items": report,
        "ok_count": ok_count,
        "total": len(report),
        "notes": notes,
        "at": time.time(),
        "at_text": _now_text(),
        "terminal_profile": uuid,
        "fonts": {"mono": mono_family, "ui": ui_family},
    }
    _save_state({"last_apply": result, "state_after": collect_state_for_state(),
                 "preset": want["id"], "overrides": overrides or {}})
    return result


def apply_editor(want, mono_family):
    items, notes = [], []
    path, data, err = read_editor_settings()
    if data is None:
        items.append({"app": EDITOR_APP, "item": "settings.json", "key": "",
                      "value": path or "—", "ok": False, "note": err})
        return {"items": items, "notes": notes, "applied_theme": ""}

    available = editor_theme_names()
    theme, theme_ok = resolve_first(want["editor_theme_candidates"], lambda n: n in available)
    if not theme_ok:
        notes.append("Trae 里没有预设对应的主题（候选：%s），编辑器主题保持原样，只改了字体"
                     % " / ".join(want["editor_theme_candidates"]))
    else:
        if theme != want["editor_theme_candidates"][0]:
            notes.append("Trae 没有 %s，编辑器主题映射到最接近的内置主题 %s（语法色不完全相同）"
                         % (want["editor_theme_candidates"][0], theme))

    family = '"%s", "Noto Sans Mono", monospace' % mono_family
    new = dict(data)
    if theme_ok:
        new["workbench.colorTheme"] = theme
    new["editor.fontFamily"] = family
    new["editor.fontSize"] = want["mono_size"]
    new["editor.lineHeight"] = want["editor_line_height"]
    try:
        write_editor_settings(path, new)
    except OSError as e:
        items.append({"app": EDITOR_APP, "item": "settings.json", "key": "",
                      "value": path, "ok": False, "note": "写入失败：%s" % e})
        return {"items": items, "notes": notes, "applied_theme": ""}

    _, verify, _ = read_editor_settings()
    verify = verify or {}
    def vitem(item, key, expected):
        got = verify.get(key)
        return {"app": EDITOR_APP, "item": item, "key": key, "value": str(expected),
                "ok": got == expected,
                "note": "" if got == expected else "回读为 %r" % (got,)}

    if theme_ok:
        items.append(vitem("主题", "workbench.colorTheme", theme))
    items.append(vitem("编辑器字体", "editor.fontFamily", family))
    items.append(vitem("编辑器字号", "editor.fontSize", want["mono_size"]))
    items.append(vitem("编辑器行高", "editor.lineHeight", want["editor_line_height"]))

    # 真正生效需要 Trae 重载 settings.json；正在运行时它会在 1~2 秒内跟上
    active = None
    if theme_ok:
        deadline = time.time() + 3.0
        while time.time() < deadline:
            active = editor_active_theme()
            if active and active.get("settings_id") == theme:
                break
            time.sleep(0.4)
        rec = items[0]
        if active and active.get("settings_id") == theme:
            rec["note"] = "Trae 已加载（label=%s）" % active.get("label", "")
        elif active:
            rec["ok"] = False
            rec["note"] = ("Trae 当前渲染的主题是 %s，还没切到 %s；"
                           "多半需要重载窗口（Ctrl+Shift+P → Reload Window）或重启 Trae"
                           % (active.get("settings_id"), theme))
        else:
            rec["note"] = "读不到 Trae 的运行时状态（可能没在运行），重启后生效"
    return {"items": items, "notes": notes, "applied_theme": theme if theme_ok else ""}


def collect_state_for_state():
    """给「应用后状态」存一份精简快照，用于前端显示是否漂移。"""
    uuid = terminal_profile_uuid(create=False)
    tpath = terminal_path(uuid) if uuid else ""
    def gs(schema, key, path=None):
        try:
            return gs_get(schema, key, path)
        except CommandError:
            return ""
    return {
        "terminal": {k: gs(TERMINAL_PROFILE_SCHEMA, k, tpath) for k in TERMINAL_KEYS} if tpath else {},
        "desktop": {k: gs(INTERFACE_SCHEMA, k) for k in INTERFACE_KEYS},
        "gedit": {k: gs(GEDIT_SCHEMA, k) for k in GEDIT_KEYS},
        "editor": {k: v for k, v in (read_editor_settings()[1] or {}).items()
                   if k in ("workbench.colorTheme", "editor.fontFamily",
                            "editor.fontSize", "editor.lineHeight")},
        "gtk_theme": unquote(gs(INTERFACE_SCHEMA, "gtk-theme")),
    }


# ── 还原 ────────────────────────────────────────────────────────────────────
def restore_backup(name=None):
    backups = list_backups()
    if not backups:
        return {"ok": False, "error": "没有任何备份，无法还原"
                                     "（本服务只在应用主题前备份，没应用过就是原始状态）"}
    target = None
    if name:
        target = next((b for b in backups if b["name"] == name), None)
    if target is None:
        target = backups[0]          # 最早的那份 = 本服务动手前的原始状态
    mf_path = os.path.join(target["dir"], "manifest.json")
    with open(mf_path, encoding="utf-8") as f:
        manifest = json.load(f)

    items = []
    uuid = manifest.get("terminal_profile") or ""
    tpath = "%s:%s/" % (TERMINAL_BASE_PATH, uuid) if uuid else ""

    def restore_keys(app, schema, path, keys_raw, keys_all):
        for key in keys_all:
            raw = (keys_raw or {}).get(key, "")
            rec = {"app": app, "item": key, "key": key,
                   "value": unquote(raw) if raw else "（恢复默认）",
                   "ok": False, "note": ""}
            try:
                if raw:
                    gs_set(schema, key, raw, path)
                else:
                    gs_reset(schema, key, path)
                cur = gs_get(schema, key, path)
                rec["ok"] = True
                rec["note"] = "当前 %s" % unquote(cur)
            except CommandError as e:
                rec["note"] = str(e)
            except Exception as e:  # noqa: BLE001
                rec["note"] = "%s: %s" % (type(e).__name__, e)
            items.append(rec)

    if tpath:
        restore_keys(TERMINAL_APP, TERMINAL_PROFILE_SCHEMA, tpath,
                     (manifest.get("keys") or {}).get(TERMINAL_APP), TERMINAL_KEYS)
    restore_keys(DESKTOP_APP, INTERFACE_SCHEMA, None,
                 (manifest.get("keys") or {}).get(DESKTOP_APP), INTERFACE_KEYS)
    restore_keys(GEDIT_APP, GEDIT_SCHEMA, None,
                 (manifest.get("keys") or {}).get(GEDIT_APP), GEDIT_KEYS)

    # 编辑器：优先用原始文件整份写回（最精确），没有则按记录的键逐项回写
    ed = manifest.get("editor") or {}
    saved = ed.get("saved_file") or ""
    ed_path = ed.get("path") or editor_settings_path()
    if saved and ed_path:
        src = os.path.join(target["dir"], saved)
        if os.path.isfile(src):
            try:
                with open(src, encoding="utf-8") as f:
                    content = f.read()
                os.makedirs(os.path.dirname(ed_path), exist_ok=True)
                with open(ed_path, "w", encoding="utf-8") as f:
                    f.write(content)
                _, cur, _ = read_editor_settings()
                items.append({"app": EDITOR_APP, "item": "settings.json 整份还原", "key": "",
                              "value": ed_path, "ok": cur is not None,
                              "note": "已覆盖为备份内容" if cur is not None else "回读失败"})
            except OSError as e:
                items.append({"app": EDITOR_APP, "item": "settings.json 整份还原", "key": "",
                              "value": ed_path, "ok": False, "note": "写入失败：%s" % e})
    elif ed.get("keys") and ed_path:
        try:
            with open(ed_path, encoding="utf-8") as f:
                data = json.load(f)
            for key, val in ed["keys"].items():
                if val is None:
                    data.pop(key, None)
                else:
                    data[key] = val
            write_editor_settings(ed_path, data)
            items.append({"app": EDITOR_APP, "item": "settings.json 键还原", "key": "",
                          "value": ed_path, "ok": True, "note": ""})
        except (OSError, ValueError) as e:
            items.append({"app": EDITOR_APP, "item": "settings.json 键还原", "key": "",
                          "value": ed_path, "ok": False, "note": "失败：%s" % e})

    ok_count = sum(1 for i in items if i["ok"])
    result = {
        "ok": ok_count == len(items) and bool(items),
        "restored_from": target["name"],
        "backup_dir": target["dir"],
        "items": items,
        "ok_count": ok_count,
        "total": len(items),
        "at": time.time(),
        "at_text": _now_text(),
    }
    _save_state({"last_restore": result, "restored_from": target["name"],
                 "preset": None, "overrides": {}})
    return result


# ── 状态持久化 ──────────────────────────────────────────────────────────────
def _save_state(patch):
    data = {}
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data.update(patch)
    data["updated_at"] = time.time()
    data["updated_text"] = _now_text()
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state():
    if not os.path.isfile(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def current_summary():
    """当前实际值（前端「当前状态」区用）。"""
    uuid = terminal_profile_uuid(create=False)
    tpath = terminal_path(uuid) if uuid else ""
    def gs(schema, key, path=None):
        try:
            return unquote(gs_get(schema, key, path))
        except CommandError:
            return ""
    term = {}
    if tpath:
        term = {
            "font": gs(TERMINAL_PROFILE_SCHEMA, "font", tpath),
            "cell_height": gs(TERMINAL_PROFILE_SCHEMA, "cell-height-scale", tpath),
            "bg": gs(TERMINAL_PROFILE_SCHEMA, "background-color", tpath),
            "fg": gs(TERMINAL_PROFILE_SCHEMA, "foreground-color", tpath),
            "use_theme_colors": gs(TERMINAL_PROFILE_SCHEMA, "use-theme-colors", tpath),
            "palette": [norm_color(c) for c in
                        parse_string_list(gs(TERMINAL_PROFILE_SCHEMA, "palette", tpath))],
        }
    _, edata, ederr = read_editor_settings()
    edata = edata or {}
    return {
        "terminal": term,
        "desktop": {
            "gtk_theme": gs(INTERFACE_SCHEMA, "gtk-theme"),
            "color_scheme": gs(INTERFACE_SCHEMA, "color-scheme"),
            "font": gs(INTERFACE_SCHEMA, "font-name"),
            "mono_font": gs(INTERFACE_SCHEMA, "monospace-font-name"),
        },
        "gedit": {
            "scheme": gs(GEDIT_SCHEMA, "scheme"),
            "font": gs(GEDIT_SCHEMA, "editor-font"),
        },
        "editor": {
            "path": editor_settings_path(),
            "theme": edata.get("workbench.colorTheme"),
            "font_family": edata.get("editor.fontFamily"),
            "font_size": edata.get("editor.fontSize"),
            "line_height": edata.get("editor.lineHeight"),
            "error": ederr,
        },
    }


def capabilities():
    fams = installed_font_families()
    return {
        "gsettings": os.path.isfile(GSETTINGS),
        "dconf": os.path.isfile(DCONF),
        "gtk_themes": list_gtk_themes(),
        "editor_themes": editor_theme_names(),
        "fonts_mono": sorted(fams["mono"]),
        "fonts_prop": sorted(fams["prop"]),
        "editor_settings": editor_settings_path(),
        "backup_root": BACKUP_ROOT,
        "state_path": STATE_PATH,
    }


def drift_report():
    """和上次应用后的状态比，看有没有被别的东西改掉（GNOME 更新、手动设置等）。"""
    state = load_state()
    after = state.get("state_after")
    if not after:
        return {"has_baseline": False, "changed": []}
    now = collect_state_for_state()
    changed = []
    for app in ("terminal", "desktop", "gedit"):
        base = after.get(app) or {}
        for key, val in (now.get(app) or {}).items():
            if key in base and base[key] != val:
                changed.append({"app": app, "key": key,
                                "expected": unquote(base[key]), "now": unquote(val)})
    base_ed = after.get("editor") or {}
    for key, val in (now.get("editor") or {}).items():
        if key in base_ed and base_ed[key] != val:
            changed.append({"app": "editor", "key": key,
                            "expected": str(base_ed[key]), "now": str(val)})
    return {"has_baseline": True, "changed": changed}
