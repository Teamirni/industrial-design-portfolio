# -*- coding: utf-8 -*-
"""
封面构图 · 像素级校验（双布局）
==============================
对 `_cover_plan.py` 里的每一套布局输出：
  · 物体清单（旋转后包围盒）
  · 画幅饱满度（真实墨迹覆盖率）
  · 物体间**真实墨迹**最小间距（按 alpha 形状，不是矩形包围盒）
  · 出血检查（压出画布边 = 饱满感来源）
  · 可见比例（落在画布内的墨迹占比，太低就辨识不出）
  · 构图对照图 `_cover_plan_preview_<layout>.png`

对照图用 `_cover_geom.paste_centered` 按**中心**锚定，与 SVG 的
`translate(x y) rotate(rot w/2 h/2)` 完全一致，不再有旧版左上角贴图的偏移。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

import _cover_plan as P
import _cover_geom as G

BASE = os.path.dirname(os.path.abspath(__file__))

# 合格线必须与 `_tune_cover.SPEC` 的 gmin 同向，否则校验器比寻优器还松、形同虚设。
# 当前 SPEC：wide gmin=62（越野车↔单反 104）、tall gmin=35（斜向两对 59）。
GMIN_OK = {'wide': 60, 'tall': 34}     # 各布局的最小间距合格线
# 覆盖率只做「是否空旷 / 是否拥挤」的粗判，不追高：极简黑白封面本就该留白。
# 历史：曾按旧版构图设成 0.36–0.56，双构图落地后实际落在 0.27–0.32，一直误报「需调整」。
COV_LO, COV_HI = 0.22, 0.45


def preview(layout):
    items = P.resolved(layout)
    vw, vh = P.canvas(layout)
    sheet = Image.new('RGB', (vw, vh), (255, 255, 255))
    for it in items:
        with Image.open(os.path.join(G.COVER, it['name'])) as im:
            rgba = im.convert('RGBA').resize((it['w'], it['h']), Image.LANCZOS)
        rgba = rgba.rotate(it['rot'], expand=True, resample=Image.BICUBIC)
        # PIL 的 rotate(expand=True) 以**内容中心**为轴，与 SVG
        # `translate(x y) rotate(rot w/2 h/2)` 一致 → 直接按中心对齐贴图。
        rw, rh = rgba.size
        px = int(round(it['cx'] - rw / 2.0))
        py = int(round(it['cy'] - rh / 2.0))
        sheet.paste(rgba, (px, py), rgba)
    sheet = sheet.filter(ImageFilter.GaussianBlur(P.BLUR))
    out = os.path.join(BASE, '_cover_plan_preview_%s.png' % layout)
    sheet.save(out)
    return out


def check(layout):
    items = P.resolved(layout)
    vw, vh = P.canvas(layout)
    gmin = GMIN_OK[layout]

    print('\n' + '=' * 62)
    print('布局 %s   画布 %d×%d  (%.3f:1)   标签 %s'
          % (layout.upper(), vw, vh, vw / float(vh), P.LAYOUT_META[layout]['note']))
    print('=' * 62)

    print('\n--- 物体清单（旋转后包围盒）---')
    for it in items:
        b = it['bbox']
        print('  %-16s %4dx%-4d 旋转 %+3d°  bbox [%6.0f,%6.0f → %6.0f,%6.0f]'
              % (it['name'].replace('ghost-', '').replace('.png', ''),
                 it['w'], it['h'], it['rot'], b[0], b[1], b[2], b[3]))

    cov = P.coverage_of(layout)
    print('\n--- 画幅饱满度 ---')
    print('  墨迹覆盖率 %.1f%%   合格区间 %.0f%%–%.0f%%   %s'
          % (cov * 100, COV_LO * 100, COV_HI * 100,
             'OK' if COV_LO <= cov <= COV_HI else '需调整'))

    print('\n--- 物体间真实墨迹最小间距（按 alpha 形状）---')
    gp = P.gaps_of(layout, ds=2, kmax=200)
    worst = 999
    for (a, b), v in sorted(gp.items(), key=lambda kv: kv[1]):
        worst = min(worst, v)
        print('  %s%-15s ↔ %-15s %4d px'
              % ('OK ' if v >= gmin else '!! ',
                 a.replace('ghost-', '').replace('.png', ''),
                 b.replace('ghost-', '').replace('.png', ''), v))
    print('  最小间距 %d px  合格线 %d px → %s'
          % (worst, gmin, '通过' if worst >= gmin else '需要拉开'))

    print('\n--- 出血 / 可见比例 ---')
    bl, vi, ar = P.bleed_of(layout), P.visible_of(layout), P.area_of(layout)
    for n in bl:
        short = n.replace('ghost-', '').replace('.png', '')
        flag = '  ' if bl[n] else '!!'
        print('  %s%-16s 出血 %-8s 可见 %5.1f%%   墨迹 %7d px²'
              % (flag, short, '、'.join(bl[n]) or '—', vi[n] * 100, ar[n]))

    out = preview(layout)
    print('\n构图对照图 →', out)
    return cov, worst


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    layouts = [only] if only else ['wide', 'tall']
    summary = {}
    for lay in layouts:
        summary[lay] = check(lay)
    print('\n' + '=' * 62)
    print('汇总')
    for lay, (cov, worst) in summary.items():
        print('  %-6s 覆盖率 %5.1f%%   最小间距 %3d px' % (lay, cov * 100, worst))


if __name__ == '__main__':
    main()
