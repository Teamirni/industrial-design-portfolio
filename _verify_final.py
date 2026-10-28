# -*- coding: utf-8 -*-
"""成品 PDF 终检：逐个原子元素核对是否被整页容纳（以源页测量 + 实际边界为准）。"""
import pymupdf
from playwright.sync_api import sync_playwright
import build_pdf_v3 as B

ATOMIC = ['.cover', '.about-hero', '.figure', '.image-row', '.stat-row',
          '.project-card', '.quote-block', '.failed-concept', '.meta-item',
          '.timeline-list > li', '.skill-bar', '.stage-header',
          '.capability-matrix', '.cap-item', '.deliverable-strip']

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=B.EDGE, headless=True,
                           args=["--no-sandbox", "--disable-gpu"])
    ctx = br.new_context(viewport={"width": B.RENDER_W, "height": 900},
                         device_scale_factor=B.DPR)
    ctx.add_init_script(B.INIT_JS)
    total_bad = 0
    total_el = 0
    for rel, stem in B.PAGES:
        pg = ctx.new_page()
        pg.goto(B.file_url(str(B.BASE / rel)), wait_until="load")
        pg.wait_for_function(
            "() => Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)",
            timeout=30000)
        pg.wait_for_timeout(400)
        info = pg.evaluate(B.JS_MEASURE)
        bnd, _ = B.smart_boundaries(info["scrollHeight"], info["safe"],
                                    info["forbidden"], stem)
        els = pg.evaluate("""(sels) => {
          const out = [];
          sels.forEach(s => document.querySelectorAll(s).forEach(el => {
            const r = el.getBoundingClientRect();
            const t = r.top + scrollY, b = r.bottom + scrollY;
            if (b - t > 4) out.push([s, t, b]);
          }));
          return out;
        }""", ATOMIC)
        pg.close()
        bad = []
        for s, t, b in els:
            total_el += 1
            if not any(bnd[i] - 0.01 <= t and b <= bnd[i + 1] + 0.01
                       for i in range(len(bnd) - 1)):
                bad.append((s, round(t), round(b)))
        total_bad += len(bad)
        flag = "OK " if not bad else "BAD"
        print(f"{flag} {stem:11s} 原子元素 {len(els):3d} 个，跨页 {len(bad)} 个")
        for s, t, b in bad[:6]:
            print(f"     跨页: {s} [{t},{b}]")
    br.close()

print(f"\n合计：{total_el} 个原子元素，{total_bad} 个被分页切开")

doc = pymupdf.open(str(B.BASE / "pdf" / "翁彥斌-作品集.pdf"))
print(f"PDF：{doc.page_count} 页，页面尺寸 "
      f"{doc[0].rect.width:.0f}x{doc[0].rect.height:.0f} pt（横向 A4）")
