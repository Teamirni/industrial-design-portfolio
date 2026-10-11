# -*- coding: utf-8 -*-
"""
生成封面 SVG 片段并注入 index.html
==================================
构图数据源统一在 `_cover_plan.py`（读取 `_cover_layout.json`），
生成器与像素级校验器共用同一份数据，避免坐标不一致。

输出**两套** SVG：
  · `cover-svg--wide`  桌面 / 平板横向 / A4 打印
  · `cover-svg--tall`  手机竖屏
由 CSS 断点切换显示。单一构图在宽扁容器里必然左右留白、在竖长容器里必然
上下留白 —— 这是「元素偏小、留白过多」的结构性成因。

每套 SVG 各带一份 `<defs>` 与独立 filter id（`ghostBlurW` / `ghostBlurT`），
避免被 `display:none` 的那一套影响另一套的滤镜解析。

写入 `_cover_svg.html`，注入 index.html 的 <!-- COVER-SVG:START/END --> 区间。
"""
import os

import _cover_plan as P

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_SVG = os.path.join(BASE, '_cover_svg.html')
INDEX = os.path.join(BASE, 'index.html')

FILTER_ID = {'wide': 'ghostBlurW', 'tall': 'ghostBlurT'}


def build_one(layout):
    items = P.resolved(layout)
    vw, vh = P.canvas(layout)
    meta = P.LAYOUT_META[layout]
    fid = FILTER_ID[layout]
    L = []
    L.append('        <svg class="%s" viewBox="0 0 %d %d" preserveAspectRatio="xMidYMid meet"'
             % (meta['cls'], vw, vh))
    L.append('             role="img" aria-label="%s">' % meta['label'])
    L.append('          <defs>')
    L.append('            <filter id="%s" x="-30%%" y="-30%%" width="160%%" height="160%%"'
             ' color-interpolation-filters="sRGB">' % fid)
    L.append('              <feGaussianBlur stdDeviation="%d"/>' % P.BLUR)
    L.append('            </filter>')
    L.append('          </defs>')
    L.append('          <g filter="url(#%s)" opacity="%s">' % (fid, P.OPACITY))
    ccx, ccy = vw / 2.0, vh / 2.0
    s = P.SCALE
    for it in items:
        w = int(round(it['w'] * s))
        h = int(round(it['h'] * s))
        nx = ccx + (it['x'] - ccx) * s
        ny = ccy + (it['y'] - ccy) * s
        L.append('            <image href="assets/images/cover/%s" width="%d" height="%d"'
                 % (it['name'], w, h))
        L.append('                   transform="translate(%.0f %.0f) rotate(%d %.1f %.1f)"/>'
                 % (nx, ny, it['rot'], w / 2.0, h / 2.0))
    L.append('          </g>')
    L.append('        </svg>')
    return '\n'.join(L)


def build_svg():
    L = []
    L.append('      <!-- 幽灵白模构图板 · 双布局。')
    L.append('           wide = 桌面 / 平板横向 / A4 打印；tall = 手机竖屏。')
    L.append('           单一构图在宽扁容器里必然左右留白、在竖长容器里必然上下留白，')
    L.append('           这是「元素偏小、留白过多」的结构性成因，故按断点各出一套画布，')
    L.append('           两套画布比例按实测容器比例设计，各自把画幅吃满。')
    L.append('           两者都在 preserveAspectRatio="xMidYMid meet" 下等比缩放：')
    L.append('           既不裁切也不变形。打印强制用 wide。')
    L.append('           本区块由 _gen_cover_svg.py 自动注入，请勿手工编辑。 -->')
    L.append(build_one('wide'))
    L.append(build_one('tall'))
    return '\n'.join(L)


def inject(svg):
    with open(INDEX, encoding='utf-8') as f:
        html = f.read()
    start, end = '<!-- COVER-SVG:START -->', '<!-- COVER-SVG:END -->'
    i, j = html.find(start), html.find(end)
    if i < 0 or j < 0:
        print('!! index.html 中未找到 COVER-SVG 标记区间，未注入')
        return False
    html = html[:i] + start + '\n' + svg + '\n      ' + end + html[j + len(end):]
    with open(INDEX, 'w', encoding='utf-8') as f:
        f.write(html)
    return True


def main():
    svg = build_svg()
    with open(OUT_SVG, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('-> 写入 %s' % OUT_SVG)
    print('-> %s index.html' % ('已注入' if inject(svg) else '注入失败'))
    print()
    print(svg)


if __name__ == '__main__':
    main()
