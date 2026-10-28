# -*- coding: utf-8 -*-
"""翁彥斌作品集 v2 · PDF 生成脚本 v3.1（像素级还原网页 + 零裁切分页）

策略：Playwright 驱动本机 Edge 逐页「整页截图」→ 按横向 A4 比例切片 → reportlab
把每片以 JPEG 全幅嵌进横向 A4 页 → 拼成单 PDF。

分页算法（v3.1 重写，修复「图片/卡片/统计数字被切」）：
  旧版的 bug：候选安全位不足时回退到「理想位置」任意下刀，直接切进图片与卡片。
  新版改为「禁越区间 + 最大填充」：
    1) JS 采集两类信息——
         safe[]      ：可下刀的候选位（章节上下沿、容器直接子块上下沿、原子元素上下沿）
         forbidden[] ：不可跨越的区间（图片/卡片/统计行等原子元素；标题与其紧随内容）
    2) 过滤掉落在 forbidden 内的候选位；
    3) 每页取「不超过一页高的最大安全位」（最大化填充，且绝不切进受保护元素）；
       若整页都无安全位（单个元素比一页还高），才按页高硬切并在报告中标注。

为何不用 print-to-pdf（旧 v2）：宽幅连续滚动网页塞进窄高 A4 竖版必重排失真；
为何不用 Edge --screenshot：它只拍视口高度、不拍整页（实测被静默截断）。

降级处理（截图不吃 @media print，均在 style.css 的 body.pdf-export 模式里完成）：
- 隐藏 .nav/.mobile-menu/.footer/.ticker-band / 越野车 #viewer-section（无法交互）
- 封面 / about hero 固定为一张横向 A4 页高
- 中和 motion.css 的滚动揭示隐藏起点
- 收紧过胖 section 间距，限制图片高度

用法：build_pdf_v3.py            → 横向 A4 定高版（每页标准 A4，页底可能留白）
      build_pdf_v3.py --seamless → 无缝版（每页按内容实际高度，无页底留白，页高不一）
产物：portfolio-v2/pdf/翁彥斌-作品集.pdf（或 -无缝版.pdf），同步复制到工作区根与 D:\\工作文件\\
"""
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent.resolve()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not Path(EDGE).exists():
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

RENDER_W = 1280          # 网页原生桌面宽（容器 max-width 1280 正好铺满，无多余留白）
DPR = 2                  # 设备缩放，保证清晰
PAGE_PX_W = RENDER_W * DPR            # 2560
SLICE_PX_H = round(PAGE_PX_W / (2 ** 0.5))   # 1810 ≈ 横向 A4 比例
SLICE_CSS_H = SLICE_PX_H / DPR        # 905 CSS px
JPEG_QUALITY = 86

# 阅读顺序：首页(封面+简介+项目总览) → 关于我 → 4 个项目页 → 方法论
PAGES = [
    ("index.html", "index"),
    ("about.html", "about"),
    ("projects/offroad-toy.html", "toy"),
    ("projects/cat-nest.html", "catnest"),
    ("projects/headphones.html", "headphones"),
    ("projects/dslr.html", "dslr"),
    ("methodology.html", "methodology"),
]

# 尽早给 <body> 注入 pdf-export 类（在页面脚本运行前），触发 style.css 的降级模式
INIT_JS = (
    "(()=>{var a=function(){if(document.body){document.body.classList.add('pdf-export');}"
    "else{requestAnimationFrame(a);}};a();})();"
)

