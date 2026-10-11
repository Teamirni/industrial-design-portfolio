# -*- coding: utf-8 -*-
"""
竖版 A/B 渲染
==============
把 `_tall_ab.py` 产出的两份布局轮流装进 `_cover_layout.json`，
重新生成 SVG 并截图，产出可审核的手机端预览图 + 指标。

输出：`_shots/竖版-<tag>-390x844.png` / `_shots/竖版-<tag>-360x780.png`
"""
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LAYOUT = os.path.join(BASE, '_cover_layout.json')
SHOTS = os.path.join(BASE, '_shots')

TAGS = ['A-等比', 'B-照搬']
KEYS = ('tall', '间距', '覆盖', '可见', '出血', '!!', '✗')


def run(args):
    return subprocess.run(args, cwd=BASE, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def main():
    for tag in TAGS:
        print('\n########## %s ##########' % tag, flush=True)
        shutil.copy(os.path.join(BASE, '_ab_tall_%s.json' % tag), LAYOUT)

        r = run([PY, '_check_composition.py'])
        hit = False
        for line in r.stdout.splitlines():
            if any(k in line for k in KEYS):
                print('  ' + line.strip(), flush=True)
                hit = True
        if not hit:
            print('  (校验器无输出，回显)\n' + (r.stdout or r.stderr)[-600:], flush=True)

        run([PY, '_gen_cover_svg.py'])
        run([PY, '_shot.py', 'index.html'])

        for vp in ('390x844', '360x780'):
            src = os.path.join(SHOTS, 'index-phone-%s.png' % vp)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(SHOTS, '竖版-%s-%s.png' % (tag, vp)))
        print('  预览 -> _shots/竖版-%s-390x844.png' % tag, flush=True)


if __name__ == '__main__':
    main()
