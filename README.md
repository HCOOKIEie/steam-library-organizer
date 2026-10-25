# Steam Library Organizer

一个只读取本机 Steam 客户端数据、先生成安全预览、再备份并写入 Steam 收藏夹的 Windows 桌面工具。它是社区个人项目，与 Valve 或 Steam 官方无隶属、授权或背书关系。

默认流程是：读取数据 → 选择分类规则 → 审阅并勾选预览 → 退出 Steam 后备份写入。默认启用“首字母 + 游戏类型”，也支持条目形式、开发商、发行商、安装状态、最近游玩和游玩时长。

当前版本为 **v1.1.2**，更新内容见 [CHANGELOG.md](CHANGELOG.md)。旧版 v1.1.0 / v1.1.1 已撤回。Windows 程序统一从 GitHub Releases 下载；仓库保留源码，本地构建产物集中在 `dist/release/`。构建与验收步骤见 [发布检查清单](docs/RELEASE_CHECKLIST.md)。

## 下载

从 [GitHub Releases](https://github.com/HCOOKIEie/steam-library-organizer/releases/latest) 下载最新版。推荐下载 `SteamLibraryOrganizer-<版本>-win-x64-portable.zip`，完整解压后运行其中的 `SteamLibraryOrganizer.exe`；该压缩包已包含第三方许可。单文件 `SteamLibraryOrganizer-<版本>-win-x64.exe` 是便携备选，但启动时需要先解包到临时目录，更容易触发杀毒软件的启发式检查；选择单文件版时，请同时下载并保留同版本的 `SteamLibraryOrganizer-<版本>-third-party-licenses.zip`。正式发布包面向 **64 位 Windows 10/11**；Windows 7/8.1、32 位 Windows 与 Windows on ARM 均未列入支持范围。

单文件版正常退出时会自动清理临时解包目录；系统崩溃或强制结束进程时可能留下临时文件。担心系统盘空间或杀毒软件误报时，优先使用 portable ZIP，并在程序完全退出后再通过 Windows 临时文件清理功能处理残留。

本项目暂未购买 Windows 代码签名证书，因此首次运行时 SmartScreen 可能显示“Windows 已保护你的电脑”。请只从本仓库 Release 下载，并用同一 Release 中的 SHA-256 文件核对内容；这项提醒不等于文件已被确认有害。

完整的新界面需要 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)；Windows 10/11 通常已预装。WebView2 缺失或损坏时，正式 EXE 会自动切换到内置 tkinter 兼容界面；安装或修复 Evergreen Runtime 后即可恢复新界面。

## 启动

下载 portable ZIP 的用户应先完整解压，不要只把 EXE 单独移出文件夹；然后运行其中的 `SteamLibraryOrganizer.exe`。仓库中的 `启动Steam分类工具.bat` 主要给源码开发环境使用。旧版入口已移除，历史实现仍可通过 Git 历史查看。

正式版优先使用 WebView2 嵌入式桌面窗口：不会打开外部浏览器，也不会启动或监听 HTTP 服务。源码模式和正式 EXE 均包含 tkinter 兼容回退界面，因此 WebView2 启动失败时仍能完成核心操作。

程序会从注册表和常见安装位置自动寻找 Steam。识别失败时，可点击窗口左上角的 Steam 路径选择正确目录；选择会保存到 `%LOCALAPPDATA%\SteamLibraryOrganizer\settings.json`。

使用源码运行：

```powershell
py -3.13-64 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe steam_modern.py
```

可复现发布构建使用 CPython 3.13.2 x64 的全新虚拟环境；精确版本见 `requirements-lock.txt`，发布流程见 [发布检查清单](docs/RELEASE_CHECKLIST.md)。不要从 Anaconda、系统全局 site-packages 或日常开发环境直接打包。

运行日志保存在 `%LOCALAPPDATA%\SteamLibraryOrganizer\steam_modern.log`。

## 新桌面界面