# 分页测量：采集「可下刀位」与「禁越区间」
JS_MEASURE = r"""
() => {
  const PAGE = 905;
  /* 原子元素：整块不可跨越（图片/统计行/卡片/引用/时间线条目/阶段头……） */
  const ATOMIC = ['.cover', '.about-hero', '.figure', '.image-row', '.stat-row',
                  '.project-card', '.quote-block', '.failed-concept', '.meta-item',
                  '.timeline-list > li', '.skill-bar', '.stage-header',
                  '.capability-matrix', '.cap-item', '.deliverable-strip',
                  '.concept-card', '.process-step'];
  const safe = [];
  const forbidden = [];
  const addSafe = (t) => { if (isFinite(t)) safe.push(Math.round(t * 10) / 10); };
  const forbid = (t, b) => { if (b - t > 4) forbidden.push([t, b]); };
  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return [r.top + window.scrollY, r.bottom + window.scrollY];
  };
  const q = (sel, root) => Array.from(root.querySelectorAll(sel));
  /* 只认块级盒：inline / inline-block 的上下沿不是合法分页位
     （否则会在 <strong>/<span> 中间下刀，把一行文字切成两半） */
  const isBlock = (el) => {
    const d = getComputedStyle(el).display;
    return d !== 'none' && !d.startsWith('inline');
  };

  // 1) 原子元素：整块不可跨越
  ATOMIC.forEach(sel => q(sel, document).forEach(el => {
    const [t, b] = rect(el);
    addSafe(t); addSafe(b); forbid(t, b);
  }));

  // 2) 所有块级元素的上下沿 → 候选分页位（落在禁越区间内的稍后会被过滤）
  //    注意用 body *：index.html 的正文直接在 <header> 之后、没有包 <main>，
  //    而 .nav/.footer 等在 pdf-export 下 display:none，其子孙会被 isBlock 自然排除。
  q('body *', document).forEach(el => {
    if (!isBlock(el)) return;
    const [t, b] = rect(el);
    if (b - t < 3) return;
    addSafe(t); addSafe(b);
  });

  // 3) 标题 / label：与紧随内容的前几行绑定（keep-with-next，避免孤立标题）
  q('h1, h2, h3, h4, .label', document).forEach(el => {
    const [t, b] = rect(el);
    addSafe(t); addSafe(b);
    const nx = el.nextElementSibling;
    if (nx) {
      const [nt, nb] = rect(nx);
      const glue = Math.min(b + 72, nb);   // 至少带上下一个块的开头几行
      if (glue > t + 4) { addSafe(glue); forbid(t, glue); }
    }
  });

  return {safe: safe, forbidden: forbidden,
          scrollHeight: document.documentElement.scrollHeight};
}
"""


def file_url(path: str) -> str:
    return "file://" + urllib.request.pathname2url(path)


def _snap_int(b: float, forbidden: list, lo: int, hi: int) -> int:
    """把边界取整，且保证不落入任何禁越区间内部。
    int(round()) 可能把「贴在元素下沿的边界」舍进去零点几 px，
    本函数负责把他推到区间外沿（贴上沿→下取整，贴下沿→上取整）。"""
    c = int(round(b))
    for (t, bo) in forbidden:
        if t < c < bo:
            up, dn = int(bo) + 1, int(t)
            if up <= hi and (dn < lo or abs(up - c) <= abs(c - dn)):
                if up > lo:
                    return up
            if dn > lo:
                return dn
            break
    return c


def _finalize(bnd_floats, forbidden, H):
    """浮点边界 → 整数边界（去重、保序、补齐首尾、微调避开禁越区间）。"""
    out = []
    Hi = int(round(H))
    for b in bnd_floats:
        bi = _snap_int(b, forbidden, (out[-1] if out else -1) + 1, Hi)
        if out and bi <= out[-1]:
            bi = int(round(b))          # 保底：不因微调产生零长页
            if bi <= out[-1]:
                continue
        out.append(bi)
    if not out or out[0] != 0:
        out.insert(0, 0)
    if out[-1] != Hi:
        out[-1] = Hi
    return out


