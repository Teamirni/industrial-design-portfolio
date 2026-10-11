# -*- coding: utf-8 -*-
"""
封面白模素材预处理 v3
=====================
v2 的亮度抠像得到动态范围不足的淡影。v3 在抠像后增加**模型区动态范围拉伸**：
只在非背景像素上统计分位数，把 [p05, p97] 线性映射到 [0, 255]，
让浅灰白模也能获得有存在感的剪影，同时保持边缘羽化溶入白底。
"""
import math
import os

from PIL import Image, ImageFilter

SRC = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/assets/images'
OUT = os.path.join(SRC, 'cover')
os.makedirs(OUT, exist_ok=True)

MAX_W = 1200


def load_gray(path, max_w=MAX_W):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    if w > max_w:
        im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
    return im.convert('L')


def bg_level(g, border=0.05):
    w, h = g.size
    bw, bh = max(1, int(w * border)), max(1, int(h * border))
    px = []
    for box in ((0, 0, w, bh), (0, h - bh, w, h), (0, 0, bw, h), (w - bw, 0, w, h)):
        px.extend(list(g.crop(box).getdata()))
    px.sort()
    return px[len(px) // 2]


def radial_feather(w, h, inner=0.72, outer=1.34, blur=10, ss=384):
    """归一化椭圆羽化遮罩：中心 255 → 边缘 0。"""
    m = Image.new('L', (ss, ss), 0)
    px = m.load()
    c = ss / 2.0
    for y in range(ss):
        dy = (y + 0.5 - c) / c
        row = m.crop((0, y, 1, y + 1))
        for x in range(ss):
            dx = (x + 0.5 - c) / c
            r = math.hypot(dx, dy)
            if r <= inner:
                a = 255
            elif r >= outer:
                a = 0
            else:
                t = (r - inner) / (outer - inner)
                a = int(round(255 * (1 - t) ** 1.4))
            px[x, y] = a
    return m.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(blur))


def stretch(raw, thresh=10, low_p=0.04, high_p=0.975, gamma=1.0):
    """在非背景像素上做动态范围拉伸，让浅色白模也获得足够 alpha。"""
    data = sorted(v for v in raw.getdata() if v > thresh)
    if len(data) < 200:
        return raw
    lo = data[int(len(data) * low_p)]
    hi = data[int(len(data) * high_p)]
    if hi - lo < 24:
        hi = lo + 24
    scale = 255.0 / (hi - lo)
    lut = []
    for v in range(256):
        if v <= lo:
            o = 0
        else:
            o = min(255.0, (v - lo) * scale)
        if gamma != 1.0:
            o = 255.0 * (o / 255.0) ** gamma
        lut.append(int(round(o)))
    return raw.point(lut)


def autocrop(alpha, pad=0.03, thresh=18):
    """裁到物体包围盒（含少量留白），去掉原图四周的大片空白。"""
    bbox = alpha.point(lambda v: 255 if v > thresh else 0).getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    w, h = alpha.size
    px, py = int((x1 - x0) * pad), int((y1 - y0) * pad)
    return (max(0, x0 - px), max(0, y0 - py), min(w, x1 + px), min(h, y1 + py))


def key_light_bg(src, dst, tone=190, offset=6, inner=0.74, outer=1.30, gamma=0.94, crop=True):
    """浅底 / 灰底白模：背景比模型亮 → alpha = 背景亮度 - 当前亮度，拉伸后羽化。"""
    g = load_gray(os.path.join(SRC, src))
    bl = bg_level(g)
    cut = bl - offset
    raw = g.point([max(0, min(255, int(cut - v))) for v in range(256)])
    alpha = stretch(raw, gamma=gamma)
    box = autocrop(alpha) if crop else None
    if box:
        alpha = alpha.crop(box)
    w, h = alpha.size
    alpha = Image.composite(alpha, Image.new('L', (w, h), 0), radial_feather(w, h, inner, outer))
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.2))
    out = Image.new('LA', (w, h))
    out.paste(Image.new('L', (w, h), tone), (0, 0))
    out.putalpha(alpha)
    out.save(dst)
    print('  LIGHT %-42s bgL=%3d 裁切=%-22s -> %s'
          % (src, bl, str(box), os.path.basename(dst)))


def key_dark_bg(src, dst, tone=196, offset=34, inner=0.86, outer=1.34, gamma=0.96, crop=True):
    """黑底白模：模型比背景亮 → alpha = 当前亮度 - 背景亮度，拉伸后羽化。"""
    g = load_gray(os.path.join(SRC, src))
    bl = bg_level(g)
    cut = bl + offset
    raw = g.point([max(0, min(255, int(v - cut))) for v in range(256)])
    alpha = stretch(raw, gamma=gamma)
    box = autocrop(alpha) if crop else None
    if box:
        alpha = alpha.crop(box)
    w, h = alpha.size
    alpha = Image.composite(alpha, Image.new('L', (w, h), 0), radial_feather(w, h, inner, outer, blur=11))
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.4))
    out = Image.new('LA', (w, h))
    out.paste(Image.new('L', (w, h), tone), (0, 0))
    out.putalpha(alpha)
    out.save(dst)
    print('  DARK  %-42s bgL=%3d 裁切=%-22s -> %s'
          % (src, bl, str(box), os.path.basename(dst)))


print('封面白模素材 →', OUT)
key_light_bg('catnest-iso.png', os.path.join(OUT, 'ghost-catnest-01.png'), tone=172)
key_light_bg('微信图片_20260813144708_35_2.png', os.path.join(OUT, 'ghost-catnest-02.png'), tone=178)
key_light_bg('headphones-clay.jpg', os.path.join(OUT, 'ghost-headphones-01.png'), tone=176)
key_light_bg('headphones-clay-side.jpg', os.path.join(OUT, 'ghost-headphones-02.png'), tone=170)
key_light_bg('dslr-right.jpg', os.path.join(OUT, 'ghost-dslr-01.png'), tone=170, inner=0.60, outer=1.28)
key_light_bg('dslr-right.jpg', os.path.join(OUT, 'ghost-dslr-02.png'), tone=174, inner=0.58, outer=1.20)
key_dark_bg('truck-shaded.jpg', os.path.join(OUT, 'ghost-truck-01.png'), tone=176)
print('完成。')
