# -*- coding: utf-8 -*-
"""
封面构图自动寻优
================
同一组白模生成两套排布（宽幅 / 竖幅），输出 `_cover_layout.json`。

为什么需要两套
--------------
`preserveAspectRatio="xMidYMid meet"` 下，构图板只能等比缩放去适配容器。
容器实测比例：桌面 1383×473 ≈ 2.9:1，手机 390×553 ≈ 0.71:1。
一块固定比例构图在两者之间必然有一边大面积留白 —— 实测桌面左右各空 271px、
手机上下各空 167px。这就是「元素偏小、留白过多」的结构性成因。
所以按断点给两套画布，各自把画幅吃满。

搜索目标
--------
① 墨迹覆盖率尽量高，并落在 [COV_MIN, COV_MAX]
② 两两**真实墨迹**最小间距 ≥ GMIN（按 alpha 形状，不是矩形包围盒）
③ 每个物体至少压出一条画布边（出血 → 饱满感）
④ 每个物体至少 VIS_MIN 的墨迹落在画布内（可辨识）
⑤ 体量层级分明：最大墨迹 : 最小墨迹 ∈ [HIER_LO, HIER_HI]
⑥ 墨迹重心靠近画布中心（视觉重心）

两阶段
------
Phase 1  位置爬山。尺寸固定，掩码只栅格化一次，评估极快；
         用**旋转包围盒间距**作下界（墨迹 ⊆ 包围盒 ⇒ 真实间距 ≥ 包围盒间距），
         因此 Phase 1 的解天然满足真实间距约束。
Phase 2  在真实墨迹间距刚好触到 GMIN 的前提下，二分放大统一尺寸系数 λ，
         再逐物体贪心补量 —— 直接回应「元素太小」。
"""
import json
import math
import os
import random
import time

import numpy as np

import _cover_geom as G

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(BASE, '_cover_layout.json')

GMIN = 42          # 真实墨迹最小间距下限（画布像素，宽幅基准）
COV_MIN, COV_MAX = 0.40, 0.56
VIS_MIN = 0.30     # 物体墨迹落在画布内的最低比例
HIER_LO, HIER_HI = 1.6, 3.4
CELL_MIN = 0.20    # 网格空置线：4×3 格内墨迹率低于此值即计罚
DS = 3             # Phase 1 降采样倍率（越小越准、越慢）

