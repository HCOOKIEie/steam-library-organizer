# Steam Library Organizer

一个只读取本机 Steam 客户端数据、先生成安全预览、再备份并写入 Steam 收藏夹的 Windows 桌面工具。它是社区个人项目，与 Valve 或 Steam 官方无隶属、授权或背书关系。

默认流程是：读取数据 → 选择分类规则 → 审阅并勾选预览 → 退出 Steam 后备份写入。默认启用“首字母 + 游戏类型”，也支持条目形式、开发商、发行商、安装状态、最近游玩和游玩时长。

## 下载

从 [GitHub Releases](https://github.com/HCOOKIEie/steam-library-organizer/releases/latest) 下载最新版。推荐下载 `SteamLibraryOrganizer-<版本>-win-x64-portable.zip`，完整解压后运行其中的 `SteamLibraryOrganizer.exe`；该压缩包已包含第三方许可。单文件 `SteamLibraryOrganizer-<版本>-win-x64.exe` 是便携备选，但启动时需要先解包到临时目录，更容易触发杀毒软件的启发式检查；选择单文件版时，请同时下载并保留同版本的 `SteamLibraryOrganizer-<版本>-third-party-licenses.zip`。正式发布包面向 **64 位 Windows 10/11**；Windows 7/8.1、32 位 Windows 与 Windows on ARM 均未列入支持范围。

单文件版正常退出时会自动清理临时解包目录；系统崩溃或强制结束进程时可能留下临时文件。担心系统盘空间或杀毒软件误报时，优先使用 portable ZIP，并在程序完全退出后再通过 Windows 临时文件清理功能处理残留。

本项目暂未购买 Windows 代码签名证书，因此首次运行时 SmartScreen 可能显示“Windows 已保护你的电脑”。请只从本仓库 Release 下载，并用同一 Release 中的 SHA-256 文件核对内容；这项提醒不等于文件已被确认有害。

完整的新界面需要 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)；Windows 10/11 通常已预装。WebView2 缺失或损坏时，正式 EXE 会自动切换到内置 tkinter 兼容界面；安装或修复 Evergreen Runtime 后即可恢复新界面。

## 启动

下载 portable ZIP 的用户应先完整解压，不要只把 EXE 单独移出文件夹；然后运行其中的 `SteamLibraryOrganizer.exe`。仓库中的 `启动Steam分类工具.bat` 主要给源码开发环境使用；`legacy/` 是早期实现的存档，不应作为正式入口，也不要用它处理真实 Steam 数据。

正式版优先使用 WebView2 嵌入式桌面窗口：不会打开外部浏览器，也不会启动或监听 HTTP 服务。源码模式和正式 EXE 均包含 tkinter 兼容回退界面，因此 WebView2 启动失败时仍能完成核心操作。

程序会从注册表和常见安装位置自动寻找 Steam。识别失败时，可点击窗口左上角的 Steam 路径选择正确目录；选择会保存到 `%LOCALAPPDATA%\SteamLibraryOrganizer\settings.json`。

使用源码运行：

```powershell
py -3.13-64 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe steam_modern.py
```

可复现发布构建使用 CPython 3.13.2 x64 的全新虚拟环境；精确版本见 `requirements-lock.txt`，发布流程见 `RELEASE_CHECKLIST.md`。不要从 Anaconda、系统全局 site-packages 或日常开发环境直接打包。

运行日志保存在 `%LOCALAPPDATA%\SteamLibraryOrganizer\steam_modern.log`。

## 新桌面界面

- 单窗口工作台，不跳转浏览器；扫描、规则、预览、写入状态保持在同一视图。
- 支持跟随系统的亮色/深色主题，也可在界面中手动切换并记住选择。
- 包含状态轨道、按钮流光、卡片悬浮、勾选形变、加载反馈、抽屉与弹层动效。
- 遵循系统“减少动态效果”设置；键盘、焦点、对比度和屏幕阅读器语义均保留。
- SteamID 默认脱敏，完整账号只在用户主动点击后临时显示。
- 动效交互参考 Uiverse 社区组件并统一重绘，作者与 MIT 许可见 `THIRD_PARTY_NOTICES.md`。

## 安全边界

- 扫描和生成预览不会修改 Steam。
- 真正写入前必须完全退出 Steam。
- 写入只修改当前账号的收藏夹文件，并先生成备份。
- 恢复前也会保存当前状态；再次恢复可撤销上一次恢复。
- 普通历史备份与恢复撤销快照分别保留，互不挤占。
- 手工创建的收藏夹会保留；工具只替换自己管理的自动分类。
- 预览计划有时限并绑定本地 Steam 数据状态；数据变化后必须重新预览。
- 正式桌面版不启动本地网页服务。`steam_web.py` 仅用于开发与回归预览。
- 不修改游戏文件、许可证或登录信息。
- 最终版使用本地 `appinfo.vdf` 获取名称和元数据，不需要 Steam Web API Key。不要把 API Key 写进项目或聊天记录；若旧 Key 曾经公开过，请在 Steam 后台撤销并重建。

## 项目结构

```text
SteamLibraryOrganizer.exe  可直接运行的 Windows 桌面版
steam_modern.py            WebView2 桌面外壳与受控 Python 接口
steam_desktop.py           tkinter 兼容回退界面
steam_library_core.py      扫描、分类、备份、写入和恢复
steam_appinfo.py           Steam appinfo.vdf 离线解析器
steam_web.py               开发与回归用本地服务
steam_ui/                  嵌入式 HTML/CSS/JavaScript 界面
THIRD_PARTY_NOTICES.md     Uiverse 来源与第三方许可
THIRD_PARTY_LICENSES/      发布包所含第三方组件的完整许可文本
RELEASE_CHECKLIST.md       v1.0.1 可复现构建与发布检查清单
legacy/                    早期实现，仅供追溯，请勿用于真实数据
```

`steam_appinfo_cache.json` 是从本机 Steam 缓存生成的加速文件；删除后会在下次扫描时重建。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m py_compile steam_modern.py steam_desktop.py steam_appinfo.py steam_library_core.py steam_web.py
node --check steam_ui\app.js
```

发布要求完整回归测试全部通过。自动测试会覆盖临时测试数据上的写入与恢复；正式发布还应在隔离的测试账号/可还原数据上完成实机冒烟测试，不要直接拿主力收藏夹做首次验证。

`v1.0.1` 的发布构建改用 CPython 3.13.2 x64 纯净虚拟环境和锁定依赖，避免把 Anaconda 或开发机中的无关模块混入 EXE；支持范围仍是 Windows 10/11 x64。Windows EXE 尚未进行代码签名。

构建 Windows 发布包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1 -Version 1.0.1 -Layout Both
```

脚本会新建 `.venv-release`、安装 `requirements-lock.txt`、运行测试、构建推荐的 onedir ZIP 与单文件备选、复制第三方许可并生成 SHA-256。发布前仍应检查构建日志与 PyInstaller TOC，确认路径不含 Anaconda、用户级 `site-packages` 或其他工作区。完整步骤见 `RELEASE_CHECKLIST.md`。

## 许可状态

依赖和界面参考素材的许可见 `THIRD_PARTY_NOTICES.md` 与 `THIRD_PARTY_LICENSES/`。仓库目前尚未选择项目级 `LICENSE`，因此当前状态是 **source-available（源码公开可查看）**，并非已经采用 OSI 认可许可证的正式开源项目。在项目级许可证确定前，不应将本项目描述为已采用 MIT、Apache-2.0、GPL 等许可证。
