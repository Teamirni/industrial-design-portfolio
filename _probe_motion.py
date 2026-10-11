# -*- coding: utf-8 -*-
"""
动效时序测量
============
驱动 _probe_motion.html（同源 iframe + 逐帧采样），用 Edge --dump-dom 读回
JSON 时序数据并出报告。零依赖，不需要 CDP 客户端。

它回答的是截图回答不了的问题：
  · 过渡实际时长是多少？是否与设计的 320/560ms 一致？
  · 缓动曲线是否真的按 cubic-bezier 生效，还是退化成了 linear？
  · 网格内错峰是否按 DOM 顺序、间隔是否接近设计 step？
  · 数字滚动是否单调收敛、末值是否精确回到原文？
  · 磁性按钮是否跟手、松手后是否收敛回 0？
  · 帧间隔中位数 vs p95 是否正常（有无长帧）？
  · prefers-reduced-motion 下是否首帧即完全可见？

用法：python _probe_motion.py [页面 ...]
"""
import html as html_mod
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent.resolve()

EDGE_CANDIDATES = [
    Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
    Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
]

HOST, PORT = '127.0.0.1', 8195
TIMEOUT = 300
# 探针自身最长耗时 = 载入 700 + rAF判定 500 + A封面 ~1600
#   + B揭示 6组×1970 + C错峰 2100 + D数字 2300 + E磁性 1700 + F探测
# 取最坏情形约 20s，预算给到 60s。
VTB = 60000

PAGES = ['index.html', 'about.html', 'methodology.html',
         'projects/dslr.html', 'projects/cat-nest.html']


# ───────── cubic-bezier 参考实现：用于验证「实测缓动」是否等于「声明缓动」 ─────────
def bezier_y_at_x(x, x1, y1, x2, y2):
    """给定三次贝塞尔控制点，求 x 处对应的 y。牛顿迭代 + 二分兜底。"""
    def cx(t):
        return 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3

    def cy(t):
        return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cx(mid) < x:
            lo = mid
        else:
            hi = mid
    return cy((lo + hi) / 2)


EASE_OUT = (0.22, 1, 0.36, 1)      # css/motion.css 的 --m-ease-out
EASE_SOFT = (0, 0.71, 0.2, 1.01)   # --m-ease-soft


def find_edge():
    for p in EDGE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError('未找到 Edge')