# ── 两套布局 ──
# 画布比例必须等于**实测容器比例**，否则 preserveAspectRatio="meet" 会留白带：
#   桌面 1440×563 = 2.558   → wide 1620×633
#   手机  390×631 = 0.618   → tall  915×1480
# （去掉顶栏 + 构图零上边距后的实测值，见 _measure_cover.py）
SPEC = {
    'wide': dict(
        vw=1620, vh=633, gmin=62, top_pad=26, hier_hi=6.0,
        # 按物体对的独立间距要求：高斯模糊后视觉间隙会比几何间隙小，
        # 越野车与相机在斜向相邻，需要更大的几何间隙才读得出分离。
        pair_min={('ghost-dslr-01.png', 'ghost-truck-01.png'): 104},
        # 中间主体 = 智能猫窝 + 越野车玩具；头戴耳机与单反退到左右两侧。
        # 数组按 左→右 排列，与 zones 一一对应（zones 为归一化中心 x 区间）。
        cands=[
            ('ghost-headphones-01.png', [300, 340, 380, 420],  16),
            ('ghost-catnest-01.png',    [560, 620, 680, 740], -10),
            ('ghost-truck-01.png',      [620, 680, 740, 800],   8),
            ('ghost-dslr-01.png',       [420, 470, 520, 570], -14),
        ],
        zones=[(0.03, 0.19), (0.26, 0.42), (0.56, 0.72), (0.81, 0.97)],
    ),
    'tall': dict(
        # 竖版用户反馈「图片较为紧凑、模型展示不出来」——诉求与横版相反：
        # 横版要大要出血要饱满，竖版要**舒展**且**模型完整**。
        # 故：不强制出血（w_bleed=0）、可见率下限提到 0.96（几乎完整呈现）、
        # 覆盖率上限压到 0.28（宁可留白也不要挤）。
        #
        # ★ 2026-10-11 用户反馈：竖版里「单反的镜筒下段与玩具车白模糊在一起」。
        #   实测该对真实墨迹间距确有 60px，但**宽幅下限 58 是按画布宽等比换算来的，
        #   在竖版并不等价**——竖版各件体量占比更大，同样的绝对间距观感更挤，
        #   再叠加 SVG 的 feGaussianBlur(σ=9) 约 27px 晕影，两件就被「连」成一体。
        #   故对三处紧邻的「关键对」单独加码，通用下限仍保留 58。
        vw=915, vh=1480, gmin=58, top_pad=28, hier_hi=HIER_HI,
        pair_min={
            # ⚠️ 键必须按字母序（pair_req 用 tuple(sorted(...)) 查表），否则静默失配
            ('ghost-catnest-01.png', 'ghost-headphones-01.png'): 80,    # 猫窝右缘 ↔ 耳机左缘
            ('ghost-dslr-01.png', 'ghost-headphones-01.png'): 104,      # 单反机身右上 ↔ 耳机左耳罩
            ('ghost-dslr-01.png', 'ghost-truck-01.png'): 130,           # 镜筒下段 ↔ 玩具车上缘
            # ★ 130 是实测扫描出的甜点：单反仍保 586 宽（原 617），覆盖率仅由 25.3% 降到 23.3%，
            #   而该对间距由 60px 提到 134px —— 加大到 150 会把单反压到 545、覆盖率跌到 22.3%，
            #   收益递减。改这组数前请重跑 _tune_cover.tune('tall') 的扫描再定。
        },
        vis_min=0.96, w_bleed=0.0, cov_max=0.28, cov_min=0.05,
        # 尺寸界放宽以便寻优器为拉开间距而收体量；上限 1.02 保证不被放大到出框
        bound_lo=0.84, bound_hi=1.02,
        # 体量整体收一档（原尺寸 ×0.84），给间距腾出空间
        cands=[
            ('ghost-catnest-01.png',    [520, 580, 645, 705], -10),
            ('ghost-headphones-01.png', [285, 320, 360, 400],  15),
            ('ghost-dslr-01.png',       [425, 475, 525, 575], -13),
            ('ghost-truck-01.png',      [460, 515, 570, 625],   8),
        ],
        zones=None,
    ),
}


# ─────────────── 几何小工具 ───────────────

def _h_of(name, w):
    sw, sh = G.size_of(name)
    return int(round(w * sh / float(sw)))


def _bbox_of(cx, cy, w, h, rot):
    return G.rot_bbox(cx, cy, w, h, rot)


def pair_req(layout, a, b):
    """某一对物体之间的最小间距要求（未配置则用布局的全局底线）。"""
    sp = SPEC[layout]
    pm = sp.get('pair_min') or {}
    return pm.get(tuple(sorted((a, b))), sp['gmin'])


def pair_req_map(layout):
    """展开成 {(nameA, nameB): 要求值}，供批量检查用。"""
    sp = SPEC[layout]
    names = [c[0] for c in sp['cands']]
    out = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out[(names[i], names[j])] = pair_req(layout, names[i], names[j])
    return out


def _bbox_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy) if dx and dy else dx + dy


# ─────────────── 评估 ───────────────

