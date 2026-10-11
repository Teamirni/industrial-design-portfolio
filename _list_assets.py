# -*- coding: utf-8 -*-
"""列出候选素材目录中的图片文件（只列顶层，避免刀模素材库噪声）。"""
import os

DIRS = [
    r'D:/工作文件/包装设计',
    r'D:/工作文件/包装设计/文件',
    r'D:/工作文件/三维兼职',
    r'D:/工作文件/2翁彦斌',
    r'D:/工作文件/1翁彦斌',
    r'D:/工作文件/封堵器',
    r'D:/工作文件/微球',
]
EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff')

for d in DIRS:
    print('###', d)
    if not os.path.isdir(d):
        print('   (不存在)')
        continue
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            sz = os.path.getsize(p) / 1024
            mark = '  <-- IMG' if name.lower().endswith(EXT) else ''
            print('   %-58s %9.0fKB%s' % (name, sz, mark))
        else:
            print('   [DIR] %s' % name)
