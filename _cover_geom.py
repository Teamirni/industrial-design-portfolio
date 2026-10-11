# -*- coding: utf-8 -*-
"""
封面构图几何原语（不依赖任何布局数据）
======================================
`_cover_plan.py`（布局注册表）与 `_tune_cover.py`（自动寻优）共用本模块，
保证「生成 SVG」与「像素级校验」用的是同一套坐标与度量。

坐标约定（★ 与 SVG 严格一致）
-----------------------------
物体记为 (name, x, y, w, rot)：
  · (x, y) 是**未旋转**矩形的左上角，h = w × 源图高宽比；
  · 旋转绕矩形中心 `(x + w/2, y + h/2)`，对应 SVG 的
    `translate(x y) rotate(rot w/2 h/2)`。

  ⚠️ 旧版校验器把 `rotate(expand=True)` 后的左上角直接贴到 (x, y)，
  与「绕中心旋转」相差 ((w−W')/2, (h−H')/2)，导致间距数据与对照图整体偏移。
  本模块统一用 `paste_centered()` 锚定中心。

越界即出血
----------
所有贴图操作在画布外自动裁剪，因此「出血」是自然结果而非特例处理。
"""
import math
import os

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
COVER = os.path.join(BASE, 'assets', 'images', 'cover')
THRESH = 30        # alpha > THRESH 视为墨迹


def size_of(name):
    with Image.open(os.path.join(COVER, name)) as im:
        return im.size


# ── 缓存：寻优会反复以同一 (尺寸, 转角, 降采样) 组合栅格化，避免重复读盘 / 重采样 ──
_SRC = {}
_MASKCACHE = {}
_CACHE_MAX = 600


def _src(name):
    a = _SRC.get(name)
    if a is None:
        with Image.open(os.path.join(COVER, name)) as im:
            a = im.convert('LA').getchannel('A').copy()
        _SRC[name] = a
    return a


def rot_bbox(cx, cy, w, h, deg):
    """绕中心旋转后的轴对齐包围盒 (x0, y0, x1, y1)。"""
    a = math.radians(deg)
    ca, sa = abs(math.cos(a)), abs(math.sin(a))
    bw, bh = w * ca + h * sa, w * sa + h * ca
    return (cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0)


def resolve(plan):
    """把 (name, x, y, w, rot) 计划展开成含实际尺寸 / 中心 / 包围盒的列表。"""
    out = []
    for name, x, y, w, rot in plan:
        sw, sh = size_of(name)
        h = int(round(w * sh / float(sw)))
        cx, cy = x + w / 2.0, y + h / 2.0
        out.append(dict(name=name, x=float(x), y=float(y), w=int(w), h=h,
                        rot=float(rot), cx=cx, cy=cy,
                        bbox=rot_bbox(cx, cy, w, h, rot)))
    return out


def raster_alpha(name, w, h, rot, ds=1):
    """缩放 + 旋转后的二值墨迹数组（尺寸为 ds 下的像素数）。

    `rotate(expand=True)` 后内容中心与原图中心重合，交由 `paste_centered` 定位。"""
    key = (name, int(w), int(h), round(float(rot), 3), int(ds))
    hit = _MASKCACHE.get(key)
    if hit is not None:
        return hit
    a = _src(name)
    tw, th = max(2, int(round(w / float(ds)))), max(2, int(round(h / float(ds))))
    a = a.resize((tw, th), Image.LANCZOS)
    a = a.rotate(rot, expand=True, resample=Image.BICUBIC)
    arr = np.asarray(a) > THRESH
    if len(_MASKCACHE) > _CACHE_MAX:
        _MASKCACHE.clear()
    _MASKCACHE[key] = arr
    return arr


