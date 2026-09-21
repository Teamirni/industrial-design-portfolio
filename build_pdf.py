"""
翁彥斌作品集 v2 · PDF 生成脚本
使用本地 Edge 浏览器将各 HTML 页面打印为 PDF，再用 pypdf 合并。
"""

import os
import subprocess
import time
from pathlib import Path
from pypdf import PdfWriter, PdfReader

BASE = Path(__file__).parent.resolve()
PDF_DIR = BASE / "pdf"
PDF_DIR.mkdir(exist_ok=True)

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
if not EDGE.exists():
    EDGE = Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")

# 页面顺序：封面 → 关于 → 项目详情 → 方法论
PAGES = [
    ("index.html", "00-index.pdf"),
    ("about.html", "01-about.pdf"),
    ("projects/dslr.html", "02-dslr.pdf"),
    ("projects/headphones.html", "03-headphones.pdf"),
    ("projects/cat-nest.html", "04-cat-nest.pdf"),
    ("projects/offroad-toy.html", "05-toy.pdf"),
    ("methodology.html", "06-methodology.pdf"),
]


def start_server():
    proc = subprocess.Popen(
        ["python", "-m", "http.server", "8000"],
        cwd=str(BASE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等待服务就绪
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:8000/", timeout=1)
            return proc
        except Exception:
            time.sleep(0.3)
    return proc


def print_to_pdf(html_path: str, out_name: str) -> Path:
    out_pdf = PDF_DIR / out_name
    url = f"http://localhost:8000/{html_path}"
    cmd = [
        str(EDGE),
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={out_pdf}",
        url,
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out_pdf


def merge_pdfs(parts: list, output: Path):
    writer = PdfWriter()
    for part in parts:
        reader = PdfReader(str(part))
        for page in reader.pages:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)


def main():
    if not EDGE.exists():
        print("未找到 Edge 浏览器，无法生成 PDF")
        return 1

    server = start_server()
    try:
        generated = []
        for html_path, out_name in PAGES:
            pdf_path = print_to_pdf(html_path, out_name)
            size = pdf_path.stat().st_size if pdf_path.exists() else 0
            print(f"生成 {out_name} — {size / 1024 / 1024:.2f} MB")
            if pdf_path.exists():
                generated.append(pdf_path)

        merged = PDF_DIR / "翁彥斌-工业设计作品集-v2.pdf"
        merge_pdfs(generated, merged)
        print(f"合并完成：{merged}")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
