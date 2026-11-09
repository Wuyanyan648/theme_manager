# theme_manager —— 统一配色与字体管理

一个本地小服务（`127.0.0.1:8790`）：把 **GNOME Terminal、桌面 GTK / 字体、gedit、Trae** 的配色与字体
收成一套「预设 + 少量微调」，一键应用、一键还原。解决的是「黑底白字/白底黑字对比度 21:1，看久了累」这件事。

- 端口固定 `8790`（8760 门户 / 8765 屏幕 / 8787 网络都没占它）。
- 托管方式：**systemd 用户单元** `theme-manager.service`，登录自启，`Restart=on-failure`。
- 只用 Python 标准库 + 系统自带 `gsettings` / `dconf`，不需要 root，不装第三方包。
- 应用前自动备份原始配置；「还原」按备份逐键写回，**原本没显式设置的键会 `gsettings reset`**，
  真正回到动手之前的状态（已实测，见文末验证记录）。

## 快速开始

```bash
cd ~/eric/wuyan_github/local_service/theme_manager

# 常驻（systemd 用户单元 + 登录自启），无需 sudo
./install-autostart.sh

# 前台调试（会打开浏览器）
./start.sh

# 命令行
python3 backend/theme_server.py --list                # 预设清单
python3 backend/theme_server.py --apply nord          # 直接应用
python3 backend/theme_server.py --status              # 当前实际值
python3 backend/theme_server.py --backups             # 备份列表
python3 backend/theme_server.py --restore             # 还原到最早的一份备份

# 卸载（只停服务，不动配色）
./uninstall-autostart.sh
```

界面：<http://127.0.0.1:8790/>

## 界面

- **预设卡片**：6 个方案，卡片上直接给 16 色盘的色块与前景/背景示例字。
- **微调**：背景色、前景色、等宽字号、界面字号、终端行高；「微调归零」回到预设原值。
- **应用**：逐项写入后**立即回读校验**，清单里只有写进去且读回一致的才打 ✓，不一致打 ✗ 并写原因。
  部分能力缺失（例如 Trae 没有对应主题、GTK 主题没装）会在「备注」里说明，不会假装成功。
- **还原**：`还原本机原始配置` = 按**最早**那份备份还原；备份表里也可以选任意一份「还原到这里」。
- **当前实际值 / 漂移提示**：把 gsettings 与 Trae 的 settings.json 现值摊开；若与上次应用后的快照不一致
  （GNOME 更新、手动改设置），顶部会提示哪几项被改掉了，重新「应用」即可覆盖回来。

## 预设与实际色值

每个预设同时定义：终端 16 色 + 前景/背景/加粗（强调）色、GTK 主题取向、编辑器主题、gedit 配色方案。
下面是**本机实测解析出的值**（候选列表里第一个真实存在的）。

### 1. 暖灰浅色 `warm-gray`

- 前景 `#3E3934` / 背景 `#F0ECE5` / 强调 `#8C6E4A`，行高 1.12
- 16 色：`#3E3934 #A8422E #5E7B45 #96742B #3C6E8F #87587A #3F7D77 #CFC7BA #6E675E #C05B3F #75935A #B08C3C #4F82A6 #9E6F92 #549B94 #FBF9F5`
- GTK：`Yaru-bark`（浅）· color-scheme `default` · gedit `Yaru` · Trae `Quiet Light`

### 2. 石墨深色 `graphite`

- 前景 `#CDD1D6` / 背景 `#21242A` / 强调 `#7FA8CC`
- 16 色：`#21242A #C96A62 #6FA36B #C2A055 #6A93B8 #A87EA8 #5EA0A0 #BFC5CC #6B7280 #DA8078 #83B57F #D2B26A #7FA8CC #BC93BC #74B4B4 #EDF0F3`
- GTK：`Adwaita-dark` · color-scheme `prefer-dark` · gedit `Adwaita-dark` · Trae `Default Dark Modern`

### 3. Gruvbox 深色 `gruvbox-dark`

- 前景 `#EBDBB2` / 背景 `#282828` / 强调 `#D79921`
- 16 色：`#282828 #CC241D #98971A #D79921 #458588 #B16286 #689D6A #A89984 #928374 #FB4934 #B8BB26 #FABD2F #83A598 #D3869B #8EC07C #EBDBB2`
- GTK：`Yaru-bark-dark` · `prefer-dark` · gedit `oblivion` · Trae `Kimbie Dark`（**近似**，见局限）

### 4. Nord `nord`

- 前景 `#D8DEE9` / 背景 `#2E3440` / 强调 `#88C0D0`
- 16 色：`#3B4252 #BF616A #A3BE8C #EBCB8B #81A1C1 #B48EAD #88C0D0 #E5E9F0 #4C566A #BF616A #A3BE8C #EBCB8B #81A1C1 #B48EAD #8FBCBB #ECEFF4`
- GTK：`Yaru-blue-dark` · `prefer-dark` · gedit `Adwaita-dark` · Trae `Default Dark Modern`（**近似**）

