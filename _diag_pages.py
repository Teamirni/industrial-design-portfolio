from pypdf import PdfReader
from pathlib import Path

pdf_dir = Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2\pdf")
merged = pdf_dir / "翁彥斌-工业设计作品集-v2.pdf"

lines = []
per_page = [
    ("00-index.pdf", "index"),
    ("01-about.pdf", "about"),
    ("02-dslr.pdf", "dslr"),
    ("03-headphones.pdf", "headphones"),
    ("04-cat-nest.pdf", "cat-nest"),
    ("05-toy.pdf", "offroad-toy"),
    ("06-methodology.pdf", "methodology"),
]
lines.append("=== per-page PDF page counts ===")
counts = {}
for fn, label in per_page:
    p = pdf_dir / fn
    if p.exists():
        c = len(PdfReader(str(p)).pages)
        counts[label] = c
        lines.append(f"{label:14s} {c} pages  ({fn})")
    else:
        lines.append(f"{label:14s} MISSING ({fn})")

lines.append("")
lines.append(f"=== merged: exists={merged.exists()} ===")
if merged.exists():
    r = PdfReader(str(merged))
    n = len(r.pages)
    lines.append(f"total pages: {n}")
    order = ["index", "about", "dslr", "headphones", "cat-nest", "offroad-toy", "methodology"]
    start = 1
    lines.append("--- combined page ranges by source ---")
    for label in order:
        c = counts.get(label, 0)
        if c > 0:
            lines.append(f"{label:14s} combined pages {start:>3d}-{start+c-1:>3d} ({c} pp)")
            start += c
    lines.append("")
    lines.append("--- first text line per merged page ---")
    for i, page in enumerate(r.pages):
        try:
            t = page.extract_text() or ""
        except Exception as e:
            t = f"<err {e}>"
        t = t.strip().replace("\n", " ")[:70]
        lines.append(f"p{i+1:>3d}: {t}")

out = pdf_dir / "_diag_pages.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("done")