class Evaluator:
    """固定尺寸组合下的快速评估（掩码只栅格化一次）。"""

    def __init__(self, layout, sizes):
        sp = SPEC[layout]
        self.layout, self.vw, self.vh = layout, sp['vw'], sp['vh']
        self.gmin = sp['gmin']
        self.hier_hi = sp.get('hier_hi', HIER_HI)
        self.zones = sp.get('zones')
        # 逐布局的目标权重（竖版要「舒展 + 完整」，与横版「饱满 + 出血」诉求不同）
        self.vis_min = sp.get('vis_min', VIS_MIN)
        self.cov_min = sp.get('cov_min', COV_MIN)
        self.cov_max = sp.get('cov_max', COV_MAX)
        self.w_cov = sp.get('w_cov', 1000.0)
        self.w_bleed = sp.get('w_bleed', 500.0)
        self.w_cent = sp.get('w_cent', 1500.0)
        self.names = [c[0] for c in sp['cands']]
        self.rots = [c[2] for c in sp['cands']]
        self.ws = list(sizes)
        self.hs = [_h_of(n, w) for n, w in zip(self.names, self.ws)]
        self.masks = [G.raster_alpha(n, w, h, r, DS)
                      for n, w, h, r in zip(self.names, self.ws, self.hs, self.rots)]
        self.ch = max(1, int(round(self.vh / float(DS))))
        self.cw = max(1, int(round(self.vw / float(DS))))

    def score(self, centers, detail=False):
        n = len(centers)
        # 逐物体栅格化一次，同时累积并集（避免重复分配）
        ms = []
        union = np.zeros((self.ch, self.cw), dtype=bool)
        for i in range(n):
            m = np.zeros((self.ch, self.cw), dtype=bool)
            G.paste_centered(m, self.masks[i], centers[i][0], centers[i][1], DS)
            ms.append(m)
            union |= m
        cov = float(union.sum()) / union.size

        bbs = [_bbox_of(centers[i][0], centers[i][1], self.ws[i], self.hs[i], self.rots[i])
               for i in range(n)]

        gap_short = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                req = pair_req(self.layout, self.names[i], self.names[j])
                gap_short += max(0.0, req - _bbox_gap(bbs[i], bbs[j]))

        n_nobleed = 0
        vis_short = 0.0
        areas = []
        for i in range(n):
            m = ms[i]
            rows = m.any(axis=1)
            cols = m.any(axis=0)
            if not (cols[0] or rows[0] or cols[-1] or rows[-1]):
                n_nobleed += 1
            a = int(m.sum())
            areas.append(a)
            total = int(self.masks[i].sum())
            if total > 0:
                vis_short += max(0.0, self.vis_min - a / float(total))

        amin = max(1, min(areas))
        hier_pen = 0.0
        ratio = max(areas) / float(amin)
        if ratio < HIER_LO:
            hier_pen = HIER_LO - ratio
        elif ratio > self.hier_hi:
            hier_pen = ratio - self.hier_hi

        # 分区：中间主体必须落在中央区段，两侧物体必须靠边
        zone_pen = 0.0
        if self.zones:
            for i, (lo, hi) in enumerate(self.zones):
                fx = centers[i][0] / float(self.vw)
                zone_pen += max(0.0, lo - fx) + max(0.0, fx - hi)

        # 墨迹重心
        ys, xs = np.where(union)
        if xs.size:
            gx = (xs.mean() * DS - self.vw / 2.0) / (self.vw / 2.0)
            gy = (ys.mean() * DS - self.vh / 2.0) / (self.vh / 2.0)
        else:
            gx = gy = 9.0
        cent_pen = max(0.0, abs(gx) - 0.24) + max(0.0, abs(gy) - 0.30)

        s = (self.w_cov * cov
             - 12.0 * gap_short
             - self.w_bleed * n_nobleed
             - 4000.0 * vis_short
             - 300.0 * hier_pen
             - 6000.0 * zone_pen
             - self.w_cent * cent_pen
             - 3000.0 * max(0.0, cov - self.cov_max)
             - 6000.0 * max(0.0, self.cov_min - cov))
        if detail:
            return s, dict(cov=cov, gap_short=gap_short, n_nobleed=n_nobleed,
                           vis_short=vis_short, hier=ratio, gx=gx, gy=gy)
        return s


# ─────────────── Phase 1：位置爬山 ───────────────

def climb(ev, centers, rounds=26, seed_step=64):
    centers = [list(c) for c in centers]
    best = ev.score(centers)
    step = seed_step
    rng = random.Random(12345)
    for _ in range(rounds):
        improved = False
        order = list(range(len(centers)))
        rng.shuffle(order)
        for i in order:
            bx, by = centers[i]
            bs = best
            for dx, dy in ((0, 0), (step, 0), (-step, 0), (0, step), (0, -step),
                           (step, step), (-step, -step), (step, -step), (-step, step)):
                centers[i] = [bx + dx, by + dy]
                s = ev.score(centers)
                if s > bs + 1e-9:
                    bs, best = s, s
                    bx, by = centers[i]
                    improved = True
            centers[i] = [bx, by]
        if not improved:
            step /= 2.0
            if step < 6:
                break
    return centers, best


