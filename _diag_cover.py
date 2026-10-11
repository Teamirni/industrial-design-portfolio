# -*- coding: utf-8 -*-
"""诊断幽灵白模素材的亮度 / alpha 分布。"""
import os, glob
from PIL import Image

OUT = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/assets/images/cover'
for f in sorted(glob.glob(os.path.join(OUT, '*.png'))):
    im = Image.open(f)
    print(os.path.basename(f), im.mode, im.size)
    r, g, b, a = im.convert('RGBA').split()
    lp = list(im.convert('LA').getchannel('L').getdata())
    ap = list(im.convert('LA').getchannel('A').getdata())
    lp.sort(); ap.sort()
    n = len(lp)
    q = lambda arr, p: arr[int(n * p)]
    print('    L   p01=%3d p10=%3d p50=%3d p90=%3d p99=%3d min=%3d max=%3d' %
          (q(lp, .01), q(lp, .10), q(lp, .50), q(lp, .90), q(lp, .99), lp[0], lp[-1]))
    print('    A   p01=%3d p10=%3d p50=%3d p90=%3d p99=%3d min=%3d max=%3d' %
          (q(ap, .01), q(ap, .10), q(ap, .50), q(ap, .90), q(ap, .99), ap[0], ap[-1]))
