# -*- coding: utf-8 -*-
"""
封面多视口截图
==============
用本地 Edge（旧版 --headless）在桌面 / 平板 / 手机三种宽度下截图 index.html，
用于验证封面在手机端不再出现比例失调。
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

BASE = Path(r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2').resolve()
OUT = BASE / '_shots'
OUT.mkdir(exist_ok=True)

EDGE_CANDIDATES = [
    Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
    Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
]
HOST, PORT = '127.0.0.1', 8161

VIEWPORTS = [
    ('desktop-1440x900', 1440, 900),
    ('laptop-1280x800', 1280, 800),
    ('phone-390x844', 390, 844),
    ('phone-360x780', 360, 780),
]


def find_edge():
    for p in EDGE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError('未找到 Edge')


def start_server():
    import http.server
    import socketserver
    os.chdir(BASE)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer((HOST, PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def wait_server(timeout=12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    page = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    edge = find_edge()
    httpd = start_server()
    if not wait_server():
        print('服务启动失败')
        return 1
    try:
        url = 'http://%s:%d/%s' % (HOST, PORT, page)
        for name, w, h in VIEWPORTS:
            out = OUT / ('%s-%s.png' % (page.replace('/', '_').replace('.html', ''), name))
            cmd = [
                str(edge), '--headless', '--no-sandbox', '--disable-gpu',
                '--hide-scrollbars', '--force-device-scale-factor=1',
                '--virtual-time-budget=9000',
                '--window-size=%d,%d' % (w, h),
                '--screenshot=%s' % out,
                url,
            ]
            subprocess.run(cmd, capture_output=True, timeout=120)
            ok = out.exists()
            print('%s  %s  %s' % ('✓' if ok else '✗', name, out.name))
    finally:
        httpd.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