### 5. One Dark `one-dark`

- 前景 `#ABB2BF` / 背景 `#282C34` / 强调 `#61AFEF`
- 16 色：`#282C34 #E06C75 #98C379 #E5C07B #61AFEF #C678DD #56B6C2 #ABB2BF #5C6370 #E06C75 #98C379 #E5C07B #61AFEF #C678DD #56B6C2 #FFFFFF`
- GTK：`Yaru-dark` · `prefer-dark` · gedit `Adwaita-dark` · Trae `Default Dark Modern`（**近似**）

### 6. Solarized 浅沙 `solarized-light`

- 前景 `#657B83` / 背景 `#FDF6E3` / 强调 `#268BD2`
- 16 色：`#073642 #DC322F #859900 #B58900 #268BD2 #D33682 #2AA198 #EEE8D5 #002B36 #CB4B16 #586E75 #657B83 #839496 #6C71C4 #93A1A1 #FDF6E3`
- GTK：`Yaru-sage` · `default` · gedit `solarized-light` · Trae `Solarized (light)`

> 微调只允许改背景色、前景色、等宽字号、界面字号、行高；其他色（16 色盘、加粗/光标/选区）始终跟预设走，
> 避免调出一套「自己都看不清」的组合。选区底色由强调色按 28% 叠在背景上算出来。

## 覆盖范围

| 应用 | 改什么 | 怎么改 | 生效方式 |
| --- | --- | --- | --- |
| GNOME Terminal | 16 色盘、前景/背景/加粗色、光标色、选区色、字体、字号、行高 `cell-height-scale` | `gsettings`（`org.gnome.Terminal.Legacy.Profile`，path 指向默认 profile） | 立即生效（终端监听 gsettings） |
| GNOME 桌面 | `gtk-theme`、`color-scheme`、`font-name`、`monospace-font-name` | `gsettings`（`org.gnome.desktop.interface`） | 立即生效；已开着的 GTK 应用多数会跟着重绘 |
| gedit | GtkSourceView 配色方案、编辑器字体 | `gsettings`（`org.gnome.gedit.preferences.editor`） | 重开文件/窗口生效 |
| Trae（VS Code 系） | `workbench.colorTheme`、`editor.fontFamily`、`editor.fontSize`、`editor.lineHeight` | 直接改 `~/.config/Trae CN/User/settings.json` | 运行中的 Trae 会 1~2 秒内热加载（服务会去 `state.vscdb` 核对它真的换了） |

**刻意不碰**（安全边界）：

- 显示器分辨率 / 缩放 / 亮度 / 色温 —— 属于 `screen` 服务（8765）；
- `org.gnome.desktop.wm.preferences` 里的窗口管理器键（标题栏字体等）；
- `screen` 服务的任何状态文件；
- shell 的 `.bashrc` / `.zshrc` / `.profile`；
- LibreOffice 的 `registrymodifications.xcu`。

## 备份与还原

- 根目录：`~/.local/share/theme-manager-backup/<YYYYmmdd_HHMMSS>/`
- 每次「应用」前抓一份快照，内容：
  - `manifest.json`：每个键的**原始 GVariant 值**（空串表示原本没显式设置）、终端 profile UUID、
    Trae settings.json 的关键键值、状态哈希（用于判断「和上次备份一致」就复用，不重复堆目录）；
  - `dconf/{terminal,interface,gedit}.ini`：`dconf dump` 出来的可读副本，方便人工核对；
  - `files/trae-settings.json`：编辑器配置的整份拷贝（还原时整份覆盖，最精确）。
- 还原逻辑：终端 / 桌面 / gedit 只回写**本服务管的那几项**（不整目录 `dconf load`，避免把后来改的
  图标主题等一并抹掉）；原本为空的键执行 `gsettings reset` → 回到 schema 默认值；编辑器整份覆盖。
- 「还原本机原始配置」按**时间最早**的那份备份还原；单份备份也可以单独还原。
- 备份不会被还原流程删除；要腾空间手动删 `~/.local/share/theme-manager-backup/<时间戳>` 即可。

## 做不到 / 只有部分生效

1. **Trae 没有 Gruvbox / Nord / One Dark 的官方主题**。这些预设的编辑器部分映射到最接近的内置主题
   （Gruvbox → `Kimbie Dark`，Nord / One Dark → `Default Dark Modern`），语法高亮颜色**与终端色盘不完全一致**，
   界面上会明确写「映射到 …」。要完全一致只能另装对应主题扩展，再改预设候选列表第一项。
2. **GTK 主题只能用本机已装的**（Yaru 各配色 + Adwaita），不会为每个预设生成一套 GTK 主题，
   所以桌面控件的配色与终端 16 色盘只是「同一取向」，不是逐色相同。候选缺失时会写进备注。
