# -*- coding: utf-8 -*-
"""
竖版间距要求 A/B 对比
=====================
把「横版的间距要求」映射到竖版，有两种口径，差别很大，故一次跑两份：

  A-等比  按画布宽度等比换算  k = 915/1620 = 0.5648
            gmin 62 -> 35    truck↔dslr 104 -> 59
            含义：间距「占画布宽的比例」与横版一致。

  B-照搬  直接沿用横版绝对像素值
            gmin 62          truck↔dslr 104
            含义：间距「在屏幕上的物理宽度」与横版一致（竖版画布窄，观感会更宽松）。

两份结果分别写 `_ab_tall_<tag>.json`（含原 wide，便于直接切换渲染），
不覆盖 `_cover_layout.json`，由调用方决定最终采用哪一份。
"""
import json
import os

import _tune_cover as T

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '_cover_layout.json')

WIDE_VW, WIDE_GMIN, WIDE_PAIR = 1620, 62, 104
TALL_VW = 915
K = TALL_VW / float(WIDE_VW)

# 斜向相邻、模糊后视觉间隙会缩水的对（横版里只有 truck↔dslr 是斜向，
# 竖版里越野车同时斜向贴着单反与耳机，故两对都要独立要求）
PAIR_KEYS = [
    ('ghost-dslr-01.png', 'ghost-truck-01.png'),
    ('ghost-headphones-01.png', 'ghost-truck-01.png'),
]

VARIANTS = [
    ('A-等比', dict(gmin=int(round(WIDE_GMIN * K)), pair=int(round(WIDE_PAIR * K)))),
    ('B-照搬', dict(gmin=WIDE_GMIN, pair=WIDE_PAIR)),
]


def main():
    with open(SRC, encoding='utf-8') as f:
        base = json.load(f)

    for tag, cfg in VARIANTS:
        sp = T.SPEC['tall']
        sp['gmin'] = cfg['gmin']
        sp['pair_min'] = {k: cfg['pair'] for k in PAIR_KEYS}

        print('\n===== %s   gmin=%d  pair=%d =====' % (tag, cfg['gmin'], cfg['pair']),
              flush=True)
        items, m = T.tune('tall')
        plan = [[it['name'], int(round(it['x'])), int(round(it['y'])), it['w'], it['rot']]
                for it in items]

        base['layouts']['tall'] = dict(vw=TALL_VW, vh=1480, plan=plan)
        out = os.path.join(BASE, '_ab_tall_%s.json' % tag)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)

        print('  → 覆盖率 %.1f%%   最小间距 %d px   逐对余量 %+d px'
              % (m['cov'] * 100, m['gap'], m['margin']), flush=True)
        for k in sorted(m['pair_gaps']):
            v, r = m['pair_gaps'][k], m['pair_reqs'][k]
            print('     %-16s ↔ %-16s %4d px  要求 %3d  %s'
                  % (k[0].replace('ghost-', '').replace('.png', ''),
                     k[1].replace('ghost-', '').replace('.png', ''), v, r,
                     'OK' if v >= r else '!!'), flush=True)
        print('     -> %s' % os.path.basename(out), flush=True)


if __name__ == '__main__':
    main()