def random_seed(ev, rng):
    n = len(ev.names)
    vw, vh = ev.vw, ev.vh
    cs = []
    for i in range(n):
        if vw >= vh:
            # 有分区就用分区中点起步，否则沿画幅横向铺开
            if ev.zones:
                lo, hi = ev.zones[i]
                cx = vw * ((lo + hi) / 2.0 + rng.uniform(-0.06, 0.06))
            else:
                cx = vw * (i + 0.5) / n + rng.uniform(-0.18, 0.18) * vw
            cy = vh * (0.34 if i % 2 == 0 else 0.70) + rng.uniform(-0.18, 0.18) * vh
        else:
            cx = vw * (0.32 if i % 2 == 0 else 0.70) + rng.uniform(-0.20, 0.20) * vw
            cy = vh * (i + 0.5) / n + rng.uniform(-0.16, 0.16) * vh
        cs.append([cx, cy])
    return cs


# ─────────────── Phase 2：约束下放大 ───────────────

def exact_min_gap(items, layout, ds_gap=3):
    sp = SPEC[layout]
    g = G.gaps(items, sp['vw'], sp['vh'], ds=ds_gap, kmax=150)
    return min(g.values()) if g else 999


def measure(items, layout, ds_gap=3, ds_mask=2):
    sp = SPEC[layout]
    vw, vh = sp['vw'], sp['vh']
    gp = G.gaps(items, vw, vh, ds=ds_gap, kmax=174)
    reqs = pair_req_map(layout)
    margin = min((v - reqs[k] for k, v in gp.items()), default=999)
    return dict(
        cov=G.coverage(items, vw, vh, ds_mask),
        gap=(min(gp.values()) if gp else 999),
        margin=margin, pair_gaps=gp, pair_reqs=reqs,
        bleed=G.bleed_edges(items, vw, vh, ds_mask),
        vis=G.visible_fraction(items, vw, vh, ds_mask),
        area=G.ink_area(items, vw, vh, ds_mask),
        inkbox=G.stats(items, vw, vh, ds_mask)['inkbox'],
    )


def feasible(items, layout, vis_min=None, ds_gap=3, ds_mask=2):
    sp = SPEC[layout]
    if vis_min is None:
        vis_min = sp.get('vis_min', VIS_MIN)
    cov_max = sp.get('cov_max', COV_MAX)
    bleed_required = sp.get('w_bleed', 500.0) > 0
    hier_hi = sp.get('hier_hi', HIER_HI)
    m = measure(items, layout, ds_gap, ds_mask)
    if m['gap'] < sp['gmin']:
        return False, m
    if m['cov'] > cov_max:
        return False, m
    if bleed_required:
        for n, e in m['bleed'].items():
            if not e:
                return False, m
    for n, v in m['vis'].items():
        if v < vis_min:
            return False, m
    a = m['area']
    if max(a.values()) / float(max(1, min(a.values()))) > hier_hi:
        return False, m
    return True, m


def scaled(items, layout, lam):
    """统一把尺寸放大 λ 倍，中心不动（λ>1 时四周自然外扩、出血加深）。"""
    out = []
    for it in items:
        w = int(round(it['w'] * lam))
        sw, sh = G.size_of(it['name'])
        h = int(round(w * sh / float(sw)))
        out.append(dict(name=it['name'], w=w, h=h, rot=it['rot'],
                        cx=it['cx'], cy=it['cy'],
                        x=it['cx'] - w / 2.0, y=it['cy'] - h / 2.0))
    for it in out:
        it['bbox'] = G.rot_bbox(it['cx'], it['cy'], it['w'], it['h'], it['rot'])
    return out


def _sync(it, wlo, whi):
    """由 (cx, cy, w, rot) 重算 h / x / y / bbox，并把宽度夹在合理区间内。"""
    w = max(wlo, min(whi, int(it['w'])))
    sw, sh = G.size_of(it['name'])
    it['w'] = w
    it['h'] = int(round(w * sh / float(sw)))
    it['x'] = it['cx'] - w / 2.0
    it['y'] = it['cy'] - it['h'] / 2.0
    it['bbox'] = G.rot_bbox(it['cx'], it['cy'], it['w'], it['h'], it['rot'])
    return it