3. **LibreOffice 不吃 GTK 配色**：它的界面字体大致跟随系统字体，但文档颜色要它自己的
   「工具 → 选项 → 应用程序颜色」，本服务不动它的 `registrymodifications.xcu`（改坏影响面太大）。
4. **Electron 系应用（含 Trae）** 改完 `settings.json` 一般热加载；个别窗口 / 扩展视图要
   `Ctrl+Shift+P → Reload Window` 或重启才完全跟上。Trae 没运行时无法核对它是否真的换了主题，会在备注里写「重启后生效」。
5. **行高**：GNOME Terminal 用 VTE 的 `cell-height-scale`（0.9~2.0，本服务限制在 1.0~1.4），不是所有终端模拟器都支持；
   编辑器用 `editor.lineHeight`，两者不是同一套渲染，视觉上只是接近。
6. **gedit 的配色方案**来自 `/usr/share/gtksourceview-5/styles`，本机没有 Gruvbox / Nord 风格，只能用
   `oblivion` / `Adwaita-dark` 近似。
7. **窗口已开着时的刷新**：GTK 主题与字体变化后，Nautilus、gedit 等可能需要重开窗口；已经渲染的网页不受影响。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 门户健康检查 |
| GET | `/api/state` | 预设、当前值、能力探测、备份列表、上次应用/还原报告、漂移检测 |
| POST | `/api/apply` | `{"preset":"nord","overrides":{"bg":"#2E3440","mono_size":13,"cell_height":1.2}}` |
| POST | `/api/restore` | `{}` 还原本机原始配置；`{"backup":"20261110_060626"}` 还原指定备份 |

返回结构里 `result.items[]` 是逐项回读结果（`ok` / `value` / `note`），`result.notes[]` 是「哪些没完全做到」。

## 运行期文件

| 路径 | 用途 |
| --- | --- |
| `~/.local/share/theme-manager/state.json` | 上次应用的预设、微调、报告、应用后快照（漂移检测用） |
| `~/.local/share/theme-manager-backup/` | 备份 |
| `~/.config/systemd/user/theme-manager.service` | 用户单元（由 `install-autostart.sh` 写入） |

## 依赖

- Ubuntu 24.04 / GNOME 46（X11 或 Wayland 都可以，本服务不碰显示输出）
- `python3`（3.12）、`gsettings`、`dconf`
- 字体：`Ubuntu Sans` / `Ubuntu Sans Mono`（本机已装；缺了会退到 `Noto Sans*` → `DejaVu Sans*`）
- Trae CN 安装在默认路径（`~/.config/Trae CN/User/settings.json`），找不到就只跳过编辑器部分

## 验证记录（本机，2026-11-10）

1. **首次应用前备份**：`~/.local/share/theme-manager-backup/20261110_060626/`，manifest 里终端 14 个键全为空串
   （说明终端当时全是 schema 默认值）、桌面 `gtk-theme='Yaru-blue-dark'`、`color-scheme='prefer-dark'`、
   gedit `scheme='Yaru-dark'`、Trae `workbench.colorTheme='Dark'` 且没有任何字体键。
2. **应用 `graphite`（CLI）**：24/24 项回读一致；`gsettings get` 复核到 `#21242A / #CDD1D6 / Adwaita-dark /
   Ubuntu Sans Mono 12 / cell-height-scale 1.12`；Trae 的 `state.vscdb` 里 `colorThemeData.settingsId`
   变成 `Default Dark Modern`（说明它真的换了，不只是文件写了）。
3. **应用 `nord` + 微调 13pt / 行高 1.2（HTTP）**：24/24 一致；外部复核 `monospace-font-name='Ubuntu Sans Mono 13'`、
   `cell-height-scale=1.2`、Trae `editor.fontSize=13`、`editor.lineHeight=1.62`。
4. **还原**：21/21 项成功；终端 14 个键全部 `gsettings reset` 回默认（`dconf read` 为空），
   桌面回到 `Yaru-blue-dark / prefer-dark`，gedit 回到 `Yaru-dark`，
   `diff 备份的 trae-settings.json 当前 settings.json` → **完全一致**。
5. **systemd 用户单元**：`systemctl --user is-active theme-manager` → `active`；
   单元环境下 `gsettings` 写入正常（用户管理器的 `DBUS_SESSION_BUS_ADDRESS` 可用）。

## 端口与自启

- 固定 `127.0.0.1:8790`，被占用时打印原因并以退出码 3 退出（不漂移，书签不会失效）。
- 单元 `theme-manager.service`：`WantedBy=default.target`、`Restart=on-failure`、`SuccessExitStatus=3`。
- 不需要 autostart 桌面项：本服务是纯 HTTP，不依赖 X11；配色本身写在 dconf 与 settings.json 里，
  **重启后自动保持**，登录后服务只是随时待命供你调整。
- 门户登记：`screen/portal/services.json` 里的 `theme-manager` 一条（`user-unit`，可显示状态 / 延迟 /
  CPU / 内存并启停）。
