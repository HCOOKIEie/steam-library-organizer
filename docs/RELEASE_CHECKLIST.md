# v1.1.2 Release Checklist

本清单用于构建面向 Windows 10/11 x64 的正式发布包。目标是让构建结果只包含应用真正需要的组件，避免从 Anaconda、用户级 `site-packages` 或日常开发环境中误收集模块。

## 1. 构建机与源码

- [ ] 使用从 python.org 安装的 **CPython 3.13.2 x64**，不要使用 Anaconda/Miniconda。
- [ ] 工作区位于干净提交；确认 `git status --short` 中没有来源不明的修改。
- [ ] 确认构建 Python：

  ```powershell
  py -3.13-64 -c "import platform, sys; print(sys.executable); print(sys.version); print(platform.machine(), 8 * __import__('struct').calcsize('P'))"
  ```

  输出应指向 CPython 3.13.2，并显示 `AMD64 64`；路径中不应出现 `Anaconda`、`Miniconda` 或其他项目的虚拟环境。

## 2. 锁定依赖

- [ ] `requirements-lock.txt` 来自 CPython 3.13.2 x64 的纯净环境，且与 `requirements.txt` 的直接依赖约束一致。
- [ ] 如果需要更新依赖，先在一次性干净环境中完成安装、测试和许可核对，再更新锁文件；不要在正式构建过程中临时升级版本。
- [ ] 可在正式构建前人工验证锁文件：

  ```powershell
  py -3.13-64 -m venv .venv-release
  .\.venv-release\Scripts\python.exe -m pip install -r requirements-lock.txt
  .\.venv-release\Scripts\python.exe -m pip check
  ```

- [ ] 禁止继承系统包：检查 `.venv-release\pyvenv.cfg` 中 `include-system-site-packages = false`。
- [ ] 保存 `pip list --format=freeze` 的输出，并与 `requirements-lock.txt` 核对。构建脚本也会生成 `BUILD-DEPENDENCIES.txt`。
- [ ] `where.exe python` 仅用于诊断；后续测试和构建必须始终调用 `.venv-release\Scripts\python.exe` 的绝对或仓库相对路径。

## 3. 自动验证

- [ ] 运行回归测试、Python 编译检查和前端语法检查：

  ```powershell
  .\.venv-release\Scripts\python.exe -m unittest discover -s tests -v
  .\.venv-release\Scripts\python.exe -m py_compile steam_modern.py steam_desktop.py steam_settings.py steam_appinfo.py steam_library_core.py steam_web.py
  node --check steam_ui\app.js
  node --check steam_ui\theme-bootstrap.js
  npm ci --ignore-scripts --no-audit --no-fund
  npm test
  ```

- [ ] 完整回归测试全部通过；在 Release Notes 中记录最终测试数量。
- [ ] GitHub Actions 的冻结包步骤成功构建 onedir，并确认 WebView2、tkinter、前端资源和 VC 运行库均存在。
- [ ] 扫描仓库和构建输出，确认不存在 API Key、访问令牌、真实 SteamID、用户名专属绝对路径或个人 Steam 数据。

## 4. 构建发布包

