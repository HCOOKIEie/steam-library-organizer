# 应用图标

三张归拢的游戏卡盒，石墨灰底、薄荷色主体。窗口、任务栏、网页页签和软件标题区共用这一图形，四种界面风格保留各自配色。

- `steam_ui/art/app-icon-master.png`：带透明通道的原始图稿。
- `steam_ui/art/app-icon.png`：256 px 网页与界面资源。
- `steam_ui/art/app-icon.ico`：16、20、24、32、40、48、64、128、256 px Windows 图标。

图稿通过内置 imagegen 生成；PNG 缩放和 ICO 转换使用 Pillow。Pillow 仅用于制作资源，不是软件运行依赖。打包时由 PyInstaller 嵌入 EXE，桌面 HTML 内嵌 PNG，无需网络加载。

生成提示词：

> Use case: logo-brand. Asset: a finished original Windows desktop app icon for Steam Library Organizer, a game library organization utility. ONE icon, square canvas, actual transparency outside tile. No letters, no text, no watermark. A dark graphite softly rounded square tile filling 90 percent of canvas. In the center, an original strong geometric symbol of three neatly gathered game cases: two slim upright mint spines at left and a wider pale-mint front case at right, whose upper outer corner has a precise diagonal cut. The front case includes one small dark rectangular inset near its upper third to read as a game case rather than a chart. Aligned bottom edges, orderly library silhouette, elegant spacing, slight overlap, generous outer breathing space. Two mint tones maximum plus charcoal. Mostly flat vector-like form, extremely subtle material bevel only on outer tile. Premium desktop productivity utility, crisp and recognizable at 24 pixels. No bar chart, no controller, no Steam logo, no circles, no sparkles, no neon, no busy decoration, no shadows outside tile, no mockup scene or presentation sheet.
