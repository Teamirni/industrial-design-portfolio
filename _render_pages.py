import os
import pymupdf

BASE = r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2"
PDF = os.path.join(BASE, "pdf", "翁彥斌-工业设计作品集-v2.pdf")
OUT = os.path.join(BASE, "_render_about")

os.makedirs(OUT, exist_ok=True)
doc = pymupdf.open(PDF)
print(f"Pages: {doc.page_count}")

for i in [2, 3, 4, 5, 6]:
    if i >= doc.page_count:
        continue
    page = doc.load_page(i)
    pix = page.get_pixmap(dpi=100)
    png = os.path.join(OUT, f"page_{i+1:03d}.png")
    pix.save(png)
    print(f"Saved {png} ({pix.width}x{pix.height})")