def smart_boundaries(total_css_h: float, safe_pts: list, forbidden: list,
                     verbose_name: str = ""):
    """生成切片边界（CSS px）。

    两步走：
    1) 过滤：丢掉所有落在 forbidden 区间内的候选位 —— 绝不切进图片/卡片/统计行/标题组；
    2) 优选：在「每页不超过一页高」的约束下，用 DP 选一组边界，
       最小化 Σ(页高亏空)²（亏空平方 → 强烈惩罚半空页），
       并给每页一个固定罚分 → 页数取最小值。
       亏空平方而非线性，是为了让各页填充量均匀，避免「一页满、一页只剩 20%」。
    """
    page = SLICE_CSS_H
    H = float(total_css_h)

    safe = sorted({float(p) for p in safe_pts} | {0.0, H})
    safe = [p for p in safe
            if not any(t + 2 < p < b - 2 for (t, b) in forbidden)]

    n = len(safe)
    INF = float("inf")
    PAGE_PEN = 5.0e6            # 每页固定罚分：优先压页数
    LAST_W = 0.08               # 末页亏空权重（末页短是正常的，只轻罚）

    def seg_cost(seg, last):
        w = LAST_W if last else 1.0
        return w * max(0.0, page - seg) ** 2

    # dp[i] = 从 safe[i] 走到文档末尾的最小代价；choice[i] = 下一跳下标
    dp = [INF] * n
    choice = [-1] * n
    for i in range(n - 1, -1, -1):
        rest = H - safe[i]
        if rest <= page + 0.5:
            dp[i] = seg_cost(rest, True)
            choice[i] = n - 1
            continue
        best, bj = INF, -1
        for j in range(i + 1, n):
            if safe[j] - safe[i] > page + 0.5:
                break
            if dp[j] == INF:
                continue
            c = seg_cost(safe[j] - safe[i], False) + PAGE_PEN + dp[j]
            if c < best:
                best, bj = c, j
        dp[i], choice[i] = best, bj

    if dp[0] == INF:
        # 理论上不会发生（safe 里必有 0 与 H）；兜底退回贪心
        return _greedy_boundaries(H, safe, page, forbidden)

    bnd = [0.0]
    i = 0
    while i < n - 1:
        j = choice[i]
        if j < 0:
            break
        bnd.append(safe[j])
        i = j
    if bnd[-1] < H:
        bnd.append(H)
    return _finalize(bnd, forbidden, H), []


def _greedy_boundaries(H: float, safe: list, page: float, forbidden: list):
    """兜底：贪心最大填充（DP 无解时才走这里）。"""
    boundaries = [0.0]
    current = 0.0
    guard = 0
    while H - current > page + 0.5 and guard < 400:
        guard += 1
        hi = min(current + page, H)
        cands = [p for p in safe if current + page * 0.45 <= p <= hi]
        if not cands:
            cands = [p for p in safe if current + 60 <= p <= hi]
        best = max(cands) if cands else hi
        if best <= current + 1:
            best = hi
        boundaries.append(best)
        current = best
    if boundaries[-1] < H:
        boundaries.append(H)
    return (_finalize(boundaries, forbidden, H),
            [(boundaries[i], boundaries[i + 1])
             for i in range(len(boundaries) - 1)
             if boundaries[i + 1] - boundaries[i] > page + 0.5])


def verify(out, forbidden, name):
    """校验：任一边界都不得落在禁越区间内部（严格，含亚像素级残留）。
    返回违规列表。"""
    bad = []
    for b in out:
        for (t, bo) in forbidden:
            if t + 0.01 < b < bo - 0.01:
                bad.append((b, t, bo))
    if bad:
        print(f"    ⚠️ {name}: {len(bad)} 处边界切进受保护元素 -> {bad[:4]}")
    return bad


def slice_to_jpgs(png_path: Path, out_dir: Path, stem: str, boundaries: list,
                  seamless: bool = False):
    """按 CSS 像素边界裁剪整页 PNG。
    - 普通模式：统一为横向 A4 单页尺寸，不足白底填充，绝不纵向拉伸；
      单页内容超高一页时按页高再切（保底，正常不会触发）。
    - 无缝模式(seamless)：不填充，按内容实际高度出页（消除页底留白）。
    返回 [(jpg 路径, 实际像素高), ...]"""
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    out = []
    idx = 0
    for i in range(len(boundaries) - 1):
        top_px = int(boundaries[i] * DPR)
        bot_px = int(min(boundaries[i + 1] * DPR, H))
        if bot_px <= top_px:
            continue
        seg_top = top_px
        while seg_top < bot_px:
            seg_bot = min(seg_top + SLICE_PX_H, bot_px)
            part = im.crop((0, seg_top, W, seg_bot))
            if not seamless and (part.height < SLICE_PX_H or part.width != PAGE_PX_W):
                pad = Image.new("RGB", (PAGE_PX_W, SLICE_PX_H), (255, 255, 255))
                pad.paste(part, (0, 0))
                part = pad
            jp = out_dir / f"{stem}_{idx:03d}.jpg"
            part.save(jp, "JPEG", quality=JPEG_QUALITY, optimize=True)
            out.append((jp, part.height))
            idx += 1
            seg_top = seg_bot
    return out


