/*
  翁彥斌 · 工业设计作品集 v2
  越野车玩具 3D 交互查看器
  - 加载 OBJ + MTL
  - 统一石膏素模材质（去色，保留柔和阴影）
  - 自动运镜（产品展示级环绕 + 俯仰微动），拖拽可随时打断
  - 纯色 PBR 材质（橄榄绿车身 + 橙色点缀 + 深色轮胎 + 灰金属件）—— 已弃用
*/

(function () {
  'use strict';

  const container = document.getElementById('model-viewer');
  if (!container) return;
  if (getComputedStyle(container).position === 'static') container.style.position = 'relative';

  const loadingEl = container.querySelector('.viewer-loading');

  /* ───────── 场景 ───────── */
  const scene = new THREE.Scene();
  // 暖白统一：不设 scene.background，画布透明，露出 CSS .model-viewer 的暖白渐变，对齐全站 Editorial Material 基调

  /* ───────── 相机 ───────── */
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000); // 长焦视角：减少畸变，模型更平展突出
  camera.position.set(80, 55, 80);

  /* ───────── 渲染器 ───────── */
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  if ('outputEncoding' in renderer) renderer.outputEncoding = THREE.sRGBEncoding;
  if ('toneMapping' in renderer) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping; // 电影级色调映射：压暗高光、提升对比
    renderer.toneMappingExposure = 0.82;                // 调低曝光，整体压暗
  }
  if ('physicallyCorrectLights' in renderer) renderer.physicallyCorrectLights = false;
  container.appendChild(renderer.domElement);

  /* ───────── 灯光 ───────── */
  // 暖白基调下略提环境光，深灰石膏不死黑；主光强、填充弱保持对比
  const ambient = new THREE.AmbientLight(0xffffff, 0.34);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.3);
  keyLight.position.set(60, 90, 50);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.width = 2048;
  keyLight.shadow.mapSize.height = 2048;
  keyLight.shadow.camera.near = 1;
  keyLight.shadow.camera.far = 600;
  keyLight.shadow.camera.left = -200;
  keyLight.shadow.camera.right = 200;
  keyLight.shadow.camera.top = 200;
  keyLight.shadow.camera.bottom = -200;
  keyLight.shadow.bias = -0.0005;
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xfff0e0, 0.15);
  fillLight.position.set(-50, 40, -40);
  scene.add(fillLight);

  const rimLight = new THREE.DirectionalLight(0xfff1e0, 0.7); // 暖白轮廓光，统一暖调并勾边
  rimLight.position.set(0, 30, -80);
  scene.add(rimLight);

  /* ───────── 地面（暖白，接收落地阴影）───────── */
  // 暖白地面：接近背景色，接收落地柔影，与全站暖白融合（而非深色割裂块）
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(800, 800),
    new THREE.MeshStandardMaterial({ color: 0xece7e1, roughness: 1, metalness: 0 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  /* ───────── 控制器（仅旋转） ───────── */
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableZoom = false;
  controls.enablePan = false;
  controls.enableRotate = true;
  controls.rotateSpeed = 0.85;
  controls.autoRotate = false;
  controls.target.set(0, 0, 0);

  /* ───────── 石膏素模材质 ───────── */
  // 深中性灰石膏：暖白背景下靠深灰本体 + 落地柔影与背景区分，保留哑光素模质感
  const plaster = new THREE.MeshStandardMaterial({
    color: 0x8c8c90,
    roughness: 0.95,
    metalness: 0.0,
    side: THREE.DoubleSide,
    flatShading: false
  });

  /* ───────── 加载模型 ───────── */
  function b64ToBlobUrl(b64, mime) {
    const bin = atob(b64);
    const len = bin.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    return URL.createObjectURL(new Blob([bytes], { type: mime }));
  }

  let mtlUrl, objUrl;
  const hasBase64 = (typeof window.__TOY_CAR_MTL_B64 === 'string' &&
                     typeof window.__TOY_CAR_OBJ_B64 === 'string');
  if (hasBase64) {
    mtlUrl = b64ToBlobUrl(window.__TOY_CAR_MTL_B64, 'model/mtl');
    objUrl = b64ToBlobUrl(window.__TOY_CAR_OBJ_B64, 'model/obj');
    if (loadingEl) loadingEl.textContent = '正在解析模型…';
  } else {
    mtlUrl = '../assets/models/toy-car.mtl';
    objUrl = '../assets/models/toy-car.obj';
  }

  let modelMaxDim = 100;
  let frameRadius = 140;   // 取景半径（包围球拟合，保证旋转全程不裁切）
  let currentModel = null; // 已加载模型，供观众校验取包围盒

  function applyPlaster(object) {
    object.traverse(function (child) {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        child.material = plaster;
        child.geometry.computeVertexNormals();
      }
    });
  }

  /* 以包围球拟合取景：无论模型高矮胖瘦，旋转一圈都不会被画面裁切（观众完整度原则） */
  /* 视图焦点：相对模型包围盒中心的偏移（推荐）。默认 0 即几何中心；角色模型可设为 [0, 眼部高度, 0] 使其面部居中。
     优先级：URL ?fx/fy/fz= > window.__MODEL_FOCUS_OFFSET / __TOY_CAR_FOCUS > window.__MODEL_FOCUS_WORLD（旧语义） */
  function vec3FromArr(arr) {
    return (Array.isArray(arr) && arr.length === 3) ? new THREE.Vector3(arr[0], arr[1], arr[2]) : null;
  }
  function parseFocusOffset() {
    const p = new URLSearchParams(location.search);
    if (p.has('fx') || p.has('fy') || p.has('fz')) {
      return new THREE.Vector3(
        parseFloat(p.get('fx')) || 0,
        parseFloat(p.get('fy')) || 0,
        parseFloat(p.get('fz')) || 0
      );
    }
    return vec3FromArr(window.__MODEL_FOCUS_OFFSET) ||
           vec3FromArr(window.__TOY_CAR_FOCUS) ||
           null;
  }
  function parseFocusWorld() {
    return vec3FromArr(window.__MODEL_FOCUS_WORLD);
  }
  /* 画幅中心微调：当几何中心/视觉中心已在画面中央，但仍感觉“偏”时，用此参数平移画幅中心。
     单位同模型，正 x 向右、正 y 向上。URL ?px/py/pz= 或 window.__MODEL_PAN。 */
  function parsePan() {
    const p = new URLSearchParams(location.search);
    return new THREE.Vector3(
      parseFloat(p.get('px')) || (vec3FromArr(window.__MODEL_PAN)?.x || 0),
      parseFloat(p.get('py')) || (vec3FromArr(window.__MODEL_PAN)?.y || 0),
      parseFloat(p.get('pz')) || (vec3FromArr(window.__MODEL_PAN)?.z || 0)
    );
  }

  function frameModel(object) {
    currentModel = object;
    let box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    object.position.sub(center); // 居中到原点
    box = new THREE.Box3().setFromObject(object); // 重新计算，后续取景基于新坐标

    // 视觉中心 = 包围盒中心 + 焦点偏移 + 画幅中心微调
    const focusOffset = parseFocusOffset();
    const focusWorld = parseFocusWorld();
    // 兼容旧语义：__MODEL_FOCUS_WORLD 传入的是模型局部坐标，需换算到居中后的坐标系
    const legacyOffset = focusWorld ? focusWorld.clone().sub(center) : null;
    const pan = parsePan();
    camTarget.copy(focusOffset || legacyOffset || new THREE.Vector3(0, 0, 0)).add(pan);
    controls.target.copy(camTarget);

    const size = box.getSize(new THREE.Vector3());
    modelMaxDim = Math.max(size.x, size.y, size.z) || 100;

    resize(); // 先确保相机宽高比正确，取景才准确
    const sph = box.getBoundingSphere(new THREE.Sphere());
    const Rsphere = sph.radius || (modelMaxDim * 0.6);
    // 以视觉中心为圆心取景：取 8 角点到视觉中心的最大距离作为拟合半径，确保整模型可见
    let Rfit = Rsphere;
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z]) {
          const d = new THREE.Vector3(x, y, z).distanceTo(camTarget);
          if (d > Rfit) Rfit = d;
        }
    const vHalf = THREE.MathUtils.degToRad(camera.fov) / 2;
    const hHalf = Math.atan(Math.tan(vHalf) * (camera.aspect || 1));
    const half = Math.min(vHalf, hHalf);
    frameRadius = (Rfit / Math.sin(half)) * 1.12; // 1.12 = 安全余量，模型约占画面 ~89%

    const dir = new THREE.Vector3(
      Math.sin(BASE_POL) * Math.cos(START_AZ),
      Math.cos(BASE_POL),
      Math.sin(BASE_POL) * Math.sin(START_AZ)
    );
    camera.position.copy(camTarget).addScaledVector(dir, frameRadius);
    camera.lookAt(camTarget);
    controls.update();

    ground.position.y = box.min.y; // 模型最低点（已居中）承接落地阴影
  }

  /* ───────── 自动运镜 + 拖拽打断 ───────── */
  const AUTO_LOOP = 24;            // 一圈时长（秒）
  const START_AZ = Math.PI * 0.25; // 起始方位：前右 3/4 视角
  const BASE_POL = Math.PI * 0.43; // 基础俯仰（距 +Y 轴约 77°），视线约 13° 高于水平面，更偏观众平视
  const POL_SWING = 0.22;          // 俯仰摆动 ±12.6°，范围约 0°–26° 高于水平面，多角度且不穿透实心地面
  let playing = true;
  const clock = new THREE.Clock();
  const camTarget = new THREE.Vector3(0, 0, 0);

  const hint = document.createElement('div');
  hint.textContent = '自动运镜中 · 拖拽可随时打断';
  hint.style.cssText = 'position:absolute;left:14px;top:14px;padding:6px 12px;border-radius:14px;' +
    'background:rgba(20,20,22,.55);color:#fff;font:500 12px/1 "Inter Tight",system-ui;pointer-events:none;' +
    'transition:opacity .4s;letter-spacing:.3px;';
  container.appendChild(hint);

  const replayBtn = document.createElement('button');
  replayBtn.textContent = '▶ 重新播放运镜';
  replayBtn.style.cssText = 'position:absolute;right:14px;bottom:14px;padding:8px 14px;border:none;' +
    'border-radius:20px;background:rgba(20,20,22,.72);color:#fff;font:600 13px/1 "Inter Tight",system-ui;' +
    'cursor:pointer;backdrop-filter:blur(4px);opacity:0;transition:opacity .3s;pointer-events:none;';
  container.appendChild(replayBtn);

  function startPlaying() {
    playing = true;
    clock.start();
    hint.style.opacity = '1';
    replayBtn.style.opacity = '0';
    replayBtn.style.pointerEvents = 'none';
  }
  function stopPlaying() {
    playing = false;
    hint.style.opacity = '0';
    replayBtn.style.opacity = '1';
    replayBtn.style.pointerEvents = 'auto';
  }
  replayBtn.addEventListener('click', startPlaying);
  controls.addEventListener('start', stopPlaying);

  /* ───────── 影棚调色面板（实时可调，对齐全站设计语言）───────── */
  // 风格：铜色强调(--accent #b87333) + 16px 圆角(--radius-lg) + Inter Tight + 深色玻璃
  const FONT = "'Inter Tight','Inter',system-ui,sans-serif";
  const ACCENT = '#b87333';
  const panel = document.createElement('div');
  panel.style.cssText = 'position:absolute;left:14px;bottom:14px;display:none;flex-direction:column;' +
    'gap:9px;padding:14px 16px;width:208px;border-radius:16px;background:rgba(20,20,22,.82);' +
    'color:#f7f5f2;font:500 12px/1.4 ' + FONT + ';backdrop-filter:blur(8px);' +
    'box-shadow:0 12px 48px rgba(0,0,0,.45);z-index:5;';
  panel.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">' +
      '<span style="font-weight:700;letter-spacing:.5px;color:' + ACCENT + ';">影棚调色</span>' +
      '<button data-close style="background:none;border:none;color:#f7f5f2;cursor:pointer;font-size:16px;line-height:1;">×</button>' +
    '</div>' +
    '<label style="display:flex;justify-content:space-between;align-items:center;gap:8px;">背景<input type="color" data-bg value="#f7f5f2" style="width:42px;height:24px;border:none;background:none;cursor:pointer;"></label>' +
    '<label style="display:flex;justify-content:space-between;align-items:center;gap:8px;">地面<input type="color" data-ground value="#ece7e1" style="width:42px;height:24px;border:none;background:none;cursor:pointer;"></label>' +
    '<label style="display:flex;justify-content:space-between;align-items:center;gap:8px;">轮廓光色<input type="color" data-rim value="#fff1e0" style="width:42px;height:24px;border:none;background:none;cursor:pointer;"></label>' +
    '<label style="display:flex;flex-direction:column;gap:4px;">曝光 <input type="range" data-exp min="0.5" max="1.2" step="0.01" value="0.82" style="width:100%;accent-color:' + ACCENT + ';"></label>' +
    '<label style="display:flex;flex-direction:column;gap:4px;">主光 <input type="range" data-key min="0.5" max="2" step="0.05" value="1.3" style="width:100%;accent-color:' + ACCENT + ';"></label>' +
    '<label style="display:flex;flex-direction:column;gap:4px;">轮廓光 <input type="range" data-rimi min="0" max="1.5" step="0.05" value="0.7" style="width:100%;accent-color:' + ACCENT + ';"></label>' +
    '<label style="display:flex;flex-direction:column;gap:4px;">填充光 <input type="range" data-fill min="0" max="1" step="0.05" value="0.15" style="width:100%;accent-color:' + ACCENT + ';"></label>' +
    '<button data-selfcheck style="margin-top:4px;padding:8px 10px;border:none;border-radius:10px;background:' + ACCENT + ';color:#fff;font:600 12px/1 ' + FONT + ';cursor:pointer;">🔍 自检（多角度巡检）</button>';
  container.appendChild(panel);

  const panelBtn = document.createElement('button');
  panelBtn.textContent = '🎨 影棚调色';
  panelBtn.style.cssText = 'position:absolute;left:14px;bottom:14px;padding:8px 14px;border:none;' +
    'border-radius:20px;background:rgba(20,20,22,.72);color:#fff;font:600 13px/1 ' + FONT + ';' +
    'cursor:pointer;backdrop-filter:blur(4px);z-index:4;';
  container.appendChild(panelBtn);

  panelBtn.addEventListener('click', () => { panel.style.display = 'flex'; panelBtn.style.display = 'none'; });
  panel.querySelector('[data-close]').addEventListener('click', () => { panel.style.display = 'none'; panelBtn.style.display = 'block'; });

  // URL 预设（便于分享固定配色，如 ?bg=0a0c10&exp=0.75&rimi=0.9）
  const q = new URLSearchParams(location.search);
  const setVal = (sel, v) => { const el = panel.querySelector(sel); if (el && v != null) el.value = v; };
  if (q.get('bg'))  { scene.background.set('#' + q.get('bg')); setVal('[data-bg]', '#' + q.get('bg')); }
  if (q.get('exp')) { renderer.toneMappingExposure = parseFloat(q.get('exp')); setVal('[data-exp]', q.get('exp')); }
  if (q.get('rimi')) { rimLight.intensity = parseFloat(q.get('rimi')); setVal('[data-rimi]', q.get('rimi')); }

  panel.querySelector('[data-bg]').addEventListener('input', e => scene.background.set(e.target.value));
  panel.querySelector('[data-ground]').addEventListener('input', e => ground.material.color.set(e.target.value));
  panel.querySelector('[data-rim]').addEventListener('input', e => rimLight.color.set(e.target.value));
  panel.querySelector('[data-exp]').addEventListener('input', e => renderer.toneMappingExposure = parseFloat(e.target.value));
  panel.querySelector('[data-key]').addEventListener('input', e => keyLight.intensity = parseFloat(e.target.value));
  panel.querySelector('[data-rimi]').addEventListener('input', e => rimLight.intensity = parseFloat(e.target.value));
  panel.querySelector('[data-fill]').addEventListener('input', e => fillLight.intensity = parseFloat(e.target.value));

  /* ───────── 自检：多角度巡检（破面 / 角度一致性）───────── */
  const checkOverlay = document.createElement('div');
  checkOverlay.style.cssText = 'position:absolute;inset:0;display:none;flex-direction:column;' +
    'align-items:center;justify-content:flex-start;gap:10px;padding:18px;overflow:auto;' +
    'background:rgba(18,18,20,.92);color:#f7f5f2;font:' + FONT + ';z-index:10;border-radius:16px;';
  container.appendChild(checkOverlay);

  function runSelfCheck(angles) {
    angles = angles || 8;
    stopPlaying();
    const savedPos = camera.position.clone();
    const savedTarget = controls.target.clone();
    const shots = [];
    const darkRatios = [];
    const W = renderer.domElement.width, H = renderer.domElement.height;
    const tmp = document.createElement('canvas');
    tmp.width = W; tmp.height = H;
    const tctx = tmp.getContext('2d');
    for (let i = 0; i < angles; i++) {
      const az = i / angles * Math.PI * 2;
      const pol = BASE_POL + POL_SWING * Math.sin(i / angles * Math.PI * 2);
      const r = frameRadius; // 与观众校验一致，保证取景半径统一
      const dir = new THREE.Vector3(Math.sin(pol) * Math.cos(az), Math.cos(pol), Math.sin(pol) * Math.sin(az));
      camera.position.copy(camTarget).addScaledVector(dir, r);
      camera.lookAt(camTarget);
      controls.target.copy(camTarget);
      renderer.render(scene, camera);
      shots.push(renderer.domElement.toDataURL('image/png'));
      tctx.drawImage(renderer.domElement, 0, 0);
      const data = tctx.getImageData(0, 0, W, H).data;
      let dark = 0; const total = data.length / 4;
      for (let p = 0; p < data.length; p += 4) {
        if (data[p] < 45 && data[p + 1] < 45 && data[p + 2] < 45) dark++;
      }
      darkRatios.push(dark / total);
    }
    camera.position.copy(savedPos);
    controls.target.copy(savedTarget);
    controls.update();
    renderer.render(scene, camera);
    const sorted = darkRatios.slice().sort((a, b) => a - b);
    const med = sorted[Math.floor(sorted.length / 2)];
    const flagged = [];
    darkRatios.forEach((v, idx) => { if (v > med + 0.06) flagged.push(idx); });
    showSelfCheckOverlay(shots, darkRatios, flagged, med);
  }

  function showSelfCheckOverlay(shots, ratios, flagged, med) {
    const n = shots.length;
    const cols = n <= 4 ? n : (n <= 6 ? 3 : 4);
    let html = '<div style="width:100%;display:flex;justify-content:space-between;align-items:center;">' +
      '<span style="font-weight:700;letter-spacing:.5px;color:' + ACCENT + ';">多角度自检 · ' + n + ' 视角</span>' +
      '<button data-close-check style="background:none;border:none;color:#f7f5f2;cursor:pointer;font-size:18px;line-height:1;">×</button></div>';
    const verdict = flagged.length === 0
      ? '<div style="color:#7fe3a0;font-weight:600;">✅ 各角度暗区占比一致（中位 ' + (med * 100).toFixed(1) + '%），未发现明显破面</div>'
      : '<div style="color:#ffb454;font-weight:600;">⚠️ 检测到 ' + flagged.length + ' 个角度暗区异常（疑似破面）：#' + flagged.map(x => x + 1).join(' #') + '，请旋转到该角度核对</div>';
    html += verdict;
    html += '<div style="display:grid;grid-template-columns:repeat(' + cols + ',1fr);gap:8px;width:100%;">';
    shots.forEach(function (s, i) {
      const warn = flagged.indexOf(i) >= 0;
      html += '<div style="border:2px solid ' + (warn ? '#ffb454' : 'transparent') + ';border-radius:8px;overflow:hidden;position:relative;">' +
        '<img src="' + s + '" style="width:100%;display:block;">' +
        '<span style="position:absolute;left:4px;top:4px;background:rgba(0,0,0,.55);padding:1px 6px;border-radius:6px;font-size:11px;">#' + (i + 1) + ' · 暗区' + (ratios[i] * 100).toFixed(1) + '%</span></div>';
    });
    html += '</div>';
    html += '<div style="font-size:11px;opacity:.7;line-height:1.5;">说明：逐个渲染各方位视角并统计近黑像素占比，某角度占比显著高于其余角度即标橙告警（破面常表现为局部黑洞）。点击标橙视角对应角度旋转核对即可定位问题面。</div>';
    checkOverlay.innerHTML = html;
    checkOverlay.style.display = 'flex';
    checkOverlay.querySelector('[data-close-check]').addEventListener('click', function () { checkOverlay.style.display = 'none'; });
  }

  panel.querySelector('[data-selfcheck]').addEventListener('click', function () { runSelfCheck(8); });

  /* ───────── 👁 观众校验（加载后自动跑完整一圈，保证模型全程完整不裁切）───────── */
  function runAudienceCheck() {
    if (!currentModel) return null;
    const box = new THREE.Box3().setFromObject(currentModel);
    const pts = [];
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z])
          pts.push(new THREE.Vector3(x, y, z));
    const angles = 16; // 一整圈采样
    const savedPos = camera.position.clone();
    const savedTarget = controls.target.clone();
    let worstMag = 0;
    const clipped = [];
    for (let i = 0; i < angles; i++) {
      const az = i / angles * Math.PI * 2;
      const pol = BASE_POL + POL_SWING * Math.sin(i / angles * Math.PI * 2);
      const r = frameRadius;
      const dir = new THREE.Vector3(Math.sin(pol) * Math.cos(az), Math.cos(pol), Math.sin(pol) * Math.sin(az));
      camera.position.copy(camTarget).addScaledVector(dir, r);
      camera.lookAt(camTarget);
      camera.updateMatrixWorld();
      let m = 0;
      for (const p of pts) {
        const ndc = p.clone().project(camera);
        const mag = Math.max(Math.abs(ndc.x), Math.abs(ndc.y));
        if (mag > m) m = mag;
      }
      if (m > worstMag) worstMag = m;
      if (m > 1.0) clipped.push(i + 1); // NDC 超出 [-1,1] = 该角度被裁切
    }
    camera.position.copy(savedPos);
    controls.target.copy(savedTarget);
    controls.update();
    renderer.render(scene, camera);
    // 自校正：若仍裁切，拉远 12% 重试（最多 3 次）
    if (clipped.length && frameRadius < modelMaxDim * 6) {
      frameRadius *= 1.12;
      return runAudienceCheck();
    }
    const complete = clipped.length === 0;
    const fitPercent = Math.round(worstMag * 100);
    // 后台审核条件：自动拉远重校已在上方完成；成品页不向观众暴露校验徽章，仅调试模式可显
    if (window.__SHOW_AUDIENCE_BADGE || new URLSearchParams(location.search).has('debug')) {
      showAudienceBadge(complete, fitPercent, clipped);
    }
    console.log('[观众校验] ' + (complete ? '完整度 100%' : ('角度 #' + clipped.join(' #') + ' 裁切')) + ' · 占比≈' + fitPercent + '%');
    return { complete: complete, fitPercent: fitPercent, clipped: clipped };
  }

  function showAudienceBadge(complete, fitPercent, clipped) {
    const badge = document.createElement('div');
    badge.style.cssText = 'position:absolute;right:14px;top:14px;padding:6px 12px;border-radius:14px;' +
      'font:600 12px/1.3 "Inter Tight",system-ui;z-index:6;pointer-events:none;letter-spacing:.3px;max-width:60%;text-align:right;' +
      (complete ? 'background:rgba(40,120,70,.85);color:#fff;' : 'background:rgba(190,110,30,.9);color:#fff;');
    if (complete) {
      const tip = fitPercent < 75 ? '（占比偏小，可拉近）' : (fitPercent > 97 ? '（接近裁切，余量偏小）' : '');
      badge.textContent = '👁 观众校验 · 完整度 100% · 占比≈' + fitPercent + '%' + tip;
    } else {
      badge.textContent = '👁 观众校验 · 角度 #' + clipped.join(' #') + ' 裁切 · 已自动拉远重校';
    }
    container.appendChild(badge);
    setTimeout(function () { badge.style.transition = 'opacity .8s'; badge.style.opacity = '0.32'; }, 7000);
  }

  function updateAutoCamera() {
    const t = (clock.getElapsedTime() % AUTO_LOOP) / AUTO_LOOP; // 0..1
    const az = START_AZ + t * Math.PI * 2;
    const pol = BASE_POL + POL_SWING * Math.sin(t * Math.PI * 2);
    const r = frameRadius; // 与取景/观众校验一致，放大模型本体且全程不裁切
    camera.position.set(
      camTarget.x + r * Math.sin(pol) * Math.cos(az),
      camTarget.y + r * Math.cos(pol),
      camTarget.z + r * Math.sin(pol) * Math.sin(az)
    );
    camera.lookAt(camTarget);
  }

  /* ───────── 模型加载回调 ───────── */
  function onModelLoaded(object) {
    applyPlaster(object);
    frameModel(object);
    scene.add(object);
    startPlaying();
    if (loadingEl) loadingEl.style.display = 'none';
    runAudienceCheck(); // 👁 作为观众：加载后即跑完整一圈校验完整性
  }

  /* ───────── 加载分流：GLB 优先，否则 OBJ+MTL ───────── */
  const hasGlb = (typeof window.__TOY_CAR_GLB_B64 === 'string');
  function onProgress(xhr) {
    if (loadingEl && xhr && xhr.total) {
      const pct = Math.round((xhr.loaded / xhr.total) * 100);
      loadingEl.textContent = '模型加载中… ' + pct + '%';
    } else if (loadingEl) {
      loadingEl.textContent = '模型加载中…';
    }
  }
  function onError(err) {
    if (loadingEl) loadingEl.textContent = '模型加载失败';
    console.error('model load error:', err);
  }

  if (hasGlb && typeof THREE.GLTFLoader === 'function') {
    // GLB 路线：自带 PBR，统一素模材质，无需 MTL
    const glbUrl = b64ToBlobUrl(window.__TOY_CAR_GLB_B64, 'model/gltf-binary');
    new THREE.GLTFLoader().load(glbUrl, function (gltf) {
      onModelLoaded(gltf.scene);
    }, onProgress, onError);
  } else {
    // OBJ+MTL 路线（当前默认）
    const mtlLoader = new THREE.MTLLoader();
    mtlLoader.load(mtlUrl, function (materials) {
      materials.preload();
      const objLoader = new THREE.OBJLoader();
      objLoader.setMaterials(materials);
      objLoader.load(objUrl, onModelLoaded, onProgress, onError);
    }, undefined, function () {
      // MTL 失败也尝试直接加载 OBJ
      new THREE.OBJLoader().load(objUrl, onModelLoaded, onProgress, onError);
    });
  }

  /* ───────── 自适应尺寸 ───────── */
  function resize() {
    const rect = container.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    const dpr = Math.min(window.devicePixelRatio, 2);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    // setSize 第三个参数 false 避免覆盖 CSS 100%，内部像素尺寸与 CSS 尺寸解耦
    renderer.setSize(w, h, false);
    renderer.setPixelRatio(dpr);
  }
  window.addEventListener('resize', resize);
  resize();

  /* ───────── 调试用：画面中心准星 ───────── */
  const debugCross = document.createElement('div');
  debugCross.style.cssText = 'position:absolute;left:50%;top:50%;width:24px;height:24px;' +
    'transform:translate(-50%,-50%);pointer-events:none;z-index:20;display:none;';
  debugCross.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><line x1="12" y1="4" x2="12" y2="20" stroke="#e24" stroke-width="1"/><line x1="4" y1="12" x2="20" y2="12" stroke="#e24" stroke-width="1"/><circle cx="12" cy="12" r="3" fill="none" stroke="#e24" stroke-width="1"/></svg>';
  container.appendChild(debugCross);
  const showDebug = new URLSearchParams(location.search).has('debug') || window.__MODEL_DEBUG;
  if (showDebug) debugCross.style.display = 'block';

  /* ───────── 渲染循环 ───────── */
  function animate() {
    requestAnimationFrame(animate);
    if (playing) updateAutoCamera();
    controls.update(); // 同步控制器内部状态，打断时无跳变
    renderer.render(scene, camera);
  }
  animate();
})();
