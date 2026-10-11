# -*- coding: utf-8 -*-
"""改动前备份 portfolio-v2 的源码文件（HTML/CSS/JS + 构建脚本）。
只备份源码，不复制 assets 与 pdf（体积大且本轮不改）。"""
import os
import shutil
import datetime

SRC = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2'
STAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
DST = os.path.join(SRC, '_bak_%s' % STAMP)

os.makedirs(DST, exist_ok=True)

count = 0
for root, dirs, files in os.walk(SRC):
    # 跳过备份目录自身、资产目录、产物目录、缓存
    dirs[:] = [d for d in dirs if d not in (
        'assets', 'pdf', '__pycache__', '_render', '_render_v2',
        '_render_v3', '_render_v4', '_render_about',
    ) and not d.startswith('_bak_')]
    for name in files:
        if name.startswith('_') and not name.startswith('_bak'):
            continue  # 跳过临时诊断脚本
        if name.endswith(('.html', '.css', '.js', '.py', '.md')) or '._bak_' in name:
            s = os.path.join(root, name)
            rel = os.path.relpath(s, SRC)
            d = os.path.join(DST, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            count += 1

print('备份目录:', DST)
print('备份文件数:', count)
