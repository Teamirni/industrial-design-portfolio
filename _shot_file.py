# -*- coding: utf-8 -*-
"""对任意本地 HTML 文件做多视口截图。用法：_shot_file.py <html绝对路径> [宽度...]"""
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
if not EDGE.exists():
    EDGE = Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe')

HOST, PORT = '127.0.0.1', 8173


def main():
    target = Path(sys.argv[1]).resolve()
    widths = [int(x) for x in sys.argv[2:]] or [1360]
    outdir = target.parent / '_shots'
    outdir.mkdir(exist_ok=True)

    cwd = os.getcwd()
    os.chdir(target.parent)

    import http.server
    import socketserver
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer((HOST, PORT), handler)
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
        for w in widths:
            h = 2000
            out = outdir / ('%s-%d.png' % (target.stem, w))
            subprocess.run([
                str(EDGE), '--headless', '--no-sandbox', '--disable-gpu',
                '--hide-scrollbars', '--force-device-scale-factor=1',
                '--virtual-time-budget=9000',
                '--window-size=%d,%d' % (w, h),
                '--screenshot=%s' % out, url,
            ], capture_output=True, timeout=180)
            print('%s %s' % ('OK ' if out.exists() else 'FAIL', out))
    finally:
        httpd.shutdown()
        os.chdir(cwd)


if __name__ == '__main__':
    main()
