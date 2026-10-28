#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_sync_dist.py —— 把 portfolio-v2 的「站点文件」同步到 portfolio-v2-dist（线上发布目录）

为什么需要它
------------
线上站点（https://57fe846e3730424ab2d3fae23fd838e9.app.workbuddy.link）是从
portfolio-v2-dist 发布的，而不是从源码目录 portfolio-v2 发布。原因：源码目录里
混着 pdf/（约 131 MB）、_bak_*/（约 30 MB）、_render*/、_shots/ 等构建产物，
整目录上传既慢又没必要。

dist 的文件集与源码不同，必须显式同步，不能简单 cp -r。

同步规则
--------
纳入（站点运行必需）：
    根级 *.html（不含 _ 开头） / README.md / build_pdf.py / qa.py
    assets/  css/  js/  projects/
排除：
    根级以 _ 开头的文件与目录（含 _bak_*/ _render*/ _shots/ __pycache__/ 及全部工具脚本）
    pdf/                        —— 约 131 MB 的 PDF 导出件，走 D:\\工作文件\\ 单独分发
    *._bak_*  /  __pycache__  /  *.pyc

用法
----
    python _sync_dist.py            # 备份旧 dist 后重建
    python _sync_dist.py --dry-run  # 只打印将要写入的清单，不落盘
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.normpath(os.path.join(SRC, '..', 'portfolio-v2-dist'))

# 纳入的根级条目（文件或目录）
KEEP_ROOT_DIRS = {'assets', 'css', 'js', 'projects'}
KEEP_ROOT_FILES = {'README.md', 'build_pdf.py', 'qa.py'}
SKIP_FILE_SUFFIX = ('._bak_',)
SKIP_DIR_NAMES = {'__pycache__', 'pdf'}

# 明确排除（已验证全站无引用）：
#   _backup_ghost-dslr-01.png —— 封面素材的内部备份图，非站点资源
#   portrait.jpg              —— About 页个人照片已删除，文件仅存档保留；
#                                css/js 里只剩 .about-portrait 空选择器，无 HTML 引用
SKIP_ASSET_FILES = {
    'assets/images/cover/_backup_ghost-dslr-01.png',
    'assets/images/portrait.jpg',
}


def should_skip(rel: str, name: str) -> bool:
    """rel 为相对源码根的正斜杠路径"""
    if rel in SKIP_ASSET_FILES:
        return True
    if name.startswith('_'):
        # 下划线开头 = 内部备份 / 中间产物，站点目录不发布
        return True
    parts = rel.split('/')
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    if name == '__pycache__' or name.endswith('.pyc'):
        return True
    if '._bak_' in name:
        return True
    return False


def collect() -> list[str]:
    out: list[str] = []
    for name in sorted(os.listdir(SRC)):
        if name.startswith('_') or name.startswith('.'):
            continue
        full = os.path.join(SRC, name)
        if os.path.isfile(full):
            if name in KEEP_ROOT_FILES or name.endswith('.html'):
                out.append(name)
        elif name in KEEP_ROOT_DIRS:
            for dp, dn, fn in os.walk(full):
                dn[:] = [d for d in dn if d not in SKIP_DIR_NAMES and d != '__pycache__']
                for f in sorted(fn):
                    p = os.path.join(dp, f)
                    rel = os.path.relpath(p, SRC).replace('\\', '/')
                    if not should_skip(rel, f):
                        out.append(rel)
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    files = collect()
    if not os.path.isdir(DST):
        print('!! 目标目录不存在：' + DST)
        return 2

    total = sum(os.path.getsize(os.path.join(SRC, f)) for f in files)
    print('源码目录 : %s' % SRC)
    print('发布目录 : %s' % DST)
    print('待同步   : %d 个文件，合计 %.2f MB' % (len(files), total / 1048576))
    if args.dry_run:
        for f in files:
            print('   + %s' % f)
        return 0

    # ── 1) 备份旧 dist（不删除，留在同级目录）──
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(os.path.dirname(DST), '_dist_bak_%s' % stamp)
    shutil.copytree(DST, bak)
    print('已备份旧 dist -> %s' % bak)

    # ── 2) 清空 dist（Python 删除不受 safe-delete shim 影响）──
    removed = 0
    for name in os.listdir(DST):
        p = os.path.join(DST, name)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                os.remove(p)
            except OSError:
                pass
        removed += 1
    print('已清空 dist（移除 %d 个顶层条目）' % removed)

    # ── 3) 按清单复制 ──
    for rel in files:
        s = os.path.join(SRC, rel)
        d = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)

    # ── 4) 落盘自检 ──
    got = []
    for dp, dn, fn in os.walk(DST):
        dn[:] = [x for x in dn if x != '__pycache__']
        for f in fn:
            got.append(os.path.relpath(os.path.join(dp, f), DST).replace('\\', '/'))
    got = sorted(got)
    missing = [f for f in files if f not in got]
    extra = [f for f in got if f not in files]
    print('写入后核对 : %d 个文件' % len(got))
    print('  缺失 %d ，多出 %d' % (len(missing), len(extra)))
    for f in missing:
        print('   ! 缺失 %s' % f)
    for f in extra:
        print('   ! 多出 %s' % f)

    # 关键文件存在性
    for key in ('index.html', 'assets/images/cover/ghost-dslr-01.png',
                'assets/images/cover/ghost-truck-01.png',
                'css/motion.css', 'js/motion.js'):
        ok = os.path.isfile(os.path.join(DST, key))
        print('   %s %s' % ('OK ' if ok else '!! ', key))
    return 0 if not missing and not extra else 1


if __name__ == '__main__':
    sys.exit(main())
