# 翁彥斌 · 工业设计作品集 v2

## 设计风格
**极简黑白**：纯白底、墨黑文字、细线分隔，大留白、大图叙事，强调材质真实感与设计过程。

## 文件结构
```
portfolio-v2/
├── index.html              # 封面 + 项目导航
├── about.html              # 个人简介、技能、经历
├── methodology.html        # 我的设计方法论
├── projects/
│   ├── dslr.html           # 01 模块化单反相机
│   ├── headphones.html     # 02 头戴式监听耳机
│   ├── cat-nest.html       # 03 面向独居青年的智能猫窝
│   └── offroad-toy.html    # 04 越野车玩具（仿真收藏级模型）
├── css/style.css           # 全部样式与响应式布局
├── js/main.js              # 导航、移动端菜单、图片灯箱
├── assets/images/          # 原始渲染 + AI 场景图
├── build_pdf_v3.py         # PDF 导出（v3.1，Playwright + reportlab）
└── pdf/                    # 合并后的 PDF 版本
```

## 如何编辑
- 直接修改 `.html` 文件中的文字内容即可。
- 样式统一在 `css/style.css` 中调整。
- 项目卡片图片、场景图、素模图统一放在 `assets/images/`。
- **建议替换为真实素材的位置**：
  - `about.html` 中的个人照片占位
  - 每个项目页中的「草图迭代板 · 请替换为个人手绘草图」

## 如何预览
1. 在 `portfolio-v2` 文件夹下运行本地服务器：
   ```bash
   python -m http.server 8000
   ```
2. 浏览器打开 `http://localhost:8000/index.html`。

## 如何导出 PDF
主力脚本为 `build_pdf_v3.py`（v3.1）：Playwright 驱动本机 Edge 整页截图 → 按横向 A4 比例切片 → reportlab 合成单 PDF（约 53 页，含封面 + 4 个项目 + 方法论）。也可直接用浏览器打开任一页面按 `Ctrl + P` 另存为 PDF。旧版 `build_pdf_v2.py`（print 分页法，已弃用）与 `build_pdf.py` 保留作历史对照。

## AI 辅助说明
- 封面与项目列表的「场景氛围渲染图」和用户「使用场景图」为 AI 辅助生成，用于统一视觉氛围。
- 每个项目页同时保留了原始 Rhino / Keyshot 输出的素模、线框与最终渲染，以保证真实感。

## 目标岗位
工业设计师 · 智能硬件方向
