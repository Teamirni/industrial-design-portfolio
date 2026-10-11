# -*- coding: utf-8 -*-
"""
动效层截图核验
==============
针对本次动效改造的两类回归风险各出一组截图：

A) 正常态（动效开启）
   · 视口内首屏必须正常渲染（封面逐字揭示、hero 擦出）
   · 用超高视口（height 9000）让整页进入视口 → 指针式扫描推进到底
     → 检验「滚动揭示后的最终版式」与静态版一致
   ⚠ 代价：封面按 min-height:100vh 会被拉到 9000px 高、比例失真。
     判断封面时请以 _shot_scroll.py（真实 900 高视口 + 滚到指定位置）为准，
     本脚本只用来确认「全部揭示完成后，页面下半部分没有缺块」。

B) 静态回退态（--force-prefers-reduced-motion）
   · 强制 prefers-reduced-motion: reduce → 页内脚本把 data-motion 置 off
   · 这是「无 JS / 打印导出 / 用户系统设置」三条路径的共同等价物
   · 检验内容是否 100% 可见 —— 若此处出现空白区块，说明初始隐藏态没兜住

相对 _shot.py 的两处加固（原脚本在本机会偶发挂死）：
  1. HTTP 服务改用 ThreadingHTTPServer：单线程 TCPServer 会被浏览器的并行
     连接请求串行化，任一连接不释放就整体阻塞。
  2. 每次截图使用独立的 --user-data-dir 临时配置目录：否则用户本机正在运行的
     Edge 会占用默认 profile，headless 实例可能挂起不退出。

用法：
  python _shot_motion.py                  # 全量
  python _shot_motion.py index.html       # 只测某页
"""
import os
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
OUT = BASE / '_shots'
OUT.mkdir(exist_ok=True)

EDGE_CANDIDATES = [
    Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
    Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
]

HOST, PORT = '127.0.0.1', 8177
TIMEOUT = 150
VTB = 6000            # virtual-time-budget：动效最长 900ms，6s 足够走完

# 高度取 9000：让整页进入视口，从而一次性验收「全部揭示完成」的版式
VIEWS = [
    ('desktop', 1440, 9000),
    ('phone', 390, 9000),
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


def shoot(edge, page, width, height, out, reduce_motion):
    profile = tempfile.mkdtemp(prefix='edge-motion-')
    url = 'http://%s:%d/%s' % (HOST, PORT, urllib.parse.quote(page))
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
        # Edge 退出后仍有少量子进程延迟释放 profile，容错删除即可
        shutil.rmtree(profile, ignore_errors=True)
    return out.exists() and out.stat().st_size > 0


def main():
    edge = find_edge()
    pages = sys.argv[1:] or [
        'index.html',
        'about.html',
        'methodology.html',
        'projects/dslr.html',
        'projects/headphones.html',
        'projects/cat-nest.html',
        'projects/offroad-toy.html',
    ]
    httpd = serve()
    ok = True
    try:
        for page in pages:
            stem = page.replace('/', '_').replace('.html', '')
            for label, w, h in VIEWS:
                for variant, flag in (('motion', False), ('static', True)):
                    out = OUT / ('%s-%s-%s.png' % (stem, label, variant))
                    good = shoot(edge, page, w, h, out, flag)
                    if not good and out.exists():
                        out.unlink()
                    ok = ok and good
                    print('%s  %-28s %-8s %-7s %s' % (
                        '✓' if good else '✗', stem, label, variant,
                        out.name if good else 'FAIL'))
    finally:
        httpd.shutdown()
    print('\n结果：', 'ALL OK' if ok else '存在失败项')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
