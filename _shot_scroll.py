# -*- coding: utf-8 -*-
"""
任意滚动位置截图
================
用同源 iframe 测试台（_shot_scroll.html）驱动站点页面滚动到指定位置后截图，
用于核验「滚动揭示 / 视差 / 滚动字带 / 时间线 scrub」在真实滚动下的表现。

与 _shot_motion.py 相同的两处加固：
  · ThreadingHTTPServer（单线程 TCPServer 会被浏览器并行连接串行化而阻塞）
  · 每次调用独立的 --user-data-dir（避免与本机正在运行的 Edge 争用默认 profile）

用法：
  python _shot_scroll.py                # 跑内置用例
  python _shot_scroll.py index.html 1200 1440 900   # 单点：页面 / y / 宽 / 高
"""
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent.resolve()
OUT = BASE / '_shots' / 'scroll'
OUT.mkdir(parents=True, exist_ok=True)

EDGE_CANDIDATES = [
    Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
    Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
]

HOST, PORT = '127.0.0.1', 8179
TIMEOUT = 150
VTB = 7000

# (页面, 滚动位置, 视口宽, 视口高, 标签)
CASES = [
    ('index.html', 900, 1440, 900, 'cover-out'),          # 刚离开封面 → 导航滑入
    ('index.html', 1700, 1440, 900, 'about-section'),     # 简介区块揭示
    ('index.html', 2600, 1440, 900, 'project-grid'),      # 项目卡片网格 stagger
    ('index.html', 3900, 1440, 900, 'ticker'),            # 滚动字带
    ('projects/cat-nest.html', 700, 1440, 900, 'stage-header'),
    ('projects/cat-nest.html', 2200, 1440, 900, 'image-row'),
    ('projects/cat-nest.html', 3600, 1440, 900, 'stat-row'),
    ('about.html', 1500, 1440, 900, 'about-skills'),
    ('about.html', 2600, 1440, 900, 'about-timeline'),    # 时间线 scrub 进度线
    ('index.html', 900, 390, 844, 'phone-nav'),
    ('index.html', 2600, 390, 844, 'phone-grid'),
    ('projects/cat-nest.html', 1600, 390, 844, 'phone-image'),
]


def find_edge():
    for p in EDGE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError('未找到 Edge')


def serve():
    handler = lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(BASE), **k)
    httpd = ThreadingHTTPServer((HOST, PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1)
            return httpd
        except Exception:
            time.sleep(0.2)
    raise RuntimeError('本地服务启动失败')


def shoot(edge, url, width, height, out, reduce_motion=False):
    profile = tempfile.mkdtemp(prefix='edge-scroll-')
    cmd = [
        str(edge), '--headless', '--no-sandbox', '--disable-gpu',
        '--hide-scrollbars', '--force-device-scale-factor=1',
        '--user-data-dir=%s' % profile,
        '--virtual-time-budget=%d' % VTB,
        '--window-size=%d,%d' % (width, height),
        '--screenshot=%s' % out,
    ]
    if reduce_motion:
        cmd.append('--force-prefers-reduced-motion')
    cmd.append(url)
    try:
        subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return out.exists() and out.stat().st_size > 0


def main():
    edge = find_edge()
    httpd = serve()
    ok = True
    try:
        if len(sys.argv) >= 5:
            page = sys.argv[1]
            y, w, h = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
            cases = [(page, y, w, h, 'custom')]
        else:
            cases = CASES

        for page, y, w, h, label in cases:
            stem = page.replace('/', '_').replace('.html', '')
            url = 'http://%s:%d/_shot_scroll.html?p=%s&y=%d' % (
                HOST, PORT, urllib.parse.quote(page), y)
            out = OUT / ('%s-y%d-%s.png' % (stem, y, label))
            good = shoot(edge, url, w, h, out)
            if not good and out.exists():
                out.unlink()
            ok = ok and good
            print('%s  %-26s y=%-5d %dx%d  %s' % (
                '✓' if good else '✗', stem, y, w, h, out.name if good else 'FAIL'))
    finally:
        httpd.shutdown()
    print('\n结果：', 'ALL OK' if ok else '存在失败项')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