- 源码与本地预览的默认外观 **光域** 提供棱阵 / 游流 / 回响三种原创空间：立体三角切面、12,000 点空间流与连续驻波网格。背景覆盖窗口，支持鼠标局部抬升、点击 / 键盘波动、暂停及静态回退；选择会被记住，审阅时停帧。这些场景已纳入 v1.1.2 EXE 和便携包。详见 [光域设计](docs/lightfield-interface.md)。
- “光域 / 分类预览”切换保留规则、搜索和勾选；生成预览后进入完整审阅区。所有现有分类、备份、写入及恢复保护继续生效。
- 新主题不使用远程字体、游戏封面服务或前端运行依赖。光域画面由本地代码生成，不代表用户游戏库中的真实游戏封面。
- 保留 **RELOAD 蓝调**：P3R 风格启发的海蓝色平面设计，配蓝白色块概括的主角侧颜、缓慢浮动和大块水面折光；标题采用离线 Anton 直立粗体，配坐标及纵向大字。
- **P5R 红黑** 替代原行记主题：红黑与纸白拼贴、离线 Barlow Condensed 斜体大字、斜切选中态，配告示卡、漫画星形、速度线和顶部字条。生成预览后，首屏海报让位于完整分类审阅区；配黑白红概括的 Joker 侧颜，不含提取的游戏素材或音乐。
- 顶栏提供 **光域 / RELOAD / P5R / 简约** 四种外观；界面风格会被记住，切换不清空规则、搜索或预览勾选。已有用户保存的外观偏好继续保留，原行记偏好自动迁移至 P5R。
- RELOAD 包含约 720ms 的有限入场转场、菜单悬停与选中反馈、约 480ms 的预览切入和分组错峰展开。视差仅作用于装饰层，不移动正文或控件。
- P3R 参考原版菜单实录，点击人物或重播时由两个错峰展开的圆形窗口显示首页画面，水光贯穿标题与人物区域；P5R 使用黑白漫画星形冲击与速度切口，配海报翻入和轻微视差。特效限于首页画面，不覆盖分类文字、统计和按钮。首页提供“重播动效 / 暂停动效”，暂停偏好会保存。参考与实现区别见 [P3R 动效记录](docs/p3r-motion-reference.md)。
- P3R 水光在画面可见时以约 30fps 缓慢运行，P5R 互动动效在闲置后停止；两套主题离屏或窗口隐藏时停止；生成分类预览后隐藏背景画布和动效控制，保留完整审阅空间。始终遵循系统和应用的减少动效设置。侧颜为 AI 生成的同人插画，离线内嵌，生成提示见 `docs/persona-art-prompts.md`。
- “更多操作 → 减少动态效果”可以关闭动画与视差，也始终遵循系统减少动态效果设置；没有界面音效或自动播放音频。
- 双栏工作台：左侧设置范围与规则，右侧查看统计、预览和操作结果。
- 支持跟随系统的亮色/深色主题，也可在界面中手动切换并记住选择。
- 原生 Windows 标题栏随界面主题切换；使用系统控件字体、本地展示字体、矢量图形和轻量过渡。
- 提供“推荐 / 轻量整理 / 游玩习惯”三组预设，自动记住分类方式、范围、名称语言和厂商门槛。
- 支持搜索分类或已展示的示例游戏；搜索时全选、取消及分组勾选只作用于匹配结果。
- 连接失败、空预览和搜索无结果都有明确说明；重新扫描及生成失败后会阻止旧预览写入。
- 遵循系统“减少动态效果”设置；键盘、焦点、对比度和屏幕阅读器语义均保留。
- SteamID 默认脱敏，完整账号只在用户主动点击后临时显示。
- 历史界面参考来源与第三方许可保留在 `THIRD_PARTY_NOTICES.md`。

### 无需 Steam 的界面预览

```powershell
python scripts\preview_ui.py --export dist\previews\SteamLibraryOrganizer-ui-preview.html
```