def main():
    seamless = "--seamless" in sys.argv
    all_slices = []          # [(jpg 路径, 实际像素高)]
    tmp_dir = BASE / "_pdf_tmp"
    slice_dir = BASE / "_pdf_slices"
    tmp_dir.mkdir(exist_ok=True)
    slice_dir.mkdir(exist_ok=True)
    total_violations = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=EDGE,
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            ctx = browser.new_context(
                viewport={"width": RENDER_W, "height": 900},
                device_scale_factor=DPR,
            )
            ctx.add_init_script(INIT_JS)
            for rel, stem in PAGES:
                page = ctx.new_page()
                src = BASE / rel
                page.goto(file_url(str(src)), wait_until="load")
                # 等图片与字体布局完全稳定后再测量/截图（否则包围盒错位 → 分页错位）
                page.wait_for_function(
                    "() => Array.from(document.images)"
                    ".every(i => i.complete && i.naturalWidth > 0)",
                    timeout=30000)
                try:
                    page.evaluate("() => document.fonts.ready")
                except Exception:
                    pass
                page.wait_for_timeout(500)
                png = tmp_dir / f"{stem}.png"
                page.screenshot(path=str(png), full_page=True, type="png")
                # 截图之后再测量：full_page 截图会临时改变视口，测完后布局已还原
                info = page.evaluate(JS_MEASURE)
                total_css_h = info["scrollHeight"]
                boundaries, hard = smart_boundaries(
                    total_css_h, info["safe"], info["forbidden"], stem)
                bad = verify(boundaries, info["forbidden"], stem)
                total_violations += len(bad)
                page.close()
                slices = slice_to_jpgs(png, slice_dir, stem, boundaries, seamless)
                all_slices.extend(slices)
                fills = [round((boundaries[i + 1] - boundaries[i]) / SLICE_CSS_H * 100)
                         for i in range(len(boundaries) - 1)]
                print(f"  {stem}: CSS 高 {total_css_h}px → {len(slices)} 页，"
                      f"填充率 {fills}%" + (f"　⚠️硬切 {len(hard)} 处" if hard else ""))
            browser.close()

        if not all_slices:
            print("无任何切片，终止", file=sys.stderr)
            return 1

        name = "翁彥斌-作品集-无缝版.pdf" if seamless else "翁彥斌-作品集.pdf"
        out = BASE / "pdf" / name
        out.parent.mkdir(exist_ok=True)
        a4w, a4h = landscape(A4)
        c = canvas.Canvas(str(out), pagesize=(a4w, a4h))
        c.setTitle("翁彥斌 · 工业设计作品集")
        c.setAuthor("翁彥斌")
        c.setSubject("产品设计作品集：DSLR / 头戴式耳机 / 智能猫窝 / 越野车玩具 + 设计方法论")
        for jp, hpx in all_slices:
            if seamless:
                ph = a4w * hpx / PAGE_PX_W          # 按内容实际高度出页
            else:
                ph = a4h
            c.setPageSize((a4w, ph))
            c.drawImage(str(jp), 0, 0, width=a4w, height=ph,
                        preserveAspectRatio=False, anchor="c")
            c.showPage()
        c.save()
        print(f"\n完成：{out}  共 {len(all_slices)} 页"
              f"（{'无缝可变页高' if seamless else '横向 A4 定高'}）")
        print(f"裁切校验：{total_violations} 处边界切进受保护元素"
              + ("　✅ 全部干净" if total_violations == 0 else "　⚠️ 见上方明细"))

        root_copy = BASE.parent / name
        try:
            shutil.copy2(out, root_copy)
            print(f"已复制：{root_copy}")
        except PermissionError:
            print(f"⚠️ 根目录被占用（可能正在查看旧 PDF），跳过：{root_copy}")
        out_dir2 = Path(r"D:\工作文件") / f"作品集PDF导出_{datetime.now():%Y%m%d}"
        out_dir2.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(out, out_dir2 / name)
            print(f"已复制：{out_dir2 / name}")
        except PermissionError:
            print(f"⚠️ 目标被占用，跳过：{out_dir2 / name}")
        return 0
    finally:
        for f in tmp_dir.glob("*"):
            f.unlink(missing_ok=True)
        for f in slice_dir.glob("*"):
            f.unlink(missing_ok=True)
        for d in (tmp_dir, slice_dir):
            if d.exists():
                try:
                    d.rmdir()
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