def refine(items, layout, rounds=14, step0=48, ds_gap=5, quiet=False):
    """真·墨迹间距约束下的坐标下降：同时微调位置与尺寸，把画幅吃满。

    Phase 1 用**旋转包围盒**间距作下界（保守：墨迹 ⊆ 包围盒 ⇒ 真实间距 ≥ 包围盒间距），
    会白扔掉大量可利用的空隙。本阶段直接约束**真实墨迹间距**并以覆盖率为目标，
    物体因此被推到「刚好不粘连」的位置 —— 元素更大、画幅更饱满，而间距仍然守住。

    在 ds_gap=5 下测量（下界安全：测得值 ≤ 真值），终检再用 ds=2 复核。"""
    vw, vh = SPEC[layout]['vw'], SPEC[layout]['vh']
    sp = SPEC[layout]
    gmin = sp['gmin']
    top_pad = sp['top_pad']
    hier_hi = sp.get('hier_hi', HIER_HI)
    zones = sp.get('zones')
    vis_min = sp.get('vis_min', VIS_MIN)
    cov_max = sp.get('cov_max', COV_MAX)
    w_cov = sp.get('w_cov', 1000.0)
    w_bleed = sp.get('w_bleed', 500.0)
    t0 = time.time()

    def ev(state):
        st = G.stats(state, vw, vh, 2)
        gp = G.gaps(state, vw, vh, ds=ds_gap, kmax=160)
        reqs = pair_req_map(layout)
        worst = min((v - reqs[k] for k, v in gp.items()), default=999)
        short = sum(max(0.0, reqs[k] - v) for k, v in gp.items())
        nobleed = sum(1 for v in st['bleed'].values() if not v)
        vshort = sum(max(0.0, vis_min - v) for v in st['vis'].values())
        a = st['area']
        ratio = max(a.values()) / float(max(1, min(a.values())))
        hier = max(0.0, ratio - hier_hi) + max(0.0, HIER_LO - ratio)
        # 分区：中间主体必须在中央，两侧物体必须靠边
        zonepen = 0.0
        if zones:
            for i, (lo, hi) in enumerate(zones):
                fx = state[i]['cx'] / float(vw)
                zonepen += max(0.0, lo - fx) + max(0.0, fx - hi)
        # 网格空置惩罚：光有总覆盖率不够 —— 物体全挤在一侧时总覆盖不低，
        # 但画面照样显得空旷。把画布切 4×3 格，直接惩罚空置格。
        empty = 0.0
        union = st['union']
        for row in np.array_split(union, 4, axis=0):
            for cell in np.array_split(row, 3, axis=1):
                r = float(cell.mean())
                if r < CELL_MIN:
                    empty += (CELL_MIN - r)
        # 上缘安全边：画面上缘是硬边界，模型被它切掉会显得「没展示全」。
        # 下缘由 CSS 渐隐处理，不在此约束。
        topcut = sum(max(0.0, top_pad - bb[1]) for bb in st['inkbox'].values())
        s = (w_cov * st['cov'] - 20.0 * short - w_bleed * nobleed
             - 4000.0 * vshort - 300.0 * hier - 2500.0 * empty
             - 20000.0 * zonepen
             - 70.0 * topcut
             - 3000.0 * max(0.0, st['cov'] - cov_max))
        return s, st['cov'], worst

    state = [dict(it) for it in items]
    bounds = []
    b_lo = sp.get('bound_lo', 0.78)
    b_hi = sp.get('bound_hi', 1.10)
    for it, sp_c in zip(state, SPEC[layout]['cands']):
        lo, hi = min(sp_c[1]), max(sp_c[1])
        bounds.append((int(lo * b_lo), int(hi * b_hi)))
        _sync(it, *bounds[-1])

    best, cov, worst = ev(state)
    step = float(step0)
    for _ in range(rounds):
        improved = False
        for i in range(len(state)):
            base = dict(state[i])
            move = None
            for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step),
                           (step, step), (-step, -step), (step, -step), (-step, step)):
                cand = dict(base)
                cand['cx'] = base['cx'] + dx
                cand['cy'] = base['cy'] + dy
                _sync(cand, *bounds[i])
                state[i] = cand
                s, c, w = ev(state)
                if s > best + 1e-9:
                    best, move, cov, worst = s, cand, c, w
            for f in (1.06, 0.945):
                cand = dict(base)
                cand['w'] = int(round(base['w'] * f))
                _sync(cand, *bounds[i])
                state[i] = cand
                s, c, w = ev(state)
                if s > best + 1e-9:
                    best, move, cov, worst = s, cand, c, w
            state[i] = move or base
            improved = improved or (move is not None)
        if not quiet:
            print('      round  cov %.1f%%  gap %3d  step %.0f  (%.0fs)'
                  % (cov * 100, worst, step, time.time() - t0), flush=True)
        if not improved:
            step /= 2.0
            if step < 9:
                break
    _, cov, worst = ev(state)
    return state, dict(cov=cov, gap=worst, elapsed=time.time() - t0)


