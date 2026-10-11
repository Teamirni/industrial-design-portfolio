from pypdf import PdfReader, PdfWriter
from pathlib import Path
from datetime import datetime
import shutil

BASE = Path(r"E:\WorkBuddy工作路径\工业设计作品集")
PDF_DIR = BASE / "portfolio-v2" / "pdf"
SRC = PDF_DIR / "翁彥斌-工业设计作品集-v2.pdf"
MERGED_NAME = "翁彥斌-工业设计作品集-v2.pdf"

# 1) 备份原始合并 PDF
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = PDF_DIR / f"_backup_pre_reorder_{ts}.pdf"
shutil.copy2(SRC, backup)

# 2) 读取并构建重排计划
reader = PdfReader(str(SRC))
N = len(reader.pages)
pages = list(reader.pages)

def seg(a, b):  # 1-indexed 闭区间 -> 0-indexed 列表
    return list(range(a - 1, b))

# 用户指令：将 22-35 页迁移到第 7 页之后，原 8-21 顺延到下方
# 新顺序 = [1-7] + [22-35] + [8-21] + [36-end]
plan = seg(1, 7) + seg(22, 35) + seg(8, 21) + list(range(35, N))
assert len(plan) == N, f"plan len {len(plan)} != N {N}"
assert sorted(plan) == list(range(N)), "plan 必须是完整排列（不重不漏）"

# 3) 写出重排后的 PDF（先写临时文件，再替换，避免同路径读写冲突）
tmp = PDF_DIR / "_reordered_tmp.pdf"
writer = PdfWriter()
for idx in plan:
    writer.add_page(pages[idx])
with open(tmp, "wb") as f:
    writer.write(f)

SRC.unlink()
tmp.rename(SRC)

# 4) 同步复制到工作区根目录与 D:\ 成品目录
root_copy = BASE / MERGED_NAME
shutil.copy2(SRC, root_copy)

output_dir = Path(r"D:\工作文件") / f"作品集PDF导出_{datetime.now().strftime('%Y%m%d')}"
output_dir.mkdir(parents=True, exist_ok=True)
output_copy = output_dir / MERGED_NAME
shutil.copy2(SRC, output_copy)

# 5) 汇总
lines = []
lines.append(f"重排完成：{N} 页 -> {N} 页（页数不变，仅调整顺序）")
lines.append("新顺序 = [1-7] + [22-35] + [8-21] + [36-end]")
lines.append(f"备份：{backup}")
lines.append(f"工作区根目录：{root_copy}")
lines.append(f"D盘成品：{output_copy}")
lines.append("")
lines.append("新页 <- 原页 映射：")
for new_i, orig_i in enumerate(plan):
    lines.append(f"  new p{new_i+1:>2d} <- old p{orig_i+1:>2d}")

out = PDF_DIR / "_reorder_summary.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("done")