- [ ] 使用仓库脚本完成安全清理、隔离环境、测试、打包和哈希生成：

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1 -Version 1.1.2 -Layout Both
  ```

- [ ] 推荐分发 `SteamLibraryOrganizer-1.1.2-win-x64-portable.zip`；压缩包内入口名为 `SteamLibraryOrganizer.exe`。`SteamLibraryOrganizer-1.1.2-win-x64.exe` 是单文件便携备选。
- [ ] 解压并核对 portable ZIP，确认 `README.md`、项目级 `LICENSE`、`THIRD_PARTY_NOTICES.md` 与完整的 `THIRD_PARTY_LICENSES/` 均已包含。
- [ ] 检查 `.build\pyinstaller-release\onefile\SteamLibraryOrganizer\` 与 `.build\pyinstaller-release\onedir\SteamLibraryOrganizer\` 下的 `Analysis-00.toc`、`EXE-00.toc` 和构建日志：所有 Python 包必须来自 `.venv-release` 或 CPython 3.13.2 标准库；不得出现 Anaconda、用户级 `AppData\Roaming\Python\...\site-packages`、旧虚拟环境或无关项目路径。
- [ ] 确认产物为 x64，并确认未意外打包 Qt、CEF、测试框架、科学计算套件等未使用组件；同时确认 tkinter 兼容回退所需模块完整保留。
- [ ] 构建脚本会为发布目录生成 `SHA256SUMS.txt`；再次用 `Get-FileHash` 人工抽查 portable ZIP 和单文件 EXE。
- [ ] `-Layout Both` 自动调用 `scripts/verify_release.py` 核对两种包中的资源与源码、版本和 ZIP 完整性，生成 `BUILD-VERIFICATION.json`；单独检查可运行 `.\.venv-release\Scripts\python.exe scripts/verify_release.py --version 1.1.2`。

## 5. 干净系统冒烟测试

至少在一台不是构建机的干净 Windows 设备或虚拟机上完成。测试时使用可还原的测试账号/测试数据，先自行备份 Steam `userdata`；不要首次就在主力收藏夹上执行写入。

- [ ] Windows 10 x64：启动、扫描、生成预览、退出 Steam 后写入、重启 Steam 验证、恢复备份。
- [ ] Windows 11 x64：完成同一流程。
- [ ] WebView2 已安装：内嵌界面正常启动，不打开外部浏览器，不监听本地 HTTP 端口。
- [ ] WebView2 缺失或损坏：程序自动切换到内置 tkinter 兼容界面，核心扫描、预览、写入和恢复仍可用；非默认 Steam 目录可以手动选择，并在重启后继续生效。
- [ ] Steam 默认路径与自定义路径均可发现；路径含空格及 Windows 用户名含非 ASCII 字符时仍可运行。
- [ ] Steam 正在运行时，写入和恢复被阻止；扫描与预览仍保持只读。
- [ ] 手工收藏夹保留；工具管理的自动分类可重复更新，不产生重复或损坏记录。
- [ ] 浅色/深色、缩放、键盘焦点以及系统“减少动态效果”均无明显回归。
- [ ] 1220×840 默认窗口、980×680 最小窗口和 125%/150% 系统缩放下，设置与预览可滚动，底部操作可达；原生标题栏与界面主题一致。
- [ ] 三组预设、设置持久化、搜索无结果、筛选后批量勾选、切换目录清空旧预览及预览生成失败均符合预期。
- [ ] 陈列室 / RELOAD / P5R / 简约外观均可使用，分别检查亮色、深色与 980×680 最小窗口；切换外观不清空搜索、规则或预览勾选。关闭后重启保留外观选择。
- [ ] 入场转场会自行结束，装饰层不拦截输入；“减少动态效果”和系统设置能停止动画及视差。原生冻结包包含 `p3r.css`、`p5r.css`、`vault.css`、`appearance.js`、`vault.js`、`persona-motion.js`、`persona-motion.css`、两幅本地人物插图及 Anton / Barlow 字体与许可。P3R 双圆转场在暂停、离屏和审阅时清除遮罩。
- [ ] 离线预览始终显示“示例数据”，不能写入、恢复或打开真实 Steam 目录；不得将其当成可整理真实数据的桌面版分发。
- [ ] `%LOCALAPPDATA%\SteamLibraryOrganizer\steam_modern.log` 不含密钥或令牌。日志可能包含本机路径、Steam 账号标识和错误堆栈；提醒用户反馈问题前先检查并脱敏，不要直接公开上传。

Windows on ARM、32 位 Windows、Windows 7/8.1 不在 v1.1.2 支持范围内；如仅在兼容层上偶然可运行，也不要在 Release Notes 中承诺支持。

## 6. 发布内容与说明

- [ ] GitHub Release 包含推荐的 portable ZIP、单文件 EXE 备选、`SteamLibraryOrganizer-1.1.2-third-party-licenses.zip`、`SHA256SUMS.txt` 与 `BUILD-DEPENDENCIES.txt`；portable ZIP 内也包含 README 和完整第三方许可。
- [ ] Release 页面明确提醒：下载单文件 EXE 时，应同时下载并保留同版本的第三方许可包；portable ZIP 已内置这些文件。
- [ ] `THIRD_PARTY_NOTICES.md` 中的版本与 `requirements-lock.txt` 以及最终 TOC 一致。
- [ ] 不把 `.venv-release/`、`build/`、`dist/`、`steam_appinfo_cache.json`、真实备份或日志打入发布包。
- [ ] Release 标题和标签使用 `v1.1.2`；注明“Windows 10/11 x64”“新界面需要 WebView2，缺失时回退兼容界面”“未签名，可能出现 SmartScreen 提醒”。
- [ ] 明确声明本项目不是 Valve/Steam 官方产品；不要使用暗示官方授权或背书的措辞。
- [ ] 项目采用 MIT 许可证；确认 portable ZIP 和单文件 EXE 配套许可包均包含根目录 `LICENSE`，并保留第三方组件各自的许可文件与声明。
- [ ] 正式产物只存放在 `dist/release/` 并上传 Release；不向 Git 提交 EXE、ZIP、构建缓存或旧版入口。

## 发布说明

本版说明见 [v1.1.2](releases/v1.1.2.md)。
