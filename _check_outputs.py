import os
import sys
from pathlib import Path
from pypdf import PdfReader

BASE = Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2")
MERGED = BASE / "pdf" / "翁彥斌-工业设计作品集-v2.pdf"
ROOT_COPY = Path(r"E:\WorkBuddy工作路径\工业设计作品集\翁彥斌-工业设计作品集-v2.pdf")
OUT_DIR = Path(r"D:\工作文件")
OUT_COPY = None
for d in OUT_DIR.iterdir() if OUT_DIR.exists() else []:
    if d.is_dir() and "作品集PDF导出" in d.name:
        cand = d / "翁彥斌-工业设计作品集-v2.pdf"
        if cand.exists():
            OUT_COPY = cand
            break

with open(BASE / "_build_summary.txt", "w", encoding="utf-8") as f:
    f.write("=== PDF 生成摘要 ===\n")
    f.write(f"合并文件存在: {MERGED.exists()}\n")
    f.write(f"合并文件大小: {MERGED.stat().st_size / 1024 / 1024:.2f} MB\n")
    if MERGED.exists():
        reader = PdfReader(str(MERGED))
        f.write(f"总页数: {len(reader.pages)}\n")
        try:
            txt = "\n".join(p.extract_text()[:300] for p in reader.pages[:2])
            f.write(f"首两页文本片段（校验乱码）:\n{txt[:600]}\n")
        except Exception as e:
            f.write(f"提取文本失败: {e}\n")
    f.write(f"根目录副本: {ROOT_COPY.exists()} ({ROOT_COPY.stat().st_size / 1024 / 1024:.2f} MB)\n")
    f.write(f"D:\\工作文件副本: {OUT_COPY}\n")
    f.write("\n=== 各页面 PDF ===\n")
    for name in ["00-index.pdf", "01-about.pdf", "02-dslr.pdf", "03-headphones.pdf", "04-cat-nest.pdf", "05-toy.pdf", "06-methodology.pdf"]:
        p = BASE / "pdf" / name
        if p.exists():
            try:
                n = len(PdfReader(str(p)).pages)
            except Exception:
                n = "?"
            f.write(f"{name}: {p.stat().st_size / 1024 / 1024:.2f} MB, {n} 页\n")
        else:
            f.write(f"{name}: 缺失\n")
print("SUMMARY_WRITTEN")