def serve():
    handler = lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(BASE), **k)
    httpd = ThreadingHTTPServer((HOST, PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1)
            return httpd
        except Exception:
            time.sleep(0.2)
    raise RuntimeError('本地服务启动失败')


def run_probe(edge, page, reduced=False):
    profile = tempfile.mkdtemp(prefix='edge-probe-')
    url = 'http://%s:%d/_probe_motion.html?p=%s' % (HOST, PORT, urllib.parse.quote(page))
    cmd = [
        str(edge), '--headless', '--no-sandbox', '--disable-gpu',
        '--hide-scrollbars', '--force-device-scale-factor=1',
        '--user-data-dir=%s' % profile,
        '--virtual-time-budget=%d' % VTB,
        '--window-size=1440,900',
    ]
    if reduced:
        cmd.append('--force-prefers-reduced-motion')
    cmd += ['--dump-dom', url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        shutil.rmtree(profile, ignore_errors=True)
        return None
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    dom = r.stdout.decode('utf-8', 'replace')
    # 取最后一处匹配：页面里若在注释中出现同名标签字面量，先匹配到的会是注释
    hits = re.findall(r'<pre id="probe">(.*?)</pre>', dom, re.S)
    if not hits:
        return None
    raw = html_mod.unescape(hits[-1]).strip()
    if raw.startswith('PENDING') or raw.startswith('IFRAME ACCESS FAILED'):
        print('   探针未完成：', raw[:120])
        return None
    try:
        return json.loads(raw)
    except Exception as e:
        print('   JSON 解析失败：', e, raw[:200])
        return None


def report_motion(data, page):
    print('\n══════ %s ══════' % page)
    print('  data-motion=%s  docH=%s  innerH=%s' % (
        data.get('dataMotion'), data.get('docH'), data.get('innerH')))

    # ── 环境体检：把「功能坏了」与「本环境测不了」分开 ──
    env = data.get('env') or {}
    rlive = data.get('rAFLive')
    if rlive is None:
        rlive_txt = '未判定'
    else:
        rlive_txt = '存活' if rlive else '★停摆（凡挂在 rAF 上的测量项都不可信）'
    print('  环境：rAF=%s  pointer:fine=%s  hover:none=%s  站点判定触摸设备=%s' % (
        rlive_txt, env.get('pointerFine'), env.get('hoverNone'), env.get('siteIsTouch')))
    se = data.get('scrollEvents')
    if se is not None:
        if se == 0:
            print('  scroll 事件：本环境投递 0 次 ★ 程序化 scrollTo 不派发 scroll 事件'
                  ' → 探针已代投合成事件（管线/CSS 仍为站点真实代码）')
        else:
            print('  scroll 事件：投递 %d 次（真实事件已驱动管线，未代投）' % se)

    errs = data.get('errors') or []
    if errs:
        print('  ★ 子框架运行时异常 %d 条：' % len(errs))
        for e in errs[:5]:
            print('       %s' % e)
    else:
        print('  子框架运行时异常：无')

    me = data.get('motionErrors')
    if me is None:
        pass
    elif me == 0:
        print('  站点任务级异常计数 __motionErrors=0（滚动管线上无任务抛错）')
    else:
        print('  ★ __motionErrors=%s：滚动管线有任务抛错（已被隔离，揭示不受影响，'
              '但需查因）' % me)

    # ── 证据分层说明：避免把「测不了」读成「坏了」 ──
    if rlive is False:
        print('  证据分层：本环境 rAF 停摆、渲染时钟在密集采样期间不推进，')
        print('           「采样层」只用来判定揭示是否发生；')
        print('           时长 / 缓动 / 错峰等结论一律以「声明回读」为准'
              '（渲染引擎的真实取值，不受时钟影响）。')

    for n in data.get('notes', []):
        print('  · %s' % n)

    # ── 封面逐字揭示（CSS 关键帧，设计值：stagger 42ms、起点 translateY .72em）──
    L = data.get('letters')
    if L and L.get('count'):
        print('  ── 封面逐字揭示（设计：错峰 42ms，起点 translateY=.72em，opacity 0→1）──')
        print('     单词「%s」字母 %s 个' % (L.get('wordsDetected'), L['count']))

        # 声明层（权威）：从渲染引擎读回的 animation-delay / duration / timing
        dd = L.get('declaredDelaysMs')
        gap_d = L.get('declaredGapsMs') or []
        if dd:
            print('     声明 animation-delay(ms) %s' % dd)
        if gap_d:
            avgd = sum(gap_d) / len(gap_d)
            print('     声明错峰间隔 %s → 均值 %.0fms（设计 42ms）%s' % (
                gap_d, avgd, 'OK' if 35 <= avgd <= 50 else ' ← 与设计值偏离'))
        specs = L.get('specs') or []
        if specs:
            s0 = specs[0]
            print('     首字母 animation：name=%s  duration=%s  timing=%s  delay=%s' % (
                s0.get('name'), s0.get('dur'), s0.get('tf'), s0.get('delay')))

        # 采样层（参考）：动画时钟在无头虚拟时间下会被冻住
        late = (L.get('opacityStart') or 0) > 0.02
        if L.get('animationClockUsable') is False:
            print('     ※ 采样层无意义：动画时钟在本环境被冻住（opacity / translateY 全程恒定）')
            print('       错峰结论以声明 animation-delay 为准')
        elif late:
            print('     ※ 采样层仅作量级参考：封面动画在页面加载即起跑'
                  '（delay 140ms + 时长 900ms），')
            print('       而探针在载入后才开始采样，起点已错过 → 给不出错峰结论；')
            print('       错峰结论以声明 animation-delay 为准')
        print('     采样首动时刻(ms) %s' % ', '.join(
            '—' if v is None else str(v) for v in L.get('firstVisibleTimes', [])))
        if L.get('gaps') and not late and L.get('animationClockUsable') is not False:
            avg = sum(L['gaps']) / len(L['gaps'])
            print('     采样错峰间隔 %s → 均值 %.0fms（设计 42ms）%s' % (
                ', '.join(str(g) for g in L['gaps']), avg,
                'OK' if 25 <= avg <= 60 else ' ← 与设计值偏离'))
        print('     translateY 起点 %s → 终点 %s ；opacity %s → %s（采样 %s 帧）' % (
            L.get('translateYStart'), L.get('translateYEnd'),
            L.get('opacityStart'), L.get('opacityEnd'), L.get('samples')))
    elif L:
        print('  ── 封面逐字揭示：本页无封面 ──')

    # ── 揭示过渡：时长 / 缓动形状 ──
    print('  ── 揭示过渡（设计：延迟 0→504ms 错峰、时长 560ms、ease-out cubic-bezier(.22,1,.36,1)）──')
    print('     %-14s %-6s %-9s %-9s %-12s %s' % (
        '元素', '首动ms', '时长ms', '终值', '扫描序列', '25/50/75% 实测 → 声明缓动'))

    def pick(d, *ks):
        for k in ks:
            if not isinstance(d, dict):
                return None
            d = d.get(k)
        return d

    diag_by_sel = {}
    for dg in data.get('diag', []):
        diag_by_sel[dg.get('sel')] = dg

    for tr in data.get('reveal', []):
        sel = tr.get('sel')
        dur = tr.get('duration')
        dg0 = diag_by_sel.get(sel) or {}
        si0 = dg0.get('sweepIndex')
        # 下标 -1 = 该元素被 initReveal 主动排除（位于 .cover/.project-hero/.about-hero 内），
        # 入场由 css/motion.css 的关键帧负责，因此它的 base 态不带 transition 属正常。
        if si0 is None:
            si_txt = '—'
        elif si0 < 0:
            si_txt = '-1(hero帧)'
        else:
            si_txt = '%s/%s' % (si0, dg0.get('sweepTotal'))

        line = '     %-14s %-6s %-9s %-9s %-12s' % (
            sel, tr.get('tStart'), dur if dur is not None else '未生效',
            tr.get('valueEnd'), si_txt)
        curve = tr.get('curve')
        if curve:
            meas = [c['value'] for c in curve]
            cands = [('ease-out', EASE_OUT), ('ease-soft', EASE_SOFT)]
            scored = []
            for name, pts in cands:
                theo = [bezier_y_at_x(c['at'], *pts) for c in curve]
                scored.append((max(abs(a - b) for a, b in zip(meas, theo)), name))
            scored.sort()
            best_dev, best_name = scored[0]
            line += ' %s | 最接近 %s（偏差 %.3f）%s' % (
                '/'.join('%.2f' % v for v in meas), best_name, best_dev,
                '' if best_dev < 0.15 else '  ← 偏差偏大')
        if si0 is not None and si0 < 0:
            line += ('（终值 %.2f 已可见；不参与扫描揭示，由 hero 关键帧负责，'
                     '故 base 态无 transition 属预期）' % (tr.get('valueEnd') or 0))
        print(line)

        # ── 失败归因：终值未到 1 时，先判断是「测量受限」还是「实现缺陷」 ──
        ve = tr.get('valueEnd')
        if ve is not None and ve < 0.999:
            dg = diag_by_sel.get(sel)
            if dg is None:
                print('        ⚠ 终值 %.3f 未到 1，且无诊断数据' % ve)
            elif dg.get('sweepIndex') is not None and dg.get('sweepIndex') < 0:
                print('        ⚠ 归因：该元素不在扫描序列内（sweepIndex=-1 / 序列长 %s）'
                      '→ CSS 藏起但 JS 不负责揭示，属实现缺陷' % dg.get('sweepTotal'))
            elif (dg.get('isinAfter') or 0) > 0 and not dg.get('opacityChanged'):
                print('        ※ 采样受限（非实现缺陷）：元素已揭示、.is-in 已加上、'
                      '过渡声明已生效，')
                print('          但本环境的渲染时钟在密集采样期间不推进（rAF 停摆），'
                      '过渡曲线采不到。')
                print('          结论以「声明回读」为准：见下表运行时 transition 规格。')
            else:
                print('        ⚠ 归因：sweepIndex=%s/%s；滚动 %s→%s；'
                      '推过后 revealed=%s isIn=%s；采样末尾 revealed=%s isIn=%s；isin总数=%s；帧 %s' % (
                          dg.get('sweepIndex'), dg.get('sweepTotal'),
                          pick(dg, 'snapPark', 'scrollY'), pick(dg, 'snapPush', 'scrollY'),
                          pick(dg, 'snapPush', 'target', 'revealed'),
                          pick(dg, 'snapPush', 'target', 'isIn'),
                          pick(dg, 'afterSample', 'revealed'),
                          pick(dg, 'afterSample', 'isIn'),
                          dg.get('isinAfter'), dg.get('frames')))

        ic = tr.get('imgClip')
        if ic and ic.get('duration') is not None:
            print('        └ 图片 clip 揭示：%sms 内从 %.0f%% 收缩到 %.0f%%' % (
                ic['duration'], ic.get('valueStart') or 0, ic.get('valueEnd') or 0))

    # ── 声明回读 ──
    dec = data.get('declared') or []
    if dec:
        print('  ── 渲染引擎中实际生效的过渡声明（computedStyle 回读，最硬的一手证据）──')
        for dd in dec:
            print('     %-14s %-34s %-10s %-30s delay=%s' % (
                dd['label'], dd['property'], dd['duration'], dd['timing'], dd['delay']))

    # ── 错峰顺序 ──
    st = data.get('stagger')
    if st:
        print('  ── 网格错峰 ── 容器=%s 子项=%s' % (st['container'], st['count']))

        # 声明层（权威）：各卡运行时 transition-delay
        dd = st.get('declaredDelays') or []
        if dd:
            print('     声明 transition-delay：')
            for i, d in enumerate(dd):
                print('       [%d] %-34s %s' % (i, d.get('cls'), d.get('delay')))
        cis = st.get('childInSweep')
        if cis:
            bad = [(i, v) for i, v in enumerate(cis) if v is None or v < 0]
            print('     子项是否在扫描序列内 %s%s' % (
                cis, '' if not bad else '  ← 下标 %s 不在序列内！' % [i for i, _ in bad]))

        # 采样层（参考）
        print('     采样（间隔 %sms，pushPast 注入 t=%sms）首动时刻 %s' % (
            st.get('sampleIntervalMs'), st.get('pushAtMs'),
            ', '.join('—' if v is None else str(v) for v in st['firstChangeTimes'])))
        if st.get('gaps'):
            avg = sum(st['gaps']) / len(st['gaps'])
            print('     间隔 %s → 均值 %.0fms；顺序%s（设计 step 72ms，窗口 25~120ms）' % (
                ', '.join(str(g) for g in st['gaps']), avg,
                '正确' if st.get('ascending') else '存在逆序 ←'))
        elif all(v is None for v in st['firstChangeTimes']):
            print('     ※ 全部未采到变化：渲染时钟在密集采样期间不推进'
                  ' → 错峰结论以声明 transition-delay 为准')

    # ── 数字滚动 ──
    ct = data.get('counters')
    if ct:
        ck = data.get('counterClock') or {}
        print('  ── 数字滚动 ──（pushPast 注入于采样 t=%sms）' % ck.get('pushAtMs'))
        for c in ct:
            print('     %-8s → 首帧 %-8s 中间 %-8s 末值 %-8s 变化帧数 %-4s 首变t=%-6s %s' % (
                c['original'], c['first'], c['mid'], c['final'], c['distinctCount'],
                c.get('tFirstChange'),
                'OK' if c['returnsToOriginal'] else '末值未回到原文 ←'))

    # ── 磁性按钮 ──
    mg = data.get('magnetic')
    if mg:
        if mg.get('measurable') is False:
            print('  ── 磁性按钮 ── 本次无法测量：%s（非实现缺陷）' % mg.get('invalidReason'))
        else:
            print('  ── 磁性按钮 ── 峰值 %s（应非 0）→ 松手后 %s → %s' % (
                mg['duringPeak'], mg['afterLast'],
                '收敛回 0' if mg['settledToZero'] else '未收敛回 0 ←'))

    # ── 图片 clip 揭示的「半消失」风险 ──
    ca = data.get('clipArmed')
    cr = data.get('clipRevealed')
    if ca is not None:
        if ca == 0:
            print('  clip 揭示：本页无 img.m-clip（无图片或未布防）')
        elif cr is not None and cr < ca:
            print('  ★ clip 揭示：布防 %s 张，已揭示 %s 张 → 有 %s 张仍被裁在中间'
                  '（若持续不揭示＝半消失）' % (ca, cr, ca - cr))
        else:
            print('  clip 揭示：布防 %s 张，已揭示 %s 张 → 全部展开' % (ca, cr))

    # ── 页面切换 ──
    tr2 = data.get('transition')
    if tr2:
        print('  ── 页面切换 ── @view-transition 规则存在=%s  内核支持=%s → 路径：%s' % (
            tr2.get('viewTransitionAtRulePresent'),
            tr2.get('crossDocumentViewTransitionSupported'),
            tr2.get('path')))


def report_static(data, page):
    print('\n══════ %s（静态回退态 / prefers-reduced-motion）══════' % page)
    print('  data-motion=%s  .is-in 数量=%s  进度条元素=%s  字带节点=%s → %s' % (
        data.get('dataMotion'), data.get('isinCount'),
        data.get('scrollProgressBarCount'), data.get('tickerClones'),
        '静态开关生效' if data.get('dataMotion') == 'off' else '!! 未切换到 off'))
    cl = data.get('coverLetters') or {}
    if cl.get('count'):
        print('  封面字母 %s 个，首字母 opacity=%s（应为 1）' % (
            cl['count'], cl.get('firstOpacity')))
    imgs = data.get('images') or {}
    print('  clip 揭示图片：共 %s 张，带 .m-clip 的 %s 张，样例 clipPath=%s' % (
        imgs.get('totalFigureImgs'), imgs.get('withClipClass'), imgs.get('sampleClipPath')))
    bad = []
    for t in data.get('targets', []):
        flag = '' if t['minOpacity'] >= 0.999 else '  ← 不可见！'
        if flag:
            bad.append(t['sel'])
        print('     %-20s ×%-3s 最小 opacity=%s%s' % (
            t['sel'], t['count'], t['minOpacity'], flag))
    print('  结论：', '全部目标首帧即可见 —— 静态 / 打印回退成立'
          if not bad else '异常不可见：%s' % ', '.join(bad))


def main():
    edge = find_edge()
    pages = sys.argv[1:] or PAGES
    httpd = serve()
    try:
        for page in pages:
            data = run_probe(edge, page, reduced=False)
            if data:
                report_motion(data, page)
            else:
                print('\n══ %s ══ 探针未返回结果' % page)

            data_s = run_probe(edge, page, reduced=True)
            if data_s:
                report_static(data_s, page)
    finally:
        httpd.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
