import shutil
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(r"E:\WorkBuddy工作路径\工业设计作品集")
PDF_NAME = "翁彥斌-作品集.pdf"
src = BASE / PDF_NAME  # 工作区根目录（build 脚本输出）

lines = []
assert src.exists(), f"未找到最终 PDF：{src}"

# 提交目录（folder + zip 双格式）
submit_dir = Path(r"D:\工作文件") / f"翁彥斌-作品集-ZURU提交_{datetime.now().strftime('%Y%m%d')}"
submit_dir.mkdir(parents=True, exist_ok=True)

# 复制 PDF 到提交目录
final_pdf = submit_dir / PDF_NAME
shutil.copy2(src, final_pdf)
lines.append(f"PDF 副本：{final_pdf}  ({final_pdf.stat().st_size/1024/1024:.2f} MB)")

# 单个 zip（不加密、不拆分），内部仅含 PDF
zip_path = submit_dir / "翁彥斌-作品集.zip"
if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(final_pdf, arcname=PDF_NAME)  # arcname 确保 zip 内文件名即 姓名-作品集.pdf
zsize = zip_path.stat().st_size / 1024 / 1024
lines.append(f"ZIP 文件：{zip_path}  ({zsize:.2f} MB)")

# 校验
assert zsize <= 50, f"ZIP 超过 50MB 限制：{zsize:.2f} MB"
with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
    bad = [n for n in names if n.lower().endswith((".exe", ".lnk")) or "/" in n]
    assert not z.infolist()[0].flag_bits & 0x1, "ZIP 被加密"
    lines.append(f"ZIP 内容校验：{len(names)} 个文件 = {names}")

lines.append("")
lines.append("✅ 提交物就绪：JD 要求的「姓名-作品集.pdf」单文件 + 单 zip（≤50MB，未加密）")
out = BASE / "portfolio-v2" / "_package_summary.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("done")
