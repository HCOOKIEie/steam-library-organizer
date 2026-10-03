# Steam Library Organizer

一个只读取本机 Steam 客户端数据、先生成安全预览、再备份并写入 Steam 收藏夹的 Windows 桌面工具。

默认流程是：读取数据 → 选择分类规则 → 审阅并勾选预览 → 退出 Steam 后备份写入。默认启用“首字母 + 游戏类型”，也支持条目形式、开发商、发行商、安装状态、最近游玩和游玩时长。

## 下载

从 [GitHub Releases](https://github.com/luyaoting114514-arch/steam-library-organizer/releases/latest) 下载最新版 `SteamLibraryOrganizer.exe`。本项目暂未购买 Windows 代码签名证书，因此首次运行时 SmartScreen 可能显示提醒；可用同一 Release 中的 SHA-256 文件核对下载内容。

运行桌面版需要 Microsoft Edge WebView2 Runtime；Windows 10/11 通常已预装。

## 启动

双击 `启动Steam分类工具.bat`，或直接运行 `SteamLibraryOrganizer.exe`。

正式版使用 WebView2 嵌入式桌面窗口：不会打开外部浏览器，也不会启动或监听 HTTP 服务。Windows 10/11 通常已包含 WebView2 Runtime；源码模式在运行环境缺少它时可回退到旧的 tkinter 界面，单文件 EXE 则会给出明确的修复提示。

程序会从注册表和常见安装位置自动寻找 Steam。识别失败时，可点击窗口左上角的 Steam 路径选择正确目录；选择会保存到 `%LOCALAPPDATA%\SteamLibraryOrganizer\settings.json`。

使用源码运行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe steam_modern.py
```

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
legacy/                    早期实现，仅供追溯
```

`steam_appinfo_cache.json` 是从本机 Steam 缓存生成的加速文件；删除后会在下次扫描时重建。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m py_compile steam_modern.py steam_desktop.py steam_appinfo.py steam_library_core.py steam_web.py
node --check steam_ui\app.js
```

当前版本包含 40 项标准库回归测试。发布前实机验证仅执行读取与预览，不执行真实写入。

当前公开版本：`v1.0.0`。Windows EXE 尚未进行代码签名。

打包 Windows EXE：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean .build\SteamLibraryOrganizer.spec
```