def paste_centered(canvas_arr, arr, cx, cy, ds=1):
    """把 arr 按**中心** (cx, cy) 画布坐标贴入 canvas_arr，越界自动裁剪（= 出血）。"""
    ch, cw = canvas_arr.shape
    ah, aw = arr.shape
    x0 = int(round(cx / float(ds) - aw / 2.0))
    y0 = int(round(cy / float(ds) - ah / 2.0))
    x1, y1 = x0 + aw, y0 + ah
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(cw, x1), min(ch, y1)
    if sx1 <= sx0 or sy1 <= sy0:
        return False
    canvas_arr[sy0:sy1, sx0:sx1] |= arr[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0]
    return True


def _canvas_shape(vw, vh, ds):
    return (max(1, int(round(vh / float(ds)))), max(1, int(round(vw / float(ds)))))


def masks(items, vw, vh, ds=1):
    """{name: 画布尺寸的二值墨迹数组}。"""
    out = {}
    for it in items:
        arr = raster_alpha(it['name'], it['w'], it['h'], it['rot'], ds)
        m = np.zeros(_canvas_shape(vw, vh, ds), dtype=bool)
        paste_centered(m, arr, it['cx'], it['cy'], ds)
        out[it['name']] = m
    return out


def stats(items, vw, vh, ds=1):
    """一次栅格化同时得到覆盖率 / 出血 / 可见比例 / 墨迹面积（寻优内循环用）。

    比分别调用 `coverage` + `bleed_edges` + `visible_fraction` + `ink_area`
    省掉三次重复栅格化。"""
    ch, cw = _canvas_shape(vw, vh, ds)
    union = np.zeros((ch, cw), dtype=bool)
    bleed, vis, area, inkbox = {}, {}, {}, {}
    factor = float(ds) * float(ds)
    for it in items:
        arr = raster_alpha(it['name'], it['w'], it['h'], it['rot'], ds)
        m = np.zeros((ch, cw), dtype=bool)
        paste_centered(m, arr, it['cx'], it['cy'], ds)
        union |= m
        n = int(m.sum())
        e = []
        if n:
            rows, cols = m.any(axis=1), m.any(axis=0)
            if cols[0]:
                e.append('左')
            if rows[0]:
                e.append('上')
            if cols[-1]:
                e.append('右')
            if rows[-1]:
                e.append('下')
        bleed[it['name']] = e
        tot = int(arr.sum())
        vis[it['name']] = (n / float(tot)) if tot else 0.0
        area[it['name']] = int(round(n * factor))
        if n:
            ys, xs = np.where(m)
            inkbox[it['name']] = (float(xs.min()) * ds, float(ys.min()) * ds,
                                  float(xs.max()) * ds, float(ys.max()) * ds)
        else:
            inkbox[it['name']] = (0.0, float(vh), 0.0, float(vh))
    return dict(cov=float(union.sum()) / union.size, bleed=bleed, vis=vis, area=area,
                inkbox=inkbox, union=union)


def coverage(items, vw, vh, ds=1):
    """画幅被墨迹覆盖的比例。"""
    ms = masks(items, vw, vh, ds)
    union = np.zeros(_canvas_shape(vw, vh, ds), dtype=bool)
    for m in ms.values():
        union |= m
    return float(union.sum()) / union.size


def _dilate_cheb(mask, radius=1):
    """二值图像的切比雪夫半径膨胀（迭代 3×3 八邻域）。

    ⚠️ 不用 PIL 的 `ImageFilter.MaxFilter`：它在核宽大时不仅 O(k²)、常数还极大，
    实测 `MaxFilter(25)` 在 200×340 的小图上就要 62ms，直接拖垮寻优。
    numpy 迭代同尺寸同半径约 4–6ms，快两个数量级。"""
    m = mask
    for _ in range(int(radius)):
        p = np.pad(m, 1, constant_values=False)
        m = (p[0:-2, 0:-2] | p[0:-2, 1:-1] | p[0:-2, 2:] |
             p[1:-1, 0:-2] | p[1:-1, 1:-1] | p[1:-1, 2:] |
             p[2:,   0:-2] | p[2:,   1:-1] | p[2:,   2:])
    return m


