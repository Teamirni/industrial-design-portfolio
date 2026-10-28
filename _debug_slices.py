# -*- coding: utf-8 -*-
"""调试：重现切片过程并保存切片图，便于目视定位跨页问题。"""
import sys
import urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from build_pdf_v3 import (INIT_JS, JS_GET_BOXES, PAGES, PROTECTED_SELECTORS,
                          RENDER_W, DPR, PAGE_PX_W, SLICE_PX_H, JPEG_QUALITY,
                          smart_boundaries, file_url)

BASE = Path(__file__).parent.resolve()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not Path(EDGE).exists():
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
OUT = BASE / "_debug_slices"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EDGE, headless=True,
                          args=["--no-sandbox", "--disable-gpu"])
    ctx = b.new_context(viewport={"width": RENDER_W, "height": 900},
                        device_scale_factor=DPR)
    ctx.add_init_script(INIT_JS)
    for rel, stem in PAGES:
        pg = ctx.new_page()
        pg.goto(file_url(str(BASE / rel)), wait_until="load")
        pg.wait_for_timeout(1500)
        info = pg.evaluate(JS_GET_BOXES)
        total = info["scrollHeight"]
        boxes = info["boxes"]
        boundaries = smart_boundaries(total, boxes)
        png = OUT / f"{stem}_full.png"
        pg.screenshot(path=str(png), full_page=True, type="png")
        pg.close()
        im = Image.open(png).convert("RGB")
        W, H = im.size
        print(f"\n=== {stem}: scrollHeight={total}, PNG={im.size}, 切片 {len(boundaries)-1} 个")
        print("    boundaries:", boundaries)
        for bx in sorted(boxes, key=lambda x: x["top"]):
            print(f"    [{bx['sel']}] {bx['top']:.0f} ~ {bx['bottom']:.0f} (h={bx['bottom']-bx['top']:.0f})")
        for i in range(len(boundaries) - 1):
            top_px = int(boundaries[i] * DPR)
            bot_px = int(min(boundaries[i + 1] * DPR, H))
            part = im.crop((0, top_px, W, bot_px))
            if part.width != PAGE_PX_W or part.height != SLICE_PX_H:
                if part.height > SLICE_PX_H:
                    part = part.resize((PAGE_PX_W, SLICE_PX_H), Image.LANCZOS)
                else:
                    pad = Image.new("RGB", (PAGE_PX_W, SLICE_PX_H), (255, 255, 255))
                    pad.paste(part, (0, 0))
                    part = pad
            part.save(OUT / f"{stem}_p{i+1}.jpg", "JPEG", quality=JPEG_QUALITY, optimize=True)
            print(f"    -> p{i+1}: CSS {boundaries[i]}~{boundaries[i+1]} "
                  f"(高 {boundaries[i+1]-boundaries[i]})")
    b.close()
print("\ndone")
