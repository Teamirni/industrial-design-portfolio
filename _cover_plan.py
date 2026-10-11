# -*- coding: utf-8 -*-
"""
封面构图注册表（唯一数据源）
============================
`_gen_cover_svg.py`（生成并注入 SVG）与 `_check_composition.py`（像素级校验）
都从这里读 LAYOUTS，避免坐标在多处漂移。

双构图
------
同一组白模配两套排布，靠 CSS 断点切换（见 `_tune_cover.py` 的搜索目标）：

  wide  1620×540   桌面 / 平板横向 / A4 打印（容器实测 ~2.9:1）
  tall   800×1120  手机竖屏（容器实测 ~0.71:1）

只用一套固定比例构图时，`preserveAspectRatio="xMidYMid meet"` 在宽扁容器里
必然左右留白、在竖长容器里必然上下留白 —— 这正是「元素偏小、留白过多」的
结构性成因，靠放大物体本身解决不了。

布局数据由 `_tune_cover.py` 搜索生成并写入 `_cover_layout.json`。
几何 / 度量原语见 `_cover_geom.py`。
"""
import json
import os

from _cover_geom import (COVER, THRESH, bleed_edges, coverage, exact_gap, gaps,
                         ink_area, masks, paste_centered, raster_alpha, resolve,
                         rot_bbox, size_of, visible_fraction)

BASE = os.path.dirname(os.path.abspath(__file__))
LAYOUT_JSON = os.path.join(BASE, '_cover_layout.json')

# SVG 渲染参数
BLUR = 9          # SVG 高斯模糊半径（用户拍板保留 9 档：0.86/5 的清晰版过于「实」，失掉幽灵感）
OPACITY = 0.92
SCALE = 1.0

LAYOUT_META = {
    'wide': dict(
        cls='cover-svg cover-svg--wide',
        label='桌面与打印版封面：智能猫窝、头戴式监听耳机、模块化单反相机与越野车玩具的白模散落构图',
        note='桌面 / 平板横向 / A4 打印',
    ),
    'tall': dict(
        cls='cover-svg cover-svg--tall',
        label='移动端封面：智能猫窝、头戴式监听耳机、模块化单反相机与越野车玩具的白模纵向散落构图',
        note='手机竖屏',
    ),
}


def _load():
    if not os.path.exists(LAYOUT_JSON):
        raise FileNotFoundError(
            '缺少 %s —— 先运行 `python _tune_cover.py` 生成构图。' % LAYOUT_JSON)
    with open(LAYOUT_JSON, encoding='utf-8') as f:
        return json.load(f)


DATA = _load()
LAYOUTS = DATA['layouts']


def canvas(layout='wide'):
    L = LAYOUTS[layout]
    return L['vw'], L['vh']


def resolved(layout='wide'):
    return resolve(LAYOUTS[layout]['plan'])


def masks_of(layout='wide', ds=1):
    vw, vh = canvas(layout)
    return masks(resolved(layout), vw, vh, ds)


def coverage_of(layout='wide', ds=1):
    vw, vh = canvas(layout)
    return coverage(resolved(layout), vw, vh, ds)


def gaps_of(layout='wide', ds=2, kmax=140):
    vw, vh = canvas(layout)
    return gaps(resolved(layout), vw, vh, ds, kmax)


def bleed_of(layout='wide'):
    vw, vh = canvas(layout)
    return bleed_edges(resolved(layout), vw, vh)


def visible_of(layout='wide'):
    vw, vh = canvas(layout)
    return visible_fraction(resolved(layout), vw, vh)


def area_of(layout='wide'):
    vw, vh = canvas(layout)
    return ink_area(resolved(layout), vw, vh)


__all__ = ['COVER', 'THRESH', 'BLUR', 'OPACITY', 'SCALE', 'LAYOUTS', 'LAYOUT_META',
           'canvas', 'resolved', 'masks_of', 'coverage_of', 'gaps_of', 'bleed_of',
           'visible_of', 'area_of', 'resolve', 'raster_alpha', 'paste_centered',
           'size_of', 'rot_bbox', 'coverage', 'gaps', 'masks', 'visible_fraction',
           'ink_area', 'bleed_edges', 'exact_gap']
