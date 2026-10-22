# 开发文档

- [界面设计](DESIGN.md)：四种主题的视觉规范与交互。
- [产品范围](PRODUCT.md)：本地整理流程与产品约束。
- [简约主题](calm-interface.md)：黑白与荧光绿、互动卡片和方格背景。
- [P3R 动效参考](p3r-motion-reference.md)与[人物插画来源](persona-art-prompts.md)。
- [发布检查清单](RELEASE_CHECKLIST.md)：隔离构建、自动验证及实机验收。
- [v1.1.1 发布说明](releases/v1.1.1.md)。

构建脚本和 PyInstaller 配置位于 `scripts/`；临时构建文件位于 `.build/`；
最终文件位于 `dist/release/`，界面预览位于 `dist/previews/`，这些生成目录不进入 Git。
旧版 `legacy/` 入口和根目录 EXE 已从源码树移除，可通过 Git 历史追溯。
