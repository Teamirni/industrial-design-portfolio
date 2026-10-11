# -*- coding: utf-8 -*-
"""为 HTML 生成：① 去空白长图 PNG ② A4 PDF。
用法：_export_html.py <html绝对路径> [宽度=1360] [窗口高=9000] [缩放=2]

注意：Edge headless 的截图高度受窗口高限制，页面比窗口高就会被**静默截断**。
页数多 / 长文档务必显式给足窗口高（CSS px），否则最后一页会缺半截。
缩放 × 窗口高 不应超过 ~26000 px（GPU 纹理上限），超高时把缩放降到 1.5 或 1。
"""
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops

EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
if not EDGE.exists():
    EDGE = Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe')
HOST, PORT = '127.0.0.1', 8191


def main():
    target = Path(sys.argv[1]).resolve()
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1360
    win_h = int(sys.argv[3]) if len(sys.argv) > 3 else 9000
    dpr = float(sys.argv[4]) if len(sys.argv) > 4 else 2
    stem = target.stem

    cwd = os.getcwd()
    os.chdir(target.parent)
    import http.server
    import socketserver
    httpd = socketserver.TCPServer((HOST, PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1)
            break
        except Exception:
            time.sleep(0.2)

    url = 'http://%s:%d/%s' % (HOST, PORT, urllib.parse.quote(target.name))
    try:
        raw = target.parent / ('_%s_raw.png' % stem)
        subprocess.run([
            str(EDGE), '--headless', '--no-sandbox', '--disable-gpu',
            '--hide-scrollbars', '--force-device-scale-factor=%s' % dpr,
            '--virtual-time-budget=14000',
            '--window-size=%d,%d' % (width, win_h),
            '--screenshot=%s' % raw, url,
        ], capture_output=True, timeout=300)

        pdf = target.parent / ('%s.pdf' % stem)
        subprocess.run([
            str(EDGE), '--headless', '--no-sandbox', '--disable-gpu',
            '--no-pdf-header-footer', '--virtual-time-budget=14000',
            '--print-to-pdf=%s' % pdf, url,
        ], capture_output=True, timeout=300)
    finally:
        httpd.shutdown()
        os.chdir(cwd)

    if raw.exists():
        im = Image.open(raw).convert('RGB')
        bg = Image.new('RGB', im.size, im.getpixel((im.size[0] - 3, im.size[1] - 3)))
        diff = ImageChops.difference(im, bg).convert('L')
        bbox = diff.getbbox()
        if bbox:
            im = im.crop((0, 0, im.size[0], min(im.size[1], bbox[3] + 40)))
        out = target.parent / ('%s-长图.png' % stem)
        im.save(out, optimize=True)
        print('长图:', out, im.size, '%.1f MB' % (os.path.getsize(out) / 1048576))
        raw.unlink(missing_ok=True)
    if pdf.exists():
        print('PDF :', pdf, '%.1f MB' % (os.path.getsize(pdf) / 1048576))


if __name__ == '__main__':
    main()
