"""
翁彥斌作品集 v2 · PDF 生成脚本 v2
使用本地 Edge 浏览器（旧版 headless）将各 HTML 页面打印为 PDF，再用 pypdf 合并。

改进点：
- 显式使用旧版 --headless（在当前 Edge 环境中可正常出 PDF，--headless=new 会失败）
- 加入 --no-sandbox / --no-pdf-header-footer / --virtual-time-budget 等稳定项
- 等待图片 / 字体加载后再打印
- 合并后自动复制到工作区根目录与 D:\工作文件\ 成品目录
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

# ───────── 配置 ─────────
BASE = Path(__file__).parent.resolve()
PDF_DIR = BASE / "pdf"
PDF_DIR.mkdir(exist_ok=True)

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

PAGES = [
    ("index.html", "00-index.pdf"),
    ("about.html", "01-about.pdf"),
    ("projects/dslr.html", "02-dslr.pdf"),
    ("projects/headphones.html", "03-headphones.pdf"),
    ("projects/cat-nest.html", "04-cat-nest.pdf"),
    ("projects/offroad-toy.html", "05-toy.pdf"),
    ("methodology.html", "06-methodology.pdf"),
]

MERGED_NAME = "翁彥斌-作品集.pdf"
HOST = "127.0.0.1"
PORT = 8155
VIRTUAL_TIME_MS = 18_000  # 等待图片 / 字体加载的虚拟时间预算


# ───────── 工具函数 ─────────
def find_edge() -> Path:
    for p in EDGE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("未找到 Microsoft Edge 浏览器，无法生成 PDF")


def start_server():
    import http.server
    import socketserver

    os.chdir(BASE)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer((HOST, PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def wait_for_server(timeout: float = 15.0):
    url = f"http://{HOST}:{PORT}/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def run_cmd(cmd, timeout: float = 90.0):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    stdout = (r.stdout or b"").decode("utf-8", "replace")
    stderr = (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, stdout, stderr


def print_to_pdf(html_path: str, out_name: str) -> Path:
    out_pdf = PDF_DIR / out_name
    url = f"http://{HOST}:{PORT}/{html_path}"
    cmd = [
        str(EDGE),
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out_pdf}",
        f"--virtual-time-budget={VIRTUAL_TIME_MS}",
        url,
    ]
    rc, out, err = run_cmd(cmd)
    return out_pdf, rc, err


def merge_pdfs(parts: list[Path], output: Path):
    writer = PdfWriter()
    page_total = 0
    for part in parts:
        reader = PdfReader(str(part))
        n = len(reader.pages)
        page_total += n
        for page in reader.pages:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    return page_total


def reorder_merged(pdf_path: Path):
    """按用户要求重排合并后的 PDF：
    把 cat-nest + offroad-toy（原第 22-35 页）整体迁移到 DSLR 第 1 页（原第 7 页）之后，
    原 DSLR 余下正文 + headphones（原第 8-21 页）顺延到下方。
    重排计划由各分册页数推导，分册页数变化但结构不变时仍可自适应。"""
    reader = PdfReader(str(pdf_path))
    N = len(reader.pages)
    pages = list(reader.pages)

    # 计算各分册在合并 PDF 中的 1-indexed 起止页
    order = [
        ("index", "00-index.pdf"),
        ("about", "01-about.pdf"),
        ("dslr", "02-dslr.pdf"),
        ("headphones", "03-headphones.pdf"),
        ("cat-nest", "04-cat-nest.pdf"),
        ("offroad-toy", "05-toy.pdf"),
        ("methodology", "06-methodology.pdf"),
    ]
    counts = {}
    for label, fn in order:
        p = PDF_DIR / fn
        counts[label] = len(PdfReader(str(p)).pages) if p.exists() else 0
    start = {}
    cur = 1
    for label, _ in order:
        start[label] = cur
        cur += counts[label]

    dslr_first = start["dslr"]                                   # 原第 7 页
    cat_start = start["cat-nest"]                                # 原第 22 页
    off_end = start["offroad-toy"] + counts["offroad-toy"] - 1   # 原第 35 页
    meth_start = start["methodology"]                            # 原第 36 页

    def seg(a, b):  # 1-indexed 闭区间 -> 0-indexed 列表
        return list(range(a - 1, b))

    # 新顺序（均为 1-indexed 闭区间）：[1..dslr_first] + [cat_start..off_end] + [dslr_first+1..cat_start-1] + [meth_start..N]
    plan = (seg(1, dslr_first) +
            seg(cat_start, off_end) +
            seg(dslr_first + 1, cat_start - 1) +
            list(range(meth_start - 1, N)))

    assert len(plan) == N, f"重排计划长度 {len(plan)} 与总页数 {N} 不符"
    assert sorted(plan) == list(range(N)), "重排计划必须是完整排列（不重不漏）"

    writer = PdfWriter()
    for idx in plan:
        writer.add_page(pages[idx])
    tmp = pdf_path.with_name("_reorder_tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    pdf_path.unlink()
    tmp.rename(pdf_path)
    return N


def copy_to_root_and_output(merged: Path):
    """复制成品到工作区根目录与 D:\工作文件\ 成品目录。"""
    copies = []

    # 1) 工作区根目录
    root_copy = BASE.parent / MERGED_NAME
    shutil.copy2(merged, root_copy)
    copies.append(root_copy)

    # 2) D:\工作文件\ 成品目录
    output_dir = Path(r"D:\工作文件") / f"作品集PDF导出_{datetime.now().strftime('%Y%m%d')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_copy = output_dir / MERGED_NAME
    shutil.copy2(merged, output_copy)
    copies.append(output_copy)

    return copies


# ───────── 主流程 ─────────
def main():
    global EDGE
    EDGE = find_edge()
    print(f"使用 Edge: {EDGE}")

    server = start_server()
    if not wait_for_server():
        print("本地 HTTP 服务启动失败", file=sys.stderr)
        return 1

    try:
        generated: list[Path] = []
        for html_path, out_name in PAGES:
            print(f"\n转换 {html_path} → {out_name} …")
            pdf_path, rc, err = print_to_pdf(html_path, out_name)
            if pdf_path.exists():
                reader = PdfReader(str(pdf_path))
                n_pages = len(reader.pages)
                print(f"  ✓ {out_name}: {pdf_path.stat().st_size / 1024 / 1024:.2f} MB, {n_pages} 页")
                generated.append(pdf_path)
            else:
                print(f"  ✗ {out_name} 生成失败 (Edge rc={rc})", file=sys.stderr)
                if err:
                    print(f"  stderr: {err[:500]}", file=sys.stderr)
                return 1

        # 合并
        merged = PDF_DIR / MERGED_NAME
        total_pages = merge_pdfs(generated, merged)
        print(f"\n合并完成：{merged}")
        print(f"总页数：{total_pages}")

        # 按用户要求重排页码：cat-nest + offroad-toy（原 22-35 页）迁移到 DSLR 第 1 页（原 7 页）之后
        reorder_merged(merged)
        print("已按用户要求重排页码：原 22-35 页迁移至第 7 页之后，原 8-21 页顺延到下方")

        # 复制成品
        copies = copy_to_root_and_output(merged)
        for p in copies:
            print(f"已复制：{p}")

        # 简单校验：逐页文本可读性
        reader = PdfReader(str(merged))
        sample_text = ""
        for i, page in enumerate(reader.pages[:3]):
            try:
                sample_text += page.extract_text()[:200]
            except Exception:
                pass
        if "翁彥斌" in sample_text:
            print("文本校验通过：已识别姓名，未出现乱码")

        print("\nPDF 生成全部完成。")
        return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
