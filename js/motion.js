/*
  翁彥斌 · 工业设计作品集 v2 · 动效引擎
  ══════════════════════════════════════════════════════════════
  零依赖、无构建步骤（站点为静态 HTML，用 file:// 或 http.server 直接打开）。
  Motion.dev 在这里的角色是「实现规范」而非运行时依赖：本项目不引入 npm 包，
  但把它文档里的参数与范式逐条对齐，用 CSS 过渡/关键帧 + 自写弹簧积分器 +
  单一 requestAnimationFrame 循环 + View Transitions 原生复刻。
  （滚动揭示不用 IntersectionObserver，理由见第 6 节注释。）

  与 css/motion.css 的分工：
  · 初始隐藏态全部写在 CSS（class 选择器）里 —— 因此不存在
    「JS 跑完才隐藏 → 用户先看到内容再闪一下」的 FOUC。
  · 本文件只负责「何时」把 .is-in 加上去，以及读取滚动位置做 scrub。

  三条安全边界：
  1. 打印导出（build_pdf_v2.py 走 Edge 打印）→ 直接不开动效，页面纯静态。
  2. prefers-reduced-motion → 由 head 内联脚本置 data-motion="off"，本文件直接退出。
  3. 任何环节抛错或脚本未加载 → head 内联脚本的 2.5s 兜底计时器会把
     data-motion 置回 "off"，内容立即可见，绝不出现「永久空白页」。
  ══════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  var html = document.documentElement;

  function all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function mediaPrint() {
    try { return window.matchMedia('print').matches; } catch (e) { return false; }
  }

  /* ─────────── 0. 准入判定 ─────────── */
  function bail() {
    html.setAttribute('data-motion', 'off');
    window.__motionReady = true;
  }

  window.__motionReady = true;          // 先声明就绪，兜底计时器不会误触发

  if (html.getAttribute('data-motion') !== 'on') return;

  /* 打印导出：彻底关掉动效层，避免未揭示区块被印成空白 */
  if (mediaPrint()) return bail();

  /* 能力探测：只依赖 requestAnimationFrame。
     揭示机制已改为指针式扫描，不再依赖 IntersectionObserver —— 因此
     对老内核的兼容面反而更宽。 */
  if (!window.requestAnimationFrame) return bail();

  var isTouch = false, isNarrow = false;
  try {
    isTouch = window.matchMedia('(hover: none)').matches ||
              !window.matchMedia('(pointer: fine)').matches;
    isNarrow = window.matchMedia('(max-width: 768px)').matches;
  } catch (e) {}

  /* ─────────── 1. 参数令牌：与 Motion.dev 文档口径对齐 ───────────
     · tween 默认时长 0.3s —— fast/base/slow 三档围绕它取值
     · useSpring { stiffness: 100, damping: 30, restDelta: 0.001 } —— 用于滚动值平滑
     · 弹簧 bounce 0.25 / damping 10 / mass 1 的 UI 等价：略欠阻尼，收尾带一点回感 */
  var T = {
    staggerStep: isNarrow ? 55 : 72,
    maxStagger: 7,
    springSmooth: { stiffness: 100, damping: 30 },
    springUI: { stiffness: 420, damping: 32 },
    springMagnet: { stiffness: 300, damping: 24 },
    countDuration: 900
  };

  /* ─────────── 1b. 任务级异常隔离 ───────────
     本层的核心不变量是「内容永不永久隐藏」。滚动管线上串了多个任务
     （揭示扫描、视差、字带、进度线），若其中任一任务抛错而异常向外传播，
     同一帧里排在它后面的任务就被跳过 —— 揭示扫描一旦被跳过，
     页面下半部分会停在隐藏态。
     因此逐任务 try/catch 隔离；同时累加计数器，避免「静默吞错」把问题藏起来
     （探针会读 window.__motionErrors）。 */
  function noteErr() {
    window.__motionErrors = (window.__motionErrors || 0) + 1;
  }

  /* ─────────── 2. 弹簧积分器（阻尼受迫振子） ─────────── */
  function Spring(cfg, initial) {
    this.k = cfg.stiffness;
    this.c = cfg.damping;
    this.m = 1;
    this.value = initial || 0;
    this.target = this.value;
    this.velocity = 0;
    this.onUpdate = null;
  }

  Spring.prototype.set = function (target) {
    this.target = target;
    if (!this.running) { this.running = true; RAF.add(this); }
  };

  Spring.prototype.step = function (dt) {
    var f = -this.k * (this.value - this.target) - this.c * this.velocity;
    this.velocity += (f / this.m) * dt;
    this.value += this.velocity * dt;
    var settled = Math.abs(this.velocity) < 0.02 &&
                  Math.abs(this.value - this.target) < 0.01;
    if (settled) {
      this.value = this.target;
      this.velocity = 0;
      this.running = false;
      RAF.remove(this);
    }
    if (this.onUpdate) this.onUpdate(this.value, settled);
  };

  /* ─────────── 3. 单 rAF 循环 ─────────── */
  var RAF = (function () {
    var items = [], id = 0, last = 0;

    function loop(now) {
      if (!last) last = now;
      /* dt 上限 1/30s：标签页切回时避免瞬时大补偿把弹簧打飞 */
      var dt = Math.min((now - last) / 1000, 1 / 30);
      last = now;
      for (var i = items.length - 1; i >= 0; i--) items[i].step(dt);
      if (items.length) {
        id = window.requestAnimationFrame(loop);
      } else {
        id = 0;
        last = 0;
      }
    }

    return {
      add: function (s) {
        if (items.indexOf(s) < 0) items.push(s);
        if (!id) id = window.requestAnimationFrame(loop);
      },
      remove: function (s) {
        var i = items.indexOf(s);
        if (i >= 0) items.splice(i, 1);
      }
    };
  })();

  /* ─────────── 4. 滚动管线：一次读取、统一写入 ───────────
     ★ rAF + 定时器双保险
     整条管线（揭示扫描、视差、字带、进度线）都挂在 rAF 上，而 rAF 在下列
     情形会被节流甚至完全停摆：后台标签页、极端省电模式、无头渲染。
     一旦停摆，滚动揭示就再也不会触发 —— 页面下半部分会永久停留在隐藏态。
     这不是假想：本项目的自动化核验环境（Edge 旧版 headless +
     --virtual-time-budget）用连续定时器滚动时，iframe 的 rAF 就被饿死，
     实测 250 帧采样里揭示数恒为 0。
     因此每次调度都附一道 200ms 兜底：rAF 没跑到就同步补跑一次。
     正常浏览器里兜底几乎不会命中，命中时也只是让管线多跑一帧。 */
  var winH = window.innerHeight;
  var scrollTasks = [];      // fn(progress, scrollY)
  var pending = false;
  var rafId = 0;
  var fallbackTimer = 0;

  function scrollMetrics() {
    winH = window.innerHeight;
    return window.pageYOffset || document.documentElement.scrollTop || 0;
  }

  function flush() {
    if (fallbackTimer) { clearTimeout(fallbackTimer); fallbackTimer = 0; }
    rafId = 0;
    pending = false;

    var y = scrollMetrics();
    var docH = Math.max(1, document.documentElement.scrollHeight - winH);
    var p = Math.min(1, Math.max(0, y / docH));
    for (var i = 0; i < scrollTasks.length; i++) {
      /* 逐任务隔离：一个任务抛错不得让同帧后续任务（含揭示扫描）失效 */
      try { scrollTasks[i](p, y); } catch (e) { noteErr(); }
    }
  }

  function onScroll() {
    if (pending) return;
    pending = true;
    rafId = window.requestAnimationFrame(flush);
    fallbackTimer = window.setTimeout(function () {
      if (!pending) return;
      if (rafId) { window.cancelAnimationFrame(rafId); rafId = 0; }
      flush();
    }, 200);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', function () {
    winH = window.innerHeight;
    onScroll();
  }, { passive: true });
  /* 标签页重新可见 / 从往返缓存恢复时补跑一次，覆盖「后台期间滚动」的情形 */
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) onScroll();
  });

  /* ─────────── 5. 滚动进度条（Motion.dev: scaleX ← scrollYProgress） ─────────── */
  function initProgressBar() {
    var bar = document.createElement('div');
    bar.className = 'm-scroll-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);

    var s = new Spring(T.springSmooth, 0);
    s.onUpdate = function (v) {
      bar.style.transform = 'scaleX(' + v.toFixed(4) + ')';
    };
    scrollTasks.push(function (p) { s.set(p); });
  }

  /* ─────────── 6. 滚动揭示：指针式扫描 ───────────
     ★ 为什么不用 IntersectionObserver
     本项目的验证链是「Edge 旧版 headless + --virtual-time-budget」，
     实测在该环境下程序化滚动之后 IO 不再投递回调（诊断输出 targets=12 / isin=0），
     页面上表现为「滚动过去一片空白」。与其把时间花在环境怪癖上，不如换掉机制：
     指针式扫描在同一帧内按 DOM 顺序自上而下推进，读取代价 O(1) 摊销，
     行为与 IO 等价，且复用已有的滚动管线，少一条时序路径。

     ★ 推进条件 rect.top < winH * 0.9 的语义
     高于视口的元素 rect.top 为负 → 必然满足 → 一次性补齐上方全部元素。
     这正是「锚点跳转 / 浏览器滚动恢复到底部时，上方内容不该卡在隐藏态」所需的行为。

     ★ 多道触发兜底
     初始 rAF、滚动帧、load、resize、pageshow、±两次延时复扫。
     任一环节失灵都不会让内容永久不可见。 */
  function makeSweep(els, ratio, onHit) {
    var ptr = 0;
    return function pass() {
      var limit = winH * ratio;
      while (ptr < els.length) {
        var top = els[ptr].getBoundingClientRect().top;
        if (top >= limit) break;
        onHit(els[ptr]);
        ptr++;
      }
    };
  }

  var LEAF_SEL = '.label, .heading-1, .heading-2, .heading-3, .heading-4, ' +
                 '.stage-title, .body, .body-large, .stage-body';
  var BLOCK_SEL = '.project-card, .figure, .quote-block, .failed-concept, ' +
                  '.skill-bar, .timeline-list > li, .stat-item, .meta-item, .viewer-wrap';

  var sweeps = [];

  function initReveal() {
    /* JS 跳过 .cover / .project-hero / .about-hero ——
       那几处的入场由 css/motion.css 的关键帧负责，叠加会变成「动两次」。 */
    var els = all(LEAF_SEL + ',' + BLOCK_SEL).filter(function (el) {
      return !el.closest('.cover, .project-hero, .about-hero');
    });
    if (!els.length) return;

    /* 同一 section 内按 DOM 顺序编号 → 横向 cascade，无需在 HTML 里手写延迟 */
    var counterMap = new Map();
    function groupOf(el) {
      return el.closest('section, footer') || document.body;
    }
    els.forEach(function (el) {
      var g = groupOf(el);
      if (!counterMap.has(g)) counterMap.set(g, { n: 0 });
      var c = counterMap.get(g);
      var step = Math.min(c.n++, T.maxStagger) * T.staggerStep;
      el.style.setProperty('--m-delay', step + 'ms');
    });

    mainSweep = makeSweep(els, 0.9, function (el) {
      /* 用 style 而非 class 记状态：避免与任何外部 class 命名冲突 */
      if (el.__revealed) return;
      el.__revealed = true;
      el.classList.add('is-in');
      /* .figure 的 clip 揭示跟父级同步 —— 父级揭示前图片不可见，故不会闪 */
      if (el.classList.contains('figure')) {
        var img = el.querySelector('img');
        if (img) img.classList.add('is-in');
      }
    });
    sweeps.push(mainSweep);
  }

  var mainSweep = null;

  function schedulePasses() {
    function run() {
      for (var i = 0; i < sweeps.length; i++) {
        /* 逐 sweep 隔离：一个 sweep 出错不该让其余 sweep 当帧失效。
           run() 有 rAF / 定时器 / scrollTasks 三条入口，其中 rAF 与定时器
           两条是「裸调用」，没有 flush 那层保护，所以隔离必须写在这里。 */
        try { sweeps[i](); } catch (e) { noteErr(); }
      }
    }
    window.requestAnimationFrame(run);
    setTimeout(run, 60);          /* rAF 被节流时的首帧兜底 */
    scrollTasks.push(run);
    window.addEventListener('load', run, { once: true });
    window.addEventListener('pageshow', run);
    window.addEventListener('resize', run, { passive: true });
    /* 字体与图片落地后布局会位移，复扫两次把「当时还在折线下」的元素补上 */
    setTimeout(run, 400);
    setTimeout(run, 1500);
  }

  /* ─────────── 7. 图片：骨架 shimmer + clip 揭示 ───────────
     clipPath inset(0 50% 0 50%) → inset(0 0 0 0)：从中间向两侧展开。
     揭示时机由上面的 mainSweep 统一驱动（.m-clip 与 .is-in 配对）。 */
  function initFigures() {
    all('.figure, .project-card-image').forEach(function (wrap) {
      var img = wrap.querySelector('img');
      if (!img) return;

      if (!img.complete) {
        wrap.classList.add('is-loading');
        var done = function () { wrap.classList.remove('is-loading'); };
        img.addEventListener('load', done, { once: true });
        img.addEventListener('error', done, { once: true });
        setTimeout(done, 6000);           /* 兜底：加载事件丢失也不会一直闪 */
      }
    });

    all('.figure img').forEach(function (img) {
      img.classList.add('m-clip');
    });
  }

  /* ─────────── 8. 视差：封面构图板 → scroll zoom ───────────
     不用 translateY：.cover-art 是 overflow:hidden 的裁剪框，
     平移会在下缘露出空白。改用 1 → 1.07 的缩放（Motion.dev 的 Scroll Zoom Hero），
     缩放只会裁掉边缘、永远不会露出空白。 */
  function initCoverZoom() {
    var cover = document.querySelector('.cover');
    var art = cover && cover.querySelector('.cover-art');
    if (!art) return;
    var svgs = all('.cover-svg', art);
    if (!svgs.length) return;

    var amp = isNarrow ? 0.03 : 0.07;
    var s = new Spring(T.springSmooth, 1);
    s.onUpdate = function (v) {
      var t = 'scale(' + v.toFixed(4) + ')';
      svgs.forEach(function (el) { el.style.transform = t; });
    };

    scrollTasks.push(function (p, y) {
      var top = cover.offsetTop;
      var h = Math.max(1, cover.offsetHeight);
      var prog = Math.min(1, Math.max(0, (y - top) / h));
      s.set(1 + prog * amp);
    });
  }

  /* ─────────── 9. 滚动字带（POCH 的 scroll text lines） ───────────
     两行反向位移，全部由滚动位置驱动。实心 / 描边交替是黑白体系下
     唯一能做出「层次」而不动色相的手法。 */
  function initTicker() {
    var band = document.querySelector('.ticker-band');
    if (!band) return;
    band.setAttribute('aria-hidden', 'true');

    var rows = all('.m-ticker', band);
    if (!rows.length) return;

    var built = false;

    function build() {
      rows.forEach(function (row) {
        var base = row.firstElementChild;
        if (!base) return;
        while (row.children.length > 1) row.removeChild(row.lastElementChild);

        var unit = base.offsetWidth || 0;
        if (!unit) { built = false; return; }

        var need = Math.ceil(window.innerWidth / unit) + 3;
        for (var i = 1; i < need; i++) {
          var c = base.cloneNode(true);
          c.classList.toggle('is-outline', i % 2 === 1);
          row.appendChild(c);
        }
        row.__unit = unit;
      });
      built = true;
    }

    build();

    function wrap(v, w) {
      var m = v % w;
      return m > 0 ? m - w : m;
    }

    scrollTasks.push(function (p, y) {
      if (!built) return;
      var amt = y * 0.32 * (isNarrow ? 0.6 : 1);
      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        if (!row.__unit) continue;
        row.style.transform = 'translate3d(' +
          wrap((i === 0 ? -1 : 1) * amt, row.__unit).toFixed(2) + 'px,0,0)';
      }
    });

    var rt = 0;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () { built = false; build(); onScroll(); }, 200);
    }, { passive: true });
  }

  /* ─────────── 10. 时间线 scrub 进度线（Modulify + Motion.dev） ───────────
     offset 口径 ["start end", "end start"]：元素顶进视口底为 0、底出视口顶为 1。 */
  function initScrubLines() {
    all('.timeline-list').forEach(function (list) {
      var line = document.createElement('span');
      line.className = 'm-scrub-line';
      line.setAttribute('aria-hidden', 'true');
      list.appendChild(line);

      function measure() {
        var lastLi = list.querySelector('li:last-child');
        /* 末条 li 的 border-left 被 style.css 去掉，进度线也不该越过它 */
        var h = list.offsetHeight - (lastLi ? lastLi.offsetHeight : 0);
        line.style.height = Math.max(0, h) + 'px';
      }
      measure();

      var s = new Spring(T.springSmooth, 0);
      s.onUpdate = function (v) {
        line.style.transform = 'scaleY(' + v.toFixed(4) + ')';
      };

      scrollTasks.push(function () {
        var r = list.getBoundingClientRect();
        var total = winH + r.height;
        var prog = total > 0 ? (winH - r.top) / total : 0;
        s.set(Math.min(1, Math.max(0, prog)));
      });

      window.addEventListener('resize', measure, { passive: true });
    });
  }

  /* ─────────── 11. 数字滚动计数（Modulify） ───────────
     取值如 73% / 12 / 4.5/5，按「前缀 + 数值 + 后缀」拆分，
     小数位数由原串决定，收尾必然回到原文，不做四舍五入漂移。 */
  function initCounters() {
    var els = all('.stat-number');
    if (!els.length) return;

    var items = [];
    els.forEach(function (el) {
      var raw = el.textContent.trim();
      var m = raw.match(/^([^\d]*)(\d+(?:\.\d+)?)([\s\S]*)$/);
      if (!m) return;
      items.push({
        el: el,
        raw: raw,
        pre: m[1],
        suf: m[3],
        target: parseFloat(m[2]),
        dec: (m[2].split('.')[1] || '').length
      });
    });
    if (!items.length) return;

    function finalize() {
      items.forEach(function (it) {
        if (it.el.textContent !== it.raw) it.el.textContent = it.raw;
      });
    }

    function run(it) {
      var t0 = 0;
      var step = function (now) {
        if (!t0) t0 = now;
        var k = Math.min(1, (now - t0) / T.countDuration);
        var e = 1 - Math.pow(1 - k, 3);                 /* easeOutCubic */
        it.el.textContent = it.pre + (it.target * e).toFixed(it.dec) + it.suf;
        if (k < 1) {
          window.requestAnimationFrame(step);
        } else {
          it.el.textContent = it.raw;                   /* 收尾必然精确回到原文 */
        }
      };
      window.requestAnimationFrame(step);
    }

    /* 与揭示共用指针式扫描：数字进入视口下缘 15% 以内即起跳 */
    var done = new Map();
    sweeps.push(makeSweep(items.map(function (it) { return it.el; }), 0.85, function (el) {
      if (done.has(el)) return;
      done.set(el, true);
      for (var i = 0; i < items.length; i++) {
        if (items[i].el === el) { run(items[i]); break; }
      }
    }));

    /* 打印前归位，避免 PDF 里出现中断的中间值 */
    window.addEventListener('beforeprint', finalize);
    /* 兜底：无论发生什么，6s 后一律回到原文 */
    setTimeout(finalize, 6000);
  }

  /* ─────────── 12. 磁性按钮（Webflow 的箭头位移 + POCH 的跟手反馈） ─────────── */
  function initMagnetic() {
    if (isTouch) return;
    all('.btn').forEach(function (btn) {
      var mx = new Spring(T.springMagnet, 0);
      var my = new Spring(T.springMagnet, 0);
      var apply = function () {
        btn.style.setProperty('--m-mx', mx.value.toFixed(2) + 'px');
        btn.style.setProperty('--m-my', my.value.toFixed(2) + 'px');
      };
      mx.onUpdate = apply;
      my.onUpdate = apply;

      btn.addEventListener('mousemove', function (e) {
        var r = btn.getBoundingClientRect();
        var dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
        var dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
        mx.set(Math.max(-1, Math.min(1, dx)) * 5);
        my.set(Math.max(-1, Math.min(1, dy)) * 4);
      });

      btn.addEventListener('mouseleave', function () {
        mx.set(0);
        my.set(0);
      });
    });
  }

  /* ─────────── 13. 卡片装饰层注入（Landdding 的悬停遮罩 + CTA 上滑） ───────────
     注入为 aria-hidden 的纯装饰元素，保持 HTML 文件干净、便于手改文案。 */
  function initCardDecor() {
    all('.project-card').forEach(function (card) {
      var image = card.querySelector('.project-card-image');
      if (image && !image.querySelector('.project-card-shade')) {
        var shade = document.createElement('span');
        shade.className = 'project-card-shade';
        shade.setAttribute('aria-hidden', 'true');
        image.appendChild(shade);
      }
      var body = card.querySelector('.project-card-body');
      if (body && !body.querySelector('.card-cta')) {
        var cta = document.createElement('span');
        cta.className = 'card-cta';
        cta.setAttribute('aria-hidden', 'true');
        var inner = document.createElement('span');
        inner.textContent = '查看项目';
        cta.appendChild(inner);
        body.appendChild(cta);
      }
    });
  }

  /* ─────────── 14. 滚动方向隐藏导航（Motion.dev: scroll-hide-header） ───────────
     main.js 管 .scrolled 与封面的 cover-mode / nav-revealed，
     本文件只管 .nav-hide —— 两组 class 互不覆盖。
     移动端不做：屏幕太小，导航常驻更实用。 */
  function initNavDirection() {
    var nav = document.querySelector('.nav');
    if (!nav || isNarrow || isTouch) return;

    var last = scrollMetrics();
    var acc = 0;

    scrollTasks.push(function (p, y) {
      if (nav.classList.contains('menu-open')) return;

      var body = document.body;
      var inCover = body.classList.contains('cover-mode') &&
                    !body.classList.contains('nav-revealed');
      if (inCover) return;                      // 封面期间由 cover-mode 负责收起

      if (y < 320) {                            // 靠近顶部恒显示
        nav.classList.remove('nav-hide');
        last = y;
        acc = 0;
        return;
      }

      acc += y - last;
      last = y;

      if (acc > 64) {
        nav.classList.add('nav-hide');
        acc = 0;
      } else if (acc < -64) {
        nav.classList.remove('nav-hide');
        acc = 0;
      }
    });
  }

  /* ─────────── 15. 页面切换 ───────────
     现代 Chromium：@view-transition { navigation: auto } 由 CSS 声明即生效，
     跨文档导航自动套上淡出 / 淡入（Motion.dev 的 AnimatePresence 的跨页等价物）。
     其余内核走 JS 降级：先让 body 淡出 220ms 再跳转。 */
  function initPageTransitions() {
    var supportsVT = false;
    try {
      supportsVT = !!(window.CSS && CSS.supports && CSS.supports('view-transition-name: none'));
    } catch (e) {}
    if (supportsVT) return;

    document.addEventListener('click', function (e) {
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      if (a.target && a.target !== '_self') return;
      if (a.hasAttribute('download') || a.hasAttribute('data-no-transition')) return;

      var href = a.getAttribute('href');
      if (!href || href.charAt(0) === '#') return;
      if (/^(mailto:|tel:|javascript:|blob:|data:)/i.test(href)) return;

      var url;
      try { url = new URL(a.href, location.href); } catch (err) { return; }
      if (url.origin !== location.origin) return;
      /* 同页锚点不拦截，交给原生平滑滚动 */
      if (url.pathname === location.pathname && url.search === location.search) return;

      e.preventDefault();

      var left = false;
      var go = function () {
        if (left) return;
        left = true;
        location.href = a.href;
      };

      document.body.classList.add('is-leaving');
      setTimeout(go, 230);
      window.addEventListener('pagehide', go);
    }, true);
  }

  /* ─────────── 16. 启动 ─────────── */
  function start() {
    initProgressBar();
    initCardDecor();
    initFigures();
    initReveal();
    initCoverZoom();
    initTicker();
    initScrubLines();
    initCounters();
    initMagnetic();
    initNavDirection();
    initPageTransitions();

    /* 所有 sweep 注册完毕后再统一接线，避免漏掉最后注册的那一个 */
    schedulePasses();

    /* 首帧对齐 + 二次对齐：字体与图片落地后布局会变，滚动进度需要重算 */
    onScroll();
    window.addEventListener('load', onScroll, { once: true });
  }

  try {
    start();
  } catch (e) {
    /* 任何异常都不该让页面停在「内容隐藏」状态 */
    bail();
  }
})();
