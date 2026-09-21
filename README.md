# 工业设计作品集 · Industrial Design Portfolio

> **4 个完整项目 + 可旋转的 3D 白模交互**——用网页把"设计过程"而不是"效果图"讲出来。
> Static portfolio site: 4 projects, real KeyShot/Rhino renders, and an interactive 3D white-model viewer.

**在线地址 / Live**: <https://57fe846e3730424ab2d3fae23fd838e9.app.workbuddy.link/index.html>

## 项目一览

| # | 项目 | 说明 |
|---|---|---|
| 01 | **模块化单反相机 DSLR** | 造型推敲 + CMF 表达，多视角渲染 |
| 02 | **头戴式监听耳机** | 素模 / 线框推敲到成品渲染的完整迭代 |
| 03 | **面向独居青年的智能猫窝** | 智能硬件：使用场景、结构爆炸图、产品智能管家 |
| 04 | **越野车玩具** | 仿真收藏级玩具的结构可行性 + 3D 白模在线交互（three.js） |

每个项目统一叙事结构：**问题定义 → 调研 → 概念 → 迭代 → 最终方案**。
整体版式为 Editorial Material 风格：暖白底、大地色强调、大留白、大图叙事。

## 硬规则（自我约束）

1. 主图必须是 **Rhino / KeyShot 真实渲染**——AI 只用于场景氛围，不代替产品表达
2. 图片严格保持**原始长宽比**，禁止拉伸变形
3. 每个项目讲清"为什么这样改"，而不是只放最终效果图

**AI 辅助说明（诚实标注）**：封面与项目列表的「场景氛围渲染图」「使用场景图」为 AI 辅助生成，仅用于统一视觉氛围；每个项目页同时保留原始 Rhino / KeyShot 输出的素模、线框与最终渲染，以保证真实感。

## 技术实现

```
index.html / about.html / methodology.html   静态站点（零框架）
projects/*.html                              4 个项目详情页
css/style.css                                全部样式与响应式布局
js/main.js                                   导航、移动端菜单、图片灯箱
js/three-viewer.js                           three.js + OrbitControls 白模交互模块
assets/models/toy-car.obj + .mtl             可旋转 3D 白模
build_pdf_v2.py                              Playwright + Python PDF 导出管线（网页版与投递版同源）
qa.py                                        页面结构自检脚本
```

- **3D 白模交互**：three.js + OBJLoader / OrbitControls，对应 JD 里"用 3D 辅助展示提升产品设计维度与写实感"的诉求
- **PDF 导出管线**：Playwright 逐页渲染 → PDF 重排与校验，保证投递版与网页版内容一致
- 全站无构建工具、无外部运行时依赖，静态文件直接部署

## 本地预览

```bash
python -m http.server 8000
# 浏览器打开 http://localhost:8000/index.html
```

## 作者

**翁彥斌（Tearimi）** · 厦门工学院 产品设计 · 2026 届
所有渲染图与建模均为本人完成 · 更多作品见 [GitHub 主页](https://github.com/Teamirni)
