from pypdf import PdfReader
from pathlib import Path

pdf = Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2\pdf\翁彥斌-作品集.pdf")
reader = PdfReader(str(pdf))
N = len(reader.pages)
out = [f"总页数: {N}"]

phrases = ["岗位能力对照", "从设计到生产", "JD 能力映射", "Creo", "可开模分件", "爆炸图", "初级 3D 设计师"]
for ph in phrases:
    hits = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if ph in t:
            hits.append(i + 1)
    out.append(f"  「{ph}」出现在页码: {hits if hits else '未找到'}")

def first_line(i):
    try:
        t = reader.pages[i].extract_text() or ""
    except Exception:
        t = ""
    return t.strip().replace("\n", " ")[:50]

out.append("\n首尾页抽样：")
for i in list(range(0, 6)) + list(range(N - 4, N)):
    out.append(f"  p{i+1}: {first_line(i)}")

Path(r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2\pdf\_verify_jd.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("done")
