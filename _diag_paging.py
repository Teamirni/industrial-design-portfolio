# -*- coding: utf-8 -*-
"""分页诊断 v2：打印边界与禁越区间明细，定位残留问题。"""
import sys
from playwright.sync_api import sync_playwright
import build_pdf_v3 as B

TARGET = sys.argv[1] if len(sys.argv) > 1 else None

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=B.EDGE, headless=True,
                           args=["--no-sandbox", "--disable-gpu"])
    ctx = br.new_context(viewport={"width": B.RENDER_W, "height": 900},
                         device_scale_factor=B.DPR)
    ctx.add_init_script(B.INIT_JS)
    for rel, stem in B.PAGES:
        if TARGET and TARGET not in stem:
            continue
        pg = ctx.new_page()
        pg.goto(B.file_url(str(B.BASE / rel)), wait_until="load")
        pg.wait_for_function(
            "() => Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)",
            timeout=30000)
        pg.wait_for_timeout(400)
        info = pg.evaluate(B.JS_MEASURE)
        H = info["scrollHeight"]
        raw = sorted({float(x) for x in info["safe"]} | {0.0, float(H)})
        kept = [p for p in raw
                if not any(t + 2 < p < b - 2 for (t, b) in info["forbidden"])]
        bnd, hard = B.smart_boundaries(H, info["safe"], info["forbidden"], stem)
        bad = B.verify(bnd, info["forbidden"], stem)
        fills = [round((bnd[i+1]-bnd[i])/B.SLICE_CSS_H*100) for i in range(len(bnd)-1)]
        print(f"\n=== {stem}  H={H}  pages={len(bnd)-1}  fill={fills}  hard={len(hard)}  bad={len(bad)}")
        print("  boundaries:", [round(b) for b in bnd])
        if bad:
            for b, t, bo in bad[:8]:
                print(f"  ⚠️ 边界 {b} 在禁越区间 [{t:.0f},{bo:.0f}]（高 {bo-t:.0f}）内")
                lo = [round(x) for x in kept if abs(x - t) < 900]
                print(f"     该区间附近保留的安全位: {lo[:14]}")
        if hard:
            print("  hard cuts:", [(round(a), round(b)) for a, b in hard])
        pg.close()
    br.close()
