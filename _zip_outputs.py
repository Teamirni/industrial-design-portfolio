import os
import zipfile
from pathlib import Path

BASE = Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2")
OUT_DIR = Path(r"D:\工作文件\作品集PDF导出_20260912")
OUT_DIR.mkdir(parents=True, exist_ok=True)

zip_path = OUT_DIR / "作品集PDF导出.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    # 合并 PDF
    merged = BASE / "pdf" / "翁彥斌-工业设计作品集-v2.pdf"
    zf.write(merged, arcname=merged.name)
    # 分页面 PDF
    for name in [
        "00-index.pdf", "01-about.pdf", "02-dslr.pdf", "03-headphones.pdf",
        "04-cat-nest.pdf", "05-toy.pdf", "06-methodology.pdf",
    ]:
        p = BASE / "pdf" / name
        zf.write(p, arcname=p.name)
    # 脚本
    script = BASE / "build_pdf_v2.py"
    zf.write(script, arcname=script.name)

print(f"ZIP_CREATED: {zip_path}")
print(f"ZIP_SIZE: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