def exact_gap(arrA, cenA, arrB, cenB, vw, vh, kmax=150, ds=2):
    """两物体**真实墨迹**最小间距（切比雪夫近似，换算回画布像素）。

    把两者贴进同一块 ds 降采样画布、裁到并集窗口，然后**线性膨胀 A**：
    第一次与 B 相交时的半径减一，即「恰好不相交」的最大膨胀半径，也就是间距下界。
    线性扫描的总迭代数 = 真实间距/ds，比二分的 ~2k 更省，且间距越紧越快。"""
    cw, ch = _canvas_shape(vw, vh, ds)[1], _canvas_shape(vw, vh, ds)[0]
    A = np.zeros((ch, cw), dtype=bool)
    B = np.zeros((ch, cw), dtype=bool)
    if not paste_centered(A, arrA, cenA[0], cenA[1], ds):
        return kmax
    if not paste_centered(B, arrB, cenB[0], cenB[1], ds):
        return kmax
    ys, xs = np.where(A | B)
    if ys.size == 0:
        return kmax
    k = max(1, int(round(kmax / float(ds))))
    # 先用两者墨迹的包围盒做下界预筛：切比雪夫距离已超上限就直接返回，省掉线性扫描
    ay, ax = np.where(A)
    by, bx = np.where(B)
    if ay.size and by.size:
        dx = max(int(ax.min()) - int(bx.max()), int(bx.min()) - int(ax.max()), 0)
        dy = max(int(ay.min()) - int(by.max()), int(by.min()) - int(ay.max()), 0)
        if max(dx, dy) > k:
            return kmax
    y0 = max(0, ys.min() - k); y1 = min(ch, ys.max() + k + 1)
    x0 = max(0, xs.min() - k); x1 = min(cw, xs.max() + k + 1)
    A = A[y0:y1, x0:x1]
    B = B[y0:y1, x0:x1]

    if (A & B).any():
        return 0
    grown = A
    for r in range(1, k + 1):
        grown = _dilate_cheb(grown, 1)
        if (grown & B).any():
            return (r - 1) * ds
    return kmax


def gaps(items, vw, vh, ds=2, kmax=140):
    """{(nameA, nameB): 真实最小间距}。"""
    arrs, cens, names = [], [], []
    for it in items:
        arrs.append(raster_alpha(it['name'], it['w'], it['h'], it['rot'], ds))
        cens.append((it['cx'], it['cy']))
        names.append(it['name'])
    out = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out[(names[i], names[j])] = exact_gap(
                arrs[i], cens[i], arrs[j], cens[j], vw, vh, kmax, ds)
    return out


def bleed_edges(items, vw, vh, ds=1):
    """各物体压出了哪几条画布边。"""
    ms = masks(items, vw, vh, ds)
    out = {}
    for it in items:
        ys, xs = np.where(ms[it['name']])
        if ys.size == 0:
            out[it['name']] = []
            continue
        e = []
        if xs.min() <= 0:
            e.append('左')
        if ys.min() <= 0:
            e.append('上')
        if xs.max() >= ms[it['name']].shape[1] - 1:
            e.append('右')
        if ys.max() >= ms[it['name']].shape[0] - 1:
            e.append('下')
        out[it['name']] = e
    return out


def visible_fraction(items, vw, vh, ds=1):
    """各物体墨迹落在画布内的比例（太低就辨识不出）。"""
    out = {}
    for it in items:
        full = raster_alpha(it['name'], it['w'], it['h'], it['rot'], ds)
        total = int(full.sum())
        if total == 0:
            out[it['name']] = 0.0
            continue
        m = np.zeros(_canvas_shape(vw, vh, ds), dtype=bool)
        paste_centered(m, full, it['cx'], it['cy'], ds)
        out[it['name']] = float(m.sum()) / total
    return out


def ink_area(items, vw, vh, ds=1):
    """各物体在画布内的墨迹像素数。"""
    ms = masks(items, vw, vh, ds)
    factor = float(ds * ds)
    return {k: int(round(v.sum() * factor)) for k, v in ms.items()}
