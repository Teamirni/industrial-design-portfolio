# -*- coding: utf-8 -*-
"""
封面几何量测：从 index.html 派生 _measure.html，叠加容器框 / SVG 内容框 / 排版块框，
用本地 Edge 截图，直接读出「构图板容器比例」与「SVG 内容占容器的比例」。

输出里的「建议画布」即 `_tune_cover.py` 的 SPEC[vw][vh] 应取的尺寸：
画布比例 == 容器比例时，`preserveAspectRatio="meet"` 才能把画幅吃满、不留白带。
"""
import subprocess
from pathlib import Path

BASE = Path(r'E:/WorkBuddy工作路径/工业设计作品集/portfolio-v2').resolve()
SRC = BASE / 'index.html'
DST = BASE / '_measure.html'
OUT = BASE / '_shots'
OUT.mkdir(exist_ok=True)

EDGE_CANDIDATES = [
    Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
    Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
]
HOST, PORT = '127.0.0.1', 8163

VIEWPORTS = [('desktop-1440x900', 1440, 900), ('laptop-1280x800', 1280, 800),
             ('phone-390x844', 390, 844)]

SCRIPT = r"""
<script>
(function(){
  var svgs = document.querySelectorAll('.cover-svg');
  function vis(){
    for (var i=0;i<svgs.length;i++){
      var s = svgs[i];
      if (s.getClientRects().length && s.getBoundingClientRect().width > 0) return s;
    }
    return svgs[0] || null;
  }
  function R(el){ var b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; }
  function box(rc, color, label){
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;z-index:2147482990;border:2px solid '+color+';pointer-events:none;box-sizing:border-box;left:'+rc[0]+'px;top:'+rc[1]+'px;width:'+rc[2]+'px;height:'+rc[3]+'px';
    document.body.appendChild(d);
    var l = document.createElement('div');
    l.style.cssText = 'position:fixed;z-index:2147483000;left:'+rc[0]+'px;top:'+Math.max(0,rc[1]-17)+'px;font:11px/17px monospace;color:#fff;background:'+color+';padding:0 4px';
    l.textContent = label; document.body.appendChild(l);
  }
  function run(){
    var cov = document.querySelector('.cover');
    var art = document.querySelector('.cover-art');
    var typ = document.querySelector('.cover-type');
    var svg = vis();
    if (!cov || !art || !typ || !svg) return;
    var vb = svg.getAttribute('viewBox').split(/[\s,]+/);
    var vw = parseFloat(vb[2]), vh = parseFloat(vb[3]);
    var c = R(cov), a = R(art), s = R(svg), t = R(typ);
    var sc = Math.min(s[2]/vw, s[3]/vh);
    var cw = vw*sc, ch = vh*sc;
    var cl = s[0]+(s[2]-cw)/2, ct = s[1]+(s[3]-ch)/2;
    box(c, '#ff8800', 'cover');
    box(a, '#0066ff', 'cover-art');
    box([cl,ct,cw,ch], '#00aa00', 'svg content');
    box(t, '#ff00aa', 'cover-type');
    var gl = cl-s[0], gr = (s[0]+s[2])-(cl+cw);
    var gt = ct-s[1], gb = (s[1]+s[3])-(ct+ch);
    var ratio = s[2]/s[3];
    var fitW = s[2]/vh, fitH = s[3]/vw;   // 让画布比例 = 容器比例时，取哪种换算
    var rec = (ratio >= 1) ? Math.round(1620) + ' x ' + Math.round(1620/ratio)
                           : Math.round(ratio*1480) + ' x ' + 1480;
    var info = document.createElement('div');
    info.style.cssText = 'position:fixed;right:6px;bottom:6px;z-index:2147483001;font:12px/1.6 monospace;background:#000;color:#0f0;padding:8px 10px;white-space:pre';
    info.textContent =
      'viewport      ' + innerWidth + 'x' + innerHeight + '\n' +
      'cover         ' + c.join(', ') + '\n' +
      'cover-art     ' + a.join(', ') + '\n' +
      'svg elem      ' + s.join(', ') + '   ratio ' + ratio.toFixed(3) + '\n' +
      'svg class     ' + svg.getAttribute('class') + '\n' +
      'viewBox       ' + Math.round(vw) + 'x' + Math.round(vh) + '  (ratio ' + (vw/vh).toFixed(3) + ')\n' +
      'svg content   ' + Math.round(cw) + 'x' + Math.round(ch) + '  (scale ' + sc.toFixed(3) + ')\n' +
      'gutters L/R   ' + gl.toFixed(0) + ' / ' + gr.toFixed(0) + ' px\n' +
      'gutters T/B   ' + gt.toFixed(0) + ' / ' + gb.toFixed(0) + ' px\n' +
      'content/elem  ' + (cw/s[2]*100).toFixed(1) + '% 宽  ' + (ch/s[3]*100).toFixed(1) + '% 高\n' +
      'art / cover   ' + (a[3]/c[3]*100).toFixed(1) + '%\n' +
      '建议画布      ' + rec;
    document.body.appendChild(info);
  }
  if (document.readyState === 'complete') setTimeout(run, 400);
  else window.addEventListener('load', function(){ setTimeout(run, 400); });
})();
</script>
"""


def main():
    html = SRC.read_text(encoding='utf-8')
    DST.write_text(html.replace('</body>', SCRIPT + '</body>'), encoding='utf-8')
    print('-> 写入', DST)

    edge = next((p for p in EDGE_CANDIDATES if p.exists()), None)
    if edge is None:
        raise FileNotFoundError('未找到 Edge')

    import http.server, socketserver, threading, time, urllib.request, os
    os.chdir(BASE)
    httpd = socketserver.TCPServer((HOST, PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    for _ in range(60):
        try:
            urllib.request.urlopen('http://%s:%d/' % (HOST, PORT), timeout=1); break
        except Exception:
            time.sleep(0.2)

    for name, w, h in VIEWPORTS:
        out = OUT / ('measure-%s.png' % name)
        subprocess.run([str(edge), '--headless', '--no-sandbox', '--disable-gpu',
                        '--hide-scrollbars', '--force-device-scale-factor=1',
                        '--virtual-time-budget=6000',
                        '--window-size=%d,%d' % (w, h),
                        '--screenshot=%s' % out,
                        'http://%s:%d/_measure.html' % (HOST, PORT)],
                       capture_output=True, timeout=120)
        print('%s  %s' % ('✓' if out.exists() else '✗', out.name))
    httpd.shutdown()


if __name__ == '__main__':
    main()
