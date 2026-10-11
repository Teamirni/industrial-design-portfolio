from pathlib import Path

OUT_DIR = Path(r"D:\工作文件\作品集PDF导出_20260912")
SUMMARY = Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2\_zip_summary.txt")

with open(SUMMARY, "w", encoding="utf-8") as f:
    f.write("=== 输出目录文件 ===\n")
    for p in sorted(OUT_DIR.iterdir()):
        size_mb = p.stat().st_size / 1024 / 1024
        f.write(f"{p.name}: {size_mb:.2f} MB\n")
print("OK")