def grow(items, layout):
    """备用：统一放大 λ（现已由 refine 取代，保留供快速试算）。"""
    lo, hi = 1.0, 2.0
    ok_lo, m_lo = feasible(items, layout)
    if not ok_lo:
        return items, m_lo
    best_items, best_m = items, m_lo
    for _ in range(7):
        mid = (lo + hi) / 2.0
        cand = scaled(items, layout, mid)
        ok, m = feasible(cand, layout)
        if ok:
            best_items, best_m = cand, m
            lo = mid
        else:
            hi = mid
    return best_items, best_m


def repair(state, layout, bounds_by_name, rounds=22):
    """终检修复：粗测（ds_gap=5）会因降采样抹掉细部而**高估**间距，
    所以必须在 ds=2 下复核。

    做法是**收缩**而不是「推开」：把最紧那一对按比例缩小。
    缩尺寸必然拉开间距，同时不改变中心（分区约束保持），
    也让墨迹上缘往中心退（上缘安全边只会更宽松）。
    之前用「沿连线推开」会和 clamp_top 的分区硬夹互相打架，收敛到粘连解。"""
    vw, vh = SPEC[layout]['vw'], SPEC[layout]['vh']
    gmin = SPEC[layout]['gmin']
    gp = {}
    reqs = pair_req_map(layout)
    for _ in range(rounds):
        gp = G.gaps(state, vw, vh, ds=2, kmax=160)
        if not gp:
            return 999, gp
        pair = max(gp, key=lambda k: reqs[k] - gp[k])
        if gp[pair] >= reqs[pair]:
            return min(gp[k] - reqs[k] for k in gp), gp
        for nm in pair:
            it = next(s for s in state if s['name'] == nm)
            lo, hi = bounds_by_name[nm]
            it['w'] = max(lo, int(round(it['w'] * 0.93)))
            _sync(it, lo, hi)
    gp = G.gaps(state, vw, vh, ds=2, kmax=160)
    return (min(gp[k] - reqs[k] for k in gp) if gp else 999), gp


def clamp_top(state, layout, bounds_by_name, rounds=6):
    """把上缘被画面切掉的物体整体下移，直到墨迹上缘让出安全边。

    画面上缘是硬边界：模型被它切开就成了「没展示全」；
    下缘由 CSS 渐隐化解，所以只约束上缘。"""
    vw, vh = SPEC[layout]['vw'], SPEC[layout]['vh']
    pad = SPEC[layout]['top_pad']
    zones = SPEC[layout].get('zones')
    for _ in range(rounds):
        moved = False
        # 分区硬约束：把中心 x 夹回各自区段（中间主体留中央、两侧物体靠边）
        if zones:
            for i, (lo, hi) in enumerate(zones):
                it = state[i]
                cx = min(max(it['cx'], lo * vw), hi * vw)
                if abs(cx - it['cx']) > 0.5:
                    it['cx'] = cx
                    _sync(it, *bounds_by_name[it['name']])
                    moved = True
        st = G.stats(state, vw, vh, 2)
        for it in state:
            top = st['inkbox'][it['name']][1]
            if top < pad - 1.0:
                it['cy'] += (pad - top) + 1.0
                _sync(it, *bounds_by_name[it['name']])
                moved = True
        if not moved:
            break
    return state


def build_items(sp, sizes, centers):
    items = []
    for i, spec in enumerate(sp['cands']):
        nm, rot = spec[0], spec[2]
        w = sizes[i]
        items.append(dict(name=nm, w=w, h=_h_of(nm, w), rot=rot,
                          cx=centers[i][0], cy=centers[i][1],
                          x=centers[i][0] - w / 2.0, y=centers[i][1] - _h_of(nm, w) / 2.0))
    for it in items:
        it['bbox'] = G.rot_bbox(it['cx'], it['cy'], it['w'], it['h'], it['rot'])
    return items


# ─────────────── 主流程 ───────────────

