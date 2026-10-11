# -*- coding: utf-8 -*-
"""把候选白模素材拼成一张联络表(contact sheet)，便于一次性查看。"""
import os
from PIL import Image, ImageDraw

BASE = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/assets/images'
CANDIDATES = [
    'dslr-front.jpg', 'dslr-left.jpg', 'dslr-right.jpg', 'dslr-final.jpg',
    'headphones-clay.jpg', 'headphones-clay-side.jpg',
    'catnest-iso.png', 'catnest-multi.jpg', 'cat-nest-hero-render.jpg',
    '微信图片_20260813144708_35_2.png', '微信图片_20260813144711_38_2.jpg',
    'truck-shaded.jpg', 'truck-wireframe.jpg',
    'recovered/toy-render-clean.png', 'explosion-diagram.png',
]

COLS = 5
CELL_W, CELL_H = 320, 240
PAD = 6
LABEL_H = 18

rows = (len(CANDIDATES) + COLS - 1) // COLS
W = COLS * (CELL_W + PAD) + PAD
H = rows * (CELL_H + LABEL_H + PAD) + PAD
sheet = Image.new('RGB', (W, H), (235, 235, 235))
draw = ImageDraw.Draw(sheet)

for i, name in enumerate(CANDIDATES):
    p = os.path.join(BASE, name)
    r, c = divmod(i, COLS)
    x = PAD + c * (CELL_W + PAD)
    y = PAD + r * (CELL_H + LABEL_H + PAD)
    tile = Image.new('RGB', (CELL_W, CELL_H), (255, 255, 255))
    if os.path.exists(p):
        im = Image.open(p).convert('RGB')
        im.thumbnail((CELL_W, CELL_H))
        tile.paste(im, ((CELL_W - im.size[0]) // 2, (CELL_H - im.size[1]) // 2))
    else:
        draw.text((x + 4, y + 4), 'MISSING', fill=(200, 0, 0))
    sheet.paste(tile, (x, y))
    draw.text((x + 2, y + CELL_H + 3), '%d. %s' % (i + 1, name), fill=(0, 0, 0))

out = r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2/_contact_sheet.png'
sheet.save(out)
print('SAVED', out, sheet.size)
