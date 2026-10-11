# -*- coding: utf-8 -*-
import os, glob
from PIL import Image

base = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/assets/images'
files = sorted(glob.glob(base + '/*') + glob.glob(base + '/recovered/*'))
for f in files:
    if os.path.isfile(f) and f.lower().endswith(('.jpg', '.png', '.jpeg')):
        try:
            im = Image.open(f)
            print('%-52s %sx%s  %sKB' % (os.path.relpath(f, base), im.size[0], im.size[1], os.path.getsize(f) // 1024))
        except Exception as e:
            print(f, 'ERR', e)