双击导出的 HTML 即可离线体验主题、规则、搜索和勾选。页面明确标记“示例数据”，所有写入、恢复及系统操作都会拒绝执行。示例使用虚构账号和 24 个游戏条目；不读取真实游戏库。`--scenario running`、`empty`、`error`、`plan-error` 可导出对应状态。厂商门槛等真实分类行为以桌面版为准。

也可运行 `python scripts\preview_ui.py --port 8761` 启动仅绑定 `127.0.0.1` 的开发预览服务。

简约采用白灰 / 灰黑表面与蓝色操作强调，精简重复说明，移除卡片演示和背景 Canvas。动效集中在选中滑块、按钮按压和预览过渡，支持中途改向、闲置停帧与减少动态效果。用 `python scripts/preview_ui.py --export dist/previews/Calm-preview.html --appearance calm` 导出体验，具体说明见 [简约主题设计](docs/calm-interface.md)。这轮改版已纳入 v1.1.2 桌面版。

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
steam_modern.py            WebView2 桌面外壳与受控 Python 接口
steam_desktop.py           tkinter 兼容回退界面
steam_settings.py          两套桌面界面共用的本机设置
steam_library_core.py      扫描、分类、备份、写入和恢复
steam_appinfo.py           Steam appinfo.vdf 离线解析器
steam_web.py               开发与回归用本地服务
steam_ui/                  嵌入式 HTML/CSS/JavaScript 界面
THIRD_PARTY_NOTICES.md     Uiverse 来源与第三方许可
THIRD_PARTY_LICENSES/      发布包所含第三方组件的完整许可文本
scripts/                   构建、校验与只读预览工具
docs/                      设计、产品与发布文档
tests/                     Python 与前端回归测试
dist/release/              本地构建产物（不进入 Git）
dist/previews/             本地界面预览（不进入 Git）
```

`steam_appinfo_cache.json` 是从本机 Steam 缓存生成的加速文件；删除后会在下次扫描时重建。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m py_compile steam_modern.py steam_desktop.py steam_settings.py steam_appinfo.py steam_library_core.py steam_web.py
node --check steam_ui\app.js
node --check steam_ui\theme-bootstrap.js
npm ci --ignore-scripts --no-audit --no-fund
npm test
```

Node.js 22 与 jsdom 仅用于开发期的前端回归测试，不会随桌面程序打包，也不是最终用户的运行依赖。前端测试验证 DOM 行为，不替代 WebView2 的视觉与实机验收。

发布要求完整回归测试全部通过。自动测试会覆盖临时测试数据上的写入与恢复；正式发布还应在隔离的测试账号/可还原数据上完成实机冒烟测试，不要直接拿主力收藏夹做首次验证。

`v1.1.2` 的正式发布继续要求 CPython 3.13.2 x64 纯净虚拟环境和锁定依赖；兼容回退界面支持选择并记住非默认 Steam 目录。支持范围仍是 Windows 10/11 x64，Windows EXE 尚未进行代码签名。

构建 Windows 发布包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1 -Version 1.1.2 -Layout Both
```

构建机还需安装 Node.js，用于在打包前检查内嵌界面的 JavaScript 语法。脚本会新建 `.venv-release`、安装 `requirements-lock.txt`、运行测试、编译检查 Python、检查 JavaScript、构建推荐的 onedir ZIP 与单文件备选、复制许可文件并生成 SHA-256；同时会删除旧版曾写在 `dist\SteamLibraryOrganizer.exe` 的歧义产物，正式上传只使用 `dist\release\`。发布前仍应检查构建日志与 PyInstaller TOC，确认路径不含 Anaconda、用户级 `site-packages` 或其他工作区。完整步骤见 [发布检查清单](docs/RELEASE_CHECKLIST.md)。

## 开源许可

本项目采用 [MIT 许可证](LICENSE)。第三方依赖、字体与素材仍遵循各自的许可证，完整声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 `THIRD_PARTY_LICENSES/`。
