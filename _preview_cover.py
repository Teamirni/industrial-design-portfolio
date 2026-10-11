# -*- coding: utf-8 -*-
"""封面构图预览：把幽灵白模按封面草稿的位置关系叠放 + 高斯模糊，确认视觉。"""
import os
from PIL import Image, ImageFilter

OUT = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/assets/images/cover'

# (文件名, x, y, 宽度, 旋转角度) —— 凌乱散落，左下留出排版区
PLAN = [
    ('ghost-catnest-01.png',    110,  10, 790,  -7),
    ('ghost-headphones-01.png', 1020,  0, 425,  11),
    ('ghost-truck-01.png',       560, 240, 630,   6),
    ('ghost-dslr-01.png',        140, 330, 690,  -4),
    ('ghost-catnest-02.png',    1030, 490, 530,   4),
    ('ghost-headphones-02.png',  800, 560, 380, -12),
]

W, H = 1600, 1000
BLUR = 8


def build(blur=BLUR, save=None, label=True):
    sheet = Image.new('RGB', (W, H), (255, 255, 255))
    for name, x, y, w, rot in PLAN:
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            print('MISSING', name)
            continue
        im = Image.open(p).convert('RGBA')
        ratio = im.size[1] / float(im.size[0])
        im = im.resize((w, max(1, int(w * ratio))), Image.LANCZOS)
        im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
        sheet.paste(im, (x, y), im)
    sheet = sheet.filter(ImageFilter.GaussianBlur(blur))
    if save:
        sheet.save(save)
        print('SAVED', save)


build(save=r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/_cover_preview.png')
