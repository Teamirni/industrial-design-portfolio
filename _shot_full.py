# -*- coding: utf-8 -*-
"""全页长截图并切片。用法：_shot_full.py <html绝对路径> <宽度> <切片高>"""
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
if not EDGE.exists():
    EDGE = Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe')
HOST, PORT = '127.0.0.1', 8181


def main():
    target = Path(sys.argv[1]).resolve()
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1360
    slice_h = int(sys.argv[3]) if len(sys.argv) > 3 else 1150

    cwd = os.getcwd()
    os.chdir(target.parent)
    import http.server
    import socketserver
    httpd = socketserver.TCPServer(
        (HOST, PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1)
            break
        except Exception:
            time.sleep(0.2)

    outdir = target.parent / '_shots'
    outdir.mkdir(exist_ok=True)
    full = outdir / ('%s-full.png' % target.stem)
    url = 'http://%s:%d/%s' % (HOST, PORT, urllib.parse.quote(target.name))
    try:
        subprocess.run([
            str(EDGE), '--headless', '--no-sandbox', '--disable-gpu',
            '--hide-scrollbars', '--force-device-scale-factor=1',
            '--virtual-time-budget=12000',
            '--window-size=%d,%d' % (width, 9000),
            '--screenshot=%s' % full, url,
        ], capture_output=True, timeout=240)
    finally:
        httpd.shutdown()
        os.chdir(cwd)

    if not full.exists():
        print('FAIL')
        return
    im = Image.open(full)
    print('full:', im.size)
    n = (im.size[1] + slice_h - 1) // slice_h
    for i in range(n):
        box = (0, i * slice_h, im.size[0], min(im.size[1], (i + 1) * slice_h))
        part = im.crop(box)
        # 裁掉纯背景空白行，减少无效内容
        p = outdir / ('%s-%02d.png' % (target.stem, i + 1))
        part.save(p)
        print(' ->', p.name, box)


if __name__ == '__main__':
    main()
