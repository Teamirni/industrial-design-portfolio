# -*- coding: utf-8 -*-
"""
只重排竖版，横版原样保留
========================
用户要求「横屏版本不用修改」，故不能跑 `_tune_cover.main()`（它会连带重排 wide）。
本脚本读入现有 `_cover_layout.json`，只对 tall 重新寻优，写回时 wide 逐字节不动。

产出 `_cover_layout.json`（tall 已更新）+ 指标打印。
"""
import json
import os
import shutil

import _tune_cover as T

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(BASE, '_cover_layout.json')
BAK = os.path.join(BASE, '_cover_layout_bak_before_tall_retune.json')


def main():
    shutil.copy(OUT_JSON, BAK)
    with open(OUT_JSON, encoding='utf-8') as f:
        data = json.load(f)

    wide_before = json.dumps(data['layouts']['wide'], sort_keys=True)

    sp = T.SPEC['tall']
    print('===== tall  %dx%d =====' % (sp['vw'], sp['vh']))
    print('  gmin=%d  vis_min=%.2f  出血权重=%.0f  cov 上限=%.2f  尺寸界=(%.2f, %.2f)'
          % (sp['gmin'], sp.get('vis_min', T.VIS_MIN), sp.get('w_bleed', 500.0),
             sp.get('cov_max', T.COV_MAX), sp.get('bound_lo', 0.78),
             sp.get('bound_hi', 1.10)), flush=True)

    items, m = T.tune('tall')
    plan = [[it['name'], int(round(it['x'])), int(round(it['y'])), it['w'], it['rot']]
            for it in items]
    data['layouts']['tall'] = dict(vw=sp['vw'], vh=sp['vh'], plan=plan)

    print('\n  → 覆盖率 %.1f%%   最小间距 %d px   逐对余量 %+d px'
          % (m['cov'] * 100, m['gap'], m['margin']))
    for k in sorted(m['pair_gaps']):
        v, r = m['pair_gaps'][k], m['pair_reqs'][k]
        print('     %-16s ↔ %-16s %4d px  要求 %3d  %s'
              % (k[0].replace('ghost-', '').replace('.png', ''),
                 k[1].replace('ghost-', '').replace('.png', ''), v, r,
                 'OK' if v >= r else '!!'))
    print('  出血 / 可见：')
    for k, v in m['bleed'].items():
        print('     %-24s 出血 %-6s 可见 %5.1f%%'
              % (k.replace('ghost-', '').replace('.png', ''),
                 '、'.join(v) or '—', m['vis'][k] * 100))
    print('  尺寸：')
    for row in plan:
        print('     %-24s x=%6d y=%6d w=%4d rot=%+d' % tuple(row))

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    wide_after = json.dumps(data['layouts']['wide'], sort_keys=True)
    print('\n  横版是否被改动：%s' % ('是 ✗' if wide_before != wide_after else '否 ✓'))
    print('-> 写入 %s（备份 %s）' % (OUT_JSON, os.path.basename(BAK)))


if __name__ == '__main__':
    main()