def tune(layout, restarts=16, rounds=24, seed=7, topk=5):
    sp = SPEC[layout]
    rng = random.Random(seed)
    t0 = time.time()
    pool = []

    for r in range(restarts):
        sizes = [c[1][rng.randrange(len(c[1]))] for c in sp['cands']]
        ev = Evaluator(layout, sizes)
        centers = random_seed(ev, rng)
        centers, sc = climb(ev, centers, rounds=rounds)
        pool.append((sc, sizes, centers))
        if sc >= max(p[0] for p in pool):
            print('  restart %2d/%d  score %8.1f  sizes %s  (%.0fs)'
                  % (r, restarts, sc, sizes, time.time() - t0), flush=True)
    print('  Phase 1 完成 (%.0fs)' % (time.time() - t0), flush=True)

    pool.sort(key=lambda t: -t[0])
    best = None
    seen = set()
    tried = 0
    for sc, sizes, centers in pool:
        key = tuple(sizes)
        if key in seen:
            continue
        seen.add(key)
        tried += 1
        items = build_items(sp, sizes, centers)
        items, _ = refine(items, layout)
        bounds_by_name = {}
        b_lo = sp.get('bound_lo', 0.78)
        b_hi = sp.get('bound_hi', 1.10)
        for it, spec in zip(items, sp['cands']):
            lo, hi = min(spec[1]), max(spec[1])
            bounds_by_name[it['name']] = (int(lo * b_lo), int(hi * b_hi))
        gap, _ = repair(items, layout, bounds_by_name)
        clamp_top(items, layout, bounds_by_name)
        gap, _ = repair(items, layout, bounds_by_name)
        clamp_top(items, layout, bounds_by_name)
        # 收缩修复会掉覆盖率，再做一轮小步精修在约束内回补
        items, _ = refine(items, layout, rounds=6, step0=16, quiet=True)
        gap, _ = repair(items, layout, bounds_by_name)
        clamp_top(items, layout, bounds_by_name)
        m = measure(items, layout, ds_gap=2, ds_mask=1)
        tops = min(bb[1] for bb in m['inkbox'].values())
        print('  精修 #%d  sizes %s  cov %.1f%%  gap %d  上缘 %d'
              % (tried, sizes, m['cov'] * 100, m['gap'], tops), flush=True)
        if best is None:
            best = (items, m)
        else:
            # 排序键：先「间距达标」，再「模型完整呈现」，再「上缘未被切」，最后比覆盖率
            def key(mm):
                top = min(bb[1] for bb in mm['inkbox'].values())
                vmin = min(mm['vis'].values()) if mm.get('vis') else 1.0
                vis_ok = vmin >= sp.get('vis_min', VIS_MIN) - 0.02
                return (mm.get('margin', 999) >= 0, vis_ok,
                        top >= sp['top_pad'] - 4, mm['cov'])
            if key(m) > key(best[1]):
                best = (items, m)
        if tried >= topk:
            break
    return best


def main():
    layouts = {}
    for layout in ('wide', 'tall'):
        print('\n===== %s  %dx%d =====' % (layout, SPEC[layout]['vw'], SPEC[layout]['vh']),
              flush=True)
        items, m = tune(layout)
        plan = [[it['name'], int(round(it['x'])), int(round(it['y'])), it['w'], it['rot']]
                for it in items]
        layouts[layout] = dict(vw=SPEC[layout]['vw'], vh=SPEC[layout]['vh'], plan=plan)
        print('  → 覆盖率 %.1f%%   最小墨迹间距 %d px   逐对余量 %+d px'
              % (m['cov'] * 100, m['gap'], m['margin']))
        for k in sorted(m['pair_gaps']):
            v, r = m['pair_gaps'][k], m['pair_reqs'][k]
            print('     %-16s ↔ %-16s %4d px  要求 %3d  %s'
                  % (k[0].replace('ghost-', '').replace('.png', ''),
                     k[1].replace('ghost-', '').replace('.png', ''), v, r,
                     'OK' if v >= r else '!!'))
        for k, v in m['bleed'].items():
            print('     %-24s 出血 %s   可见 %.0f%%   墨迹 %d px²'
                  % (k.replace('ghost-', '').replace('.png', ''), '、'.join(v) or '—',
                     m['vis'][k] * 100, m['area'][k]))
        for row in plan:
            print('     %-24s x=%6d y=%6d w=%4d rot=%+d' % tuple(row))

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(dict(layouts=layouts), f, ensure_ascii=False, indent=2)
    print('\n-> 写入', OUT_JSON)


if __name__ == '__main__':
    main()
