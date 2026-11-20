// Editor das animações de primeira pessoa. A pose vem do servidor (server.py), que usa o mesmo
// código do jogo (fp_arms.py); aqui só desenhamos, editamos o JSON e mostramos o resultado.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const $ = (s) => document.querySelector(s);
const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4, M3 = THREE.Matrix3;
const SAMPLES = 96;
const DEG = 180 / Math.PI;
const FINGERS = ['index', 'middle', 'ring', 'pinky', 'thumb'];
const FINGER_PT = { index: 'Indicador', middle: 'Médio', ring: 'Anelar', pinky: 'Mínimo', thumb: 'Polegar' };
const PHAL = ['base', 'meio', 'ponta'];
const THUMB = ['oposição', 'base', 'meio', 'ponta'];
const CURVES = [
  { name: 'tilt', label: 'Inclinação (peso)', step: 0.01, digits: 3,
    hint: 'Peso (0 a 1) da inclinação da arma definida em "Geral". 1 = pose de recarga completa.' },
  { name: 'bolt', label: 'Bomba / ferrolho', step: 0.01, digits: 3,
    hint: 'Curso da bomba (Macrófaga) ou do ferrolho (Célula B): 0 = fechado, 1 = curso todo.' },
  { name: 'mag', label: 'Carregador', step: 0.01, digits: 3,
    hint: 'Deslocamento do carregador ao longo do eixo dele: 0 = encaixado. Na Célula B, 1 = 20 cm.' },
  { name: 'bump', label: 'Solavanco (m)', step: 0.0005, digits: 4,
    hint: 'Pulo da arma para cima (metros) quando algo encaixa.' },
  { name: 'squeeze', label: 'Aperto da bolsa', step: 0.01, digits: 3,
    hint: 'Bolsa das armas orgânicas: 0 = normal, 1 = apertada (encolhe 45%).' },
];
// Curvas que fazem sentido para a arma do herói (peças animadas que ela tem).
function curvesFor() {
  const anims = Object.values((S.info && S.info.anims) || {});
  const need = { bolt: 'bolt', mag: 'mag', squeeze: 'pulse' };
  return CURVES.filter((c) => !need[c.name] || anims.includes(need[c.name]));
}
const EASES = { smooth: 'suave', linear: 'linear', in: 'acelera', out: 'desacelera', step: 'degrau' };
const EASE_FN = {
  smooth: (u) => u * u * (3 - 2 * u), linear: (u) => u, in: (u) => u * u,
  out: (u) => 1 - (1 - u) * (1 - u), step: (u) => (u >= 1 ? 1 : 0),
};
const SIDE_PT = { L: 'Mão esquerda', R: 'Mão direita' };
const SIDE_COLOR = { L: '#ff9f43', R: '#54a0ff' };
const ID12 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0];

const S = {
  infos: {}, hero: null, info: null,
  anim: null, saved: '', committed: '', undo: [], redo: [], version: 0,
  p: 0, idle: false, playing: false, loop: true, speed: 1,
  baked: null, idleFrame: null, solved: null, cur: null,
  sel: { kind: 'global' }, gizmo: 'translate', helpers: true, freeCam: false,
  dragging: false, clipboard: null, error: null,
};

// ------------------------------------------------------------------------------------------
// Utilidades
// ------------------------------------------------------------------------------------------
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const rnd = (v, d = 6) => +(+v).toFixed(d);
const m4 = (a) => new M4().set(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], 0, 0, 0, 1);
const nz = (v) => (Array.isArray(v) && v.some((x) => x) ? v : null);
const radii = (g) => (Array.isArray(g.r) ? g.r : [g.r, g.r]);
const dur = () => +(S.anim && S.anim.duration) || 1.6;

function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') e.className = v;
    else if (k === 'style') e.style.cssText = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'value') e[k] = v;
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}

async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const r = await fetch(path, opt);
  return r.json();
}

function status(msg, cls = '') {
  const s = $('#status');
  s.textContent = msg;
  s.className = cls;
  s.title = msg;
}
const isDirty = () => S.anim && JSON.stringify(S.anim) !== S.saved;
function refreshStatus() {
  if (S.error) return;
  if (isDirty()) status('● alterações não salvas');
  else status('salvo — igual ao arquivo do jogo', 'ok');
}
function setError(err) {
  S.error = err || null;
  if (err) status('Erro: ' + err, 'bad');
  else refreshStatus();
}

function samePose(a, b) {
  return a.grip === b.grip && JSON.stringify(nz(a.offset)) === JSON.stringify(nz(b.offset))
    && JSON.stringify(nz(a.rot)) === JSON.stringify(nz(b.rot)) && JSON.stringify(a.wrist || null) === JSON.stringify(b.wrist || null)
    && JSON.stringify(a.fingers || {}) === JSON.stringify(b.fingers || {});
}

function curveAt(pts, p) {
  if (!pts || !pts.length) return 0;
  const s = [...pts].sort((a, b) => a[0] - b[0]);
  if (p <= s[0][0]) return s[0][1];
  for (let i = 1; i < s.length; i++) {
    const [t0, v0] = s[i - 1], [t1, v1, e] = s[i];
    if (p < t1) {
      const u = t1 > t0 ? (p - t0) / (t1 - t0) : 1;
      return v0 + (v1 - v0) * EASE_FN[e || 'smooth'](clamp(u, 0, 1));
    }
  }
  return s[s.length - 1][1];
}

// ------------------------------------------------------------------------------------------
// Cena 3D
// ------------------------------------------------------------------------------------------
const view = $('#view');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1));
renderer.outputColorSpace = THREE.SRGBColorSpace;
view.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x2a2e35);

const gameCam = new THREE.PerspectiveCamera(50, 16 / 9, 0.01, 20);
gameCam.lookAt(0, 0, 1);
const freeCam = new THREE.PerspectiveCamera(50, 16 / 9, 0.01, 50);
freeCam.position.set(-0.6, 0.22, -0.42);
const orbit = new OrbitControls(freeCam, renderer.domElement);
orbit.target.set(0, -0.13, 0.28);
orbit.update();
orbit.enabled = false;

scene.add(new THREE.HemisphereLight(0xe4ecff, 0x3b342c, 1.25));
const sun = new THREE.DirectionalLight(0xffffff, 1.7);
sun.position.set(-0.35, 0.8, -0.45);
scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.35);
fill.position.set(0.6, 0.1, 1);
scene.add(fill);

const freeOnly = new THREE.Group();
scene.add(freeOnly);
const grid = new THREE.GridHelper(2, 20, 0x59606c, 0x3a3f48);
grid.position.y = -0.62;
freeOnly.add(grid);
const camShape = new THREE.PerspectiveCamera(50, 16 / 9, 0.02, 0.16);
camShape.lookAt(0, 0, 1);
camShape.updateMatrixWorld();
freeOnly.add(new THREE.CameraHelper(camShape));

const gunGroup = new THREE.Group();
gunGroup.matrixAutoUpdate = false;
scene.add(gunGroup);
let weapon = null; // { root, parts: {nome: node} }
let arms = null; // { root, bones: {nome: {bone, bindQ, bindS}} }

const shell = new THREE.Group();
{
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.0105, 0.0105, 0.064 * 0.76, 14),
    new THREE.MeshLambertMaterial({ color: 0xb22e34 }));
  body.position.y = 0.064 * 0.24 + 0.064 * 0.76 / 2;
  const brass = new THREE.Mesh(new THREE.CylinderGeometry(0.0111, 0.0111, 0.064 * 0.24, 14),
    new THREE.MeshLambertMaterial({ color: 0xd6b05c }));
  brass.position.y = 0.064 * 0.12;
  shell.add(body, brass);
  shell.visible = false;
  scene.add(shell);
}

function lambertize(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    o.material = new THREE.MeshLambertMaterial({
      color: m.color ? m.color.clone() : 0xffffff, map: m.map || null, vertexColors: !!m.vertexColors,
      side: THREE.DoubleSide,
    });
    o.frustumCulled = false;
  });
}

function disposeTree(root) {
  root.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
  });
}

const loader = new GLTFLoader();
async function loadModels(hero) {
  if (weapon) { gunGroup.remove(weapon.root); disposeTree(weapon.root); weapon = null; }
  if (arms) { scene.remove(arms.root); disposeTree(arms.root); arms = null; }
  const [wg, ag] = await Promise.all([
    loader.loadAsync(`/assets/${hero}.glb`), loader.loadAsync(`/assets/${hero}_arms.glb`),
  ]);
  lambertize(wg.scene);
  // O GLTFLoader tira '.' dos nomes ('w_macrophage.pump' -> 'w_macrophagepump', 'hand.L' -> 'handL').
  const clean = (n) => THREE.PropertyBinding.sanitizeNodeName(n);
  const partOf = Object.fromEntries(S.info.parts.map((n) => [clean(`w_${hero}.${n}`), n]));
  const parts = {};
  wg.scene.traverse((o) => {
    const name = partOf[o.name];
    if (name && !parts[name]) {
      parts[name] = o;
      o.matrixAutoUpdate = false;
    }
  });
  gunGroup.add(wg.scene);
  weapon = { root: wg.scene, parts };

  lambertize(ag.scene);
  scene.add(ag.scene);
  ag.scene.updateMatrixWorld(true);
  const boneOf = Object.fromEntries(S.info.bones.map((n) => [clean(n), n]));
  const bones = {};
  ag.scene.traverse((o) => {
    if (!o.isBone) return;
    const p = new V3(), q = new Q(), s = new V3();
    o.matrixWorld.decompose(p, q, s);
    const name = boneOf[o.name] || o.name;
    bones[name] = { bone: o, name, bindQ: q, bindS: s };
  });
  // Ordem pai -> filho, para converter a pose global (do servidor) em matrizes locais.
  const order = [];
  const byObj = new Map(Object.values(bones).map((b) => [b.bone, b]));
  ag.scene.traverse((o) => { if (o.isBone) order.push(byObj.get(o)); });
  for (const b of order) {
    b.bone.matrixAutoUpdate = false;
    b.world = new M4();
    b.parent = byObj.get(b.bone.parent) || null;
  }
  arms = { root: ag.scene, bones, order };
}

// Guias: empunhaduras, caminhos das mãos, ombros e cotovelos.
const helperRoot = new THREE.Group();
scene.add(helperRoot);
let gripHelpers = {};
const pathLines = {};
const markerRoot = new THREE.Group();
helperRoot.add(markerRoot);
const armGuides = new THREE.Group();
helperRoot.add(armGuides);

for (const side of ['L', 'R']) {
  const line = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({
    color: SIDE_COLOR[side], transparent: true, opacity: 0.55, depthTest: false,
  }));
  line.renderOrder = 5;
  line.frustumCulled = false;
  pathLines[side] = line;
  helperRoot.add(line);
}

function rebuildGripHelpers() {
  for (const h of Object.values(gripHelpers)) { helperRoot.remove(h); disposeTree(h); }
  gripHelpers = {};
  if (!S.anim) return;
  for (const name of Object.keys(S.anim.grips)) {
    const g = new THREE.Group();
    g.matrixAutoUpdate = false;
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 20, 1, true),
      new THREE.MeshBasicMaterial({ color: 0x9fd3ff, wireframe: true, transparent: true, opacity: 0.35, depthTest: false }));
    cyl.renderOrder = 4;
    const palm = new THREE.ArrowHelper(new V3(1, 0, 0), new V3(), 0.035, 0xff6bcb, 0.01, 0.007);
    const axis = new THREE.ArrowHelper(new V3(0, 1, 0), new V3(), 0.045, 0x7dff8a, 0.01, 0.007);
    for (const a of [palm, axis]) a.traverse((o) => { if (o.material) { o.material.depthTest = false; o.renderOrder = 6; } });
    g.add(cyl, palm, axis);
    g.userData = { cyl, palm, axis };
    helperRoot.add(g);
    gripHelpers[name] = g;
  }
}

function spaceMatrix(f, part) {
  const g = m4(f.gun);
  return part && f.parts[part] ? g.multiply(m4(f.parts[part])) : g;
}

function gripBasis(g) {
  const ax = new V3(...g.axis).normalize();
  const pm = new V3(...g.palm);
  pm.sub(ax.clone().multiplyScalar(pm.dot(ax))).normalize();
  const z = new V3().crossVectors(pm, ax);
  return new M4().makeBasis(pm, ax, z).setPosition(g.c[0], g.c[1], g.c[2]);
}

function updateGripHelpers() {
  const f = S.cur;
  for (const [name, h] of Object.entries(gripHelpers)) {
    const g = S.anim.grips[name];
    const selected = S.sel.kind === 'grip' && S.sel.name === name;
    h.visible = !!(g && f);
    if (!h.visible) continue;
    h.matrix.copy(spaceMatrix(f, g.part)).multiply(gripBasis(g));
    h.matrixWorldNeedsUpdate = true;
    const [rp, rw] = radii(g);
    h.userData.cyl.scale.set(rp, 0.07, rw);
    h.userData.cyl.material.color.set(selected ? 0xffb347 : 0x9fd3ff);
    h.userData.cyl.material.opacity = selected ? 0.8 : 0.18;
    h.userData.palm.visible = h.userData.axis.visible = selected;
  }
}

function updatePaths() {
  if (!S.baked) return;
  for (const side of ['L', 'R']) {
    const pts = S.baked.map((f) => { const b = f.bones['hand.' + side]; return new V3(b[0], b[1], b[2]); });
    pathLines[side].geometry.dispose();
    pathLines[side].geometry = new THREE.BufferGeometry().setFromPoints(pts);
  }
  updateMarkers();
}

const markerGeo = new THREE.SphereGeometry(1, 10, 8);
function updateMarkers() {
  for (const c of [...markerRoot.children]) { markerRoot.remove(c); c.material.dispose(); }
  if (!S.baked || !S.anim) return;
  for (const side of ['L', 'R']) {
    S.anim.tracks[side].forEach((k, i) => {
      const f = S.baked[clamp(Math.round(k.t * SAMPLES), 0, SAMPLES)];
      const b = f.bones['hand.' + side];
      const sel = S.sel.kind === 'key' && S.sel.side === side && S.sel.i === i;
      const m = new THREE.Mesh(markerGeo, new THREE.MeshBasicMaterial({
        color: sel ? 0xffffff : SIDE_COLOR[side], depthTest: false, transparent: true, opacity: sel ? 1 : 0.8,
      }));
      m.renderOrder = 7;
      m.scale.setScalar(sel ? 0.006 : 0.0035);
      m.position.set(b[0], b[1], b[2]);
      markerRoot.add(m);
    });
  }
}

function updateArmGuides() {
  for (const c of [...armGuides.children]) { armGuides.remove(c); disposeTree(c); }
  const f = S.cur;
  if (!f || !S.anim) return;
  for (const side of ['L', 'R']) {
    const target = S.anim.shoulders[side];
    const tgt = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 8),
      new THREE.MeshBasicMaterial({ color: SIDE_COLOR[side], wireframe: true }));
    tgt.position.set(...target);
    const up = f.bones['upperarm.' + side], fo = f.bones['forearm.' + side];
    const real = new THREE.Mesh(new THREE.SphereGeometry(0.007, 10, 8), new THREE.MeshBasicMaterial({ color: SIDE_COLOR[side] }));
    real.position.set(up[0], up[1], up[2]);
    const pole = new THREE.ArrowHelper(new V3(...S.anim.poles[side]).normalize(), new V3(fo[0], fo[1], fo[2]), 0.08,
      SIDE_COLOR[side], 0.015, 0.01);
    armGuides.add(tgt, real, pole);
  }
}

function applyFrame(f) {
  if (!f || !weapon || !arms) return;
  S.cur = f;
  gunGroup.matrix.copy(m4(f.gun));
  gunGroup.matrixWorldNeedsUpdate = true;
  for (const [name, node] of Object.entries(weapon.parts)) {
    node.matrix.copy(m4(f.parts[name] || ID12));
    node.matrixWorldNeedsUpdate = true;
  }
  const pos = new V3(), q = new Q(), dq = new Q(), inv = new M4();
  arms.root.updateMatrixWorld(true);
  for (const b of arms.order) {
    const v = f.bones[b.name];
    if (v) {
      pos.set(v[0], v[1], v[2]);
      dq.set(v[3], v[4], v[5], v[6]);
      q.multiplyQuaternions(dq, b.bindQ);
      b.world.compose(pos, q, b.bindS);
    } else b.world.copy(b.parent ? b.parent.world : b.bone.parent.matrixWorld).multiply(b.bone.matrix);
    inv.copy(b.parent ? b.parent.world : b.bone.parent.matrixWorld).invert();
    b.bone.matrix.multiplyMatrices(inv, b.world);
    b.bone.matrixWorldNeedsUpdate = true;
  }
  if (f.shell) {
    shell.visible = true;
    shell.position.set(...f.shell[0]);
    shell.quaternion.setFromUnitVectors(new V3(0, 1, 0), new V3(...f.shell[1]).normalize());
  } else shell.visible = false;
  updateGripHelpers();
  if (S.freeCam) updateArmGuides();
  syncProxy();
  refreshFields();
}

function mixFrames(a, b, t) {
  const lerpA = (x, y) => x.map((v, i) => v + (y[i] - v) * t);
  const out = { p: a.p + (b.p - a.p) * t, gun: lerpA(a.gun, b.gun), parts: {}, bones: {}, shell: t < 0.5 ? a.shell : b.shell,
    wrist: t < 0.5 ? a.wrist : b.wrist };
  for (const k of new Set([...Object.keys(a.parts), ...Object.keys(b.parts)])) {
    out.parts[k] = lerpA(a.parts[k] || ID12, b.parts[k] || ID12);
  }
  for (const [k, va] of Object.entries(a.bones)) {
    const vb = b.bones[k];
    const s = va[3] * vb[3] + va[4] * vb[4] + va[5] * vb[5] + va[6] * vb[6] < 0 ? -1 : 1;
    const v = va.map((x, i) => x + ((i >= 3 ? vb[i] * s : vb[i]) - x) * t);
    const n = Math.hypot(v[3], v[4], v[5], v[6]) || 1;
    for (let i = 3; i < 7; i++) v[i] /= n;
    out.bones[k] = v;
  }
  return out;
}

function sampleBaked(p) {
  if (!S.baked) return null;
  const x = clamp(p, 0, 1) * SAMPLES;
  const i = Math.min(SAMPLES - 1, Math.floor(x));
  return mixFrames(S.baked[i], S.baked[i + 1], x - i);
}

// Gizmo (mover/girar) num objeto auxiliar; a edição volta para o JSON.
const proxy = new THREE.Object3D();
scene.add(proxy);
const tc = new TransformControls(gameCam, renderer.domElement);
tc.setSize(0.8);
scene.add(tc);
let D = null;
tc.addEventListener('dragging-changed', (e) => {
  orbit.enabled = S.freeCam && !e.value;
  if (e.value) dragStart();
  else dragEnd();
});
tc.addEventListener('objectChange', () => { if (S.dragging) onGizmo(); });

function curKey() {
  return S.sel.kind === 'key' ? S.anim.tracks[S.sel.side][S.sel.i] : null;
}

function gizmoInfo() {
  const f = S.cur, sel = S.sel;
  if (!f || !S.anim || S.playing) return null;
  if (sel.kind === 'key') {
    const k = curKey();
    if (!k || !f.exact) return null;
    const atKey = f.p === null ? sel.i === 0 : Math.abs(f.p - k.t) < 1e-9;
    if (!atKey) return null;
    const b = f.bones['hand.' + sel.side];
    // Pulso: o gizmo representa o antebraço (no punho, com a orientação do osso do antebraço).
    const o = S.gizmo === 'wrist' ? f.bones['forearm.' + sel.side] : b;
    const quat = new Q(o[3], o[4], o[5], o[6]);
    return { pos: new V3(b[0], b[1], b[2]), quat, rotate: true };
  }
  if (sel.kind === 'grip') {
    const g = S.anim.grips[sel.name];
    if (!g) return null;
    const m = spaceMatrix(f, g.part).multiply(gripBasis(g));
    const pos = new V3(), quat = new Q(), sc = new V3();
    m.decompose(pos, quat, sc);
    return { pos, quat, rotate: true };
  }
  if (sel.kind === 'shoulder') return { pos: new V3(...S.anim.shoulders[sel.side]), quat: new Q(), rotate: false };
  return null;
}

// Pulso: [flexão, desvio] em graus, dentro dos limites do servidor (fp_arms.WRIST_X/WRIST_Y).
// Desvio + = lado do polegar nas duas mãos (o eixo Y da esquerda é espelhado).
function wristSign(side) { return S.info.hands[side].thumb[0] > 0 ? 1 : -1; }
function clampWrist(w) {
  const L = S.info.wrist_limits;
  return [rnd(clamp(w[0], L.x[0], L.x[1]), 2), rnd(clamp(w[1], L.y[0], L.y[1]), 2)];
}
function wristFromDir(d, side) {
  const a = Math.asin(clamp(d.y, -1, 1)) * DEG;
  const b = Math.atan2(-d.x, d.z) * DEG * wristSign(side);
  return clampWrist([a, b]);
}

function eulerQ(r) {
  r = r || [0, 0, 0];
  return new Q().setFromEuler(new THREE.Euler(r[0] / DEG, r[1] / DEG, r[2] / DEG, 'XYZ'));
}

function syncProxy() {
  if (S.dragging) return;
  const info = gizmoInfo();
  if (!info) { tc.detach(); updateHint(); return; }
  proxy.position.copy(info.pos);
  proxy.quaternion.copy(info.quat);
  proxy.updateMatrixWorld();
  const mode = info.rotate ? (S.gizmo === 'wrist' ? 'rotate' : S.gizmo) : 'translate';
  tc.setMode(mode);
  tc.setSpace(mode === 'rotate' ? 'local' : 'world');
  if (tc.object !== proxy) tc.attach(proxy);
  updateHint();
}

function updateHint() {
  let msg = '';
  if (S.sel.kind === 'key' && !tc.object) {
    msg = S.playing ? '' : 'Gizmo da mão: leve o cursor do tempo até a chave (clique nela na linha do tempo).';
  } else if (tc.object) {
    msg = S.sel.kind === 'key' ? (S.gizmo === 'wrist'
      ? 'Pulso: gire o antebraço em volta do punho (anel vermelho = flexão, verde = desvio); a mão fica onde está (R).'
      : `Arraste o gizmo para ajustar a mão nesta chave (${S.gizmo === 'rotate' ? 'girar mão: E' : 'mover: W'}).`)
      : S.sel.kind === 'grip' ? 'Gizmo da empunhadura: muda TODAS as chaves que a usam.' : 'Arraste o ombro.';
  } else if (!S.cur) msg = '';
  else msg = 'Clique numa mão para selecionar a chave dela · F alterna a câmera';
  $('#viewhint').textContent = msg;
}

function dragStart() {
  S.dragging = true;
  const f = S.cur, sel = S.sel;
  D = { pos0: proxy.position.clone(), q0: proxy.quaternion.clone() };
  if (sel.kind === 'key') {
    const k = curKey();
    D.off0 = (k.offset || [0, 0, 0]).slice();
    D.offQ0 = eulerQ(k.rot);
    const h = f.bones['hand.' + sel.side];
    D.handQ = new Q(h[3], h[4], h[5], h[6]);
    D.gunInv = new M3().setFromMatrix4(m4(f.gun)).invert();
  } else if (sel.kind === 'grip') {
    const g = S.anim.grips[sel.name];
    D.c0 = g.c.slice(); D.axis0 = g.axis.slice(); D.palm0 = g.palm.slice();
    D.sp3 = new M3().setFromMatrix4(spaceMatrix(f, g.part));
    D.spInv = D.sp3.clone().invert();
  }
}

function onGizmo() {
  const sel = S.sel;
  const d = proxy.position.clone().sub(D.pos0);
  if (sel.kind === 'key') {
    const k = curKey();
    if (tc.mode === 'translate') {
      const g = d.applyMatrix3(D.gunInv);
      k.offset = [rnd(D.off0[0] + g.x, 5), rnd(D.off0[1] + g.y, 5), rnd(D.off0[2] + g.z, 5)];
    } else if (S.gizmo === 'wrist') {
      // Direção do antebraço nos eixos da mão -> (flexão, desvio). A torção do antebraço não conta:
      // ela segue a mão.
      const d = new V3(0, 0, 1).applyQuaternion(proxy.quaternion).applyQuaternion(D.handQ.clone().invert());
      k.wrist = wristFromDir(d, sel.side);
    } else {
      const place = D.q0.clone().multiply(D.offQ0.clone().invert());
      const off = place.invert().multiply(proxy.quaternion);
      const e = new THREE.Euler().setFromQuaternion(off, 'XYZ');
      k.rot = [rnd(e.x * DEG, 2), rnd(e.y * DEG, 2), rnd(e.z * DEG, 2)];
    }
  } else if (sel.kind === 'grip') {
    const g = S.anim.grips[sel.name];
    if (tc.mode === 'translate') {
      const l = d.applyMatrix3(D.spInv);
      g.c = [rnd(D.c0[0] + l.x, 5), rnd(D.c0[1] + l.y, 5), rnd(D.c0[2] + l.z, 5)];
    } else {
      const dq = proxy.quaternion.clone().multiply(D.q0.clone().invert());
      const turn = (v0) => {
        const v = new V3(...v0).applyMatrix3(D.sp3).applyQuaternion(dq).applyMatrix3(D.spInv).normalize();
        return [rnd(v.x, 5), rnd(v.y, 5), rnd(v.z, 5)];
      };
      g.axis = turn(D.axis0);
      g.palm = turn(D.palm0);
    }
  } else if (sel.kind === 'shoulder') {
    S.anim.shoulders[sel.side] = [rnd(proxy.position.x, 4), rnd(proxy.position.y, 4), rnd(proxy.position.z, 4)];
  }
  edited();
}

function dragEnd() {
  S.dragging = false;
  commit();
  scheduleBake(0);
}

// Clique na vista: seleciona a chave da mão mais próxima.
let downAt = null;
renderer.domElement.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4 || tc.axis || !S.cur) return;
  const rect = renderer.domElement.getBoundingClientRect();
  const cam = S.freeCam ? freeCam : gameCam;
  let best = null;
  for (const side of ['L', 'R']) {
    const b = S.cur.bones['hand.' + side];
    const v = new V3(b[0], b[1], b[2]).project(cam);
    const sx = rect.left + (v.x + 1) / 2 * rect.width, sy = rect.top + (1 - v.y) / 2 * rect.height;
    const dist = Math.hypot(sx - e.clientX, sy - e.clientY);
    if (v.z < 1 && dist < 90 && (!best || dist < best.dist)) best = { side, dist };
  }
  if (!best) return;
  const keys = S.anim.tracks[best.side];
  let i = keys.findIndex((k) => Math.abs(k.t - S.p) < 1e-9);
  if (i < 0) { i = 0; keys.forEach((k, j) => { if (k.t <= S.p) i = j; }); }
  select({ kind: 'key', side: best.side, i });
});

// ------------------------------------------------------------------------------------------
// Servidor: quadro exato (pausado) e "bake" da recarga inteira (tocar, caminhos)
// ------------------------------------------------------------------------------------------
let liveBusy = false, liveAgain = false;
function touchLive() {
  if (S.playing || !S.anim) return;
  if (liveBusy) { liveAgain = true; return; }
  doLive();
}
async function doLive() {
  liveBusy = true;
  const hero = S.hero, p = S.idle ? null : S.p;
  try {
    const res = await api('/api/bake', { hero, anim: S.anim, times: [p] });
    if (hero === S.hero) {
      if (res.ok) {
        const f = res.frames[0];
        f.exact = true;
        if (S.error) setError(null);
        if (!S.playing) applyFrame(f);
      } else setError(res.error);
    }
  } catch (err) {
    setError('sem resposta do servidor (a janela do editor foi fechada?) ' + err.message);
  }
  liveBusy = false;
  if (liveAgain) { liveAgain = false; doLive(); }
}

let bakeTimer = 0, bakeBusy = false, bakeAgain = false;
function scheduleBake(ms = 160) {
  clearTimeout(bakeTimer);
  bakeTimer = setTimeout(doBake, ms);
}
async function doBake() {
  if (bakeBusy) { bakeAgain = true; return; }
  bakeBusy = true;
  const hero = S.hero;
  try {
    const res = await api('/api/bake', { hero, anim: S.anim });
    if (hero === S.hero) {
      if (res.ok) {
        S.baked = res.frames;
        S.idleFrame = res.idle;
        S.solved = res.solved;
        updatePaths();
        if (S.error) setError(null);
      } else setError(res.error);
    }
  } catch (err) {
    setError('sem resposta do servidor ' + err.message);
  }
  bakeBusy = false;
  if (bakeAgain) { bakeAgain = false; doBake(); }
}

// ------------------------------------------------------------------------------------------
// Edição, desfazer e salvar
// ------------------------------------------------------------------------------------------
function edited() {
  S.version++;
  touchLive();
  scheduleBake();
  refreshFields();
  refreshStatus();
  drawTimeline();
}

function selectedObject() {
  const s = S.sel;
  if (s.kind === 'key') return S.anim.tracks[s.side][s.i];
  if (s.kind === 'curve') return S.anim.curves[s.name][s.i];
  if (s.kind === 'shell') return S.anim.shell[s.i];
  return null;
}

function normalize() {
  const obj = selectedObject();
  for (const side of ['L', 'R']) S.anim.tracks[side].sort((a, b) => a.t - b.t);
  for (const c of CURVES) S.anim.curves[c.name].sort((a, b) => a[0] - b[0]);
  S.anim.shell.sort((a, b) => a[0] - b[0]);
  if (obj) {
    const s = S.sel;
    const list = s.kind === 'key' ? S.anim.tracks[s.side] : s.kind === 'curve' ? S.anim.curves[s.name] : S.anim.shell;
    s.i = list.indexOf(obj);
  }
}

function commit() {
  normalize();
  const now = JSON.stringify(S.anim);
  if (now === S.committed) return;
  S.undo.push(S.committed);
  if (S.undo.length > 400) S.undo.shift();
  S.redo = [];
  S.committed = now;
  refreshStatus();
}

function restore(text) {
  S.anim = JSON.parse(text);
  S.committed = text;
  const s = S.sel;
  if (s.kind === 'key' && !S.anim.tracks[s.side][s.i]) S.sel = { kind: 'global' };
  if (s.kind === 'curve' && !S.anim.curves[s.name][s.i]) S.sel = { kind: 'global' };
  if (s.kind === 'shell' && !S.anim.shell[s.i]) S.sel = { kind: 'global' };
  if (s.kind === 'grip' && !S.anim.grips[s.name]) S.sel = { kind: 'global' };
  rebuildGripHelpers();
  renderInspector();
  edited();
  updateMarkers();
}
function undo() {
  commit();
  if (!S.undo.length) return;
  S.redo.push(S.committed);
  restore(S.undo.pop());
}
function redo() {
  if (!S.redo.length) return;
  S.undo.push(S.committed);
  restore(S.redo.pop());
}

async function save() {
  commit();
  const res = await api('/api/save', { hero: S.hero, anim: S.anim });
  if (res.ok) {
    S.saved = JSON.stringify(S.anim);
    S.error = null;
    status(`Salvo em ${res.path}. Com o jogo aberto, aparece na próxima recarga.`, 'ok');
  } else setError(res.error);
}

function ensureShape(a) {
  a.tracks = a.tracks || {};
  for (const side of ['L', 'R']) a.tracks[side] = a.tracks[side] || [];
  a.curves = a.curves || {};
  for (const c of CURVES) a.curves[c.name] = a.curves[c.name] || [[0, 0], [1, 0]];
  a.shell = a.shell || [];
  a.tilt = a.tilt || [0, 0, 0, 0, 0, 0];
  a.notes = a.notes || '';
  a.duration = a.duration || 1.6;
  return a;
}

function setAnim(anim, fresh) {
  S.anim = ensureShape(anim);
  const text = JSON.stringify(S.anim);
  if (fresh) { S.saved = text; S.undo = []; S.redo = []; }
  S.committed = text;
  S.sel = { kind: 'global' };
  S.error = null;
  rebuildGripHelpers();
  renderInspector();
  edited();
}

async function loadHero(hero) {
  setPlaying(false);
  S.hero = hero;
  S.info = S.infos[hero];
  S.baked = null;
  S.cur = null;
  tc.detach();
  status('carregando ' + hero + '…');
  location.hash = hero;
  const anim = await api('/api/anim?hero=' + encodeURIComponent(hero));
  if (anim.error) { setError(anim.error); return; }
  await loadModels(hero);
  setAnim(anim, true);
  await doBake();
  setP(0);
}

// ------------------------------------------------------------------------------------------
// Tempo / reprodução
// ------------------------------------------------------------------------------------------
function setPlaying(v) {
  S.playing = v;
  $('#play').textContent = v ? '❚❚ Pausar' : '▶ Tocar';
  if (v) { S.idle = false; $('#idle').classList.remove('on'); tc.detach(); }
  else touchLive();
  updateHint();
}

function setP(p) {
  S.p = clamp(p, 0, 1);
  S.idle = false;
  $('#idle').classList.remove('on');
  updateTime();
  drawTimeline();
  if (!S.playing) {
    const f = sampleBaked(S.p);
    if (f) applyFrame(f);
    touchLive();
  }
}

function updateTime() {
  $('#time').textContent = S.idle ? 'PARADO (fora da recarga)'
    : `t = ${S.p.toFixed(3)}  ·  ${(S.p * dur()).toFixed(3)} s / ${dur().toFixed(2)} s`;
}

let last = performance.now();
function tick(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (S.playing && S.baked) {
    S.p += dt * S.speed / dur();
    if (S.p >= 1) {
      if (S.loop) S.p %= 1;
      else { S.p = 1; setPlaying(false); }
    }
    applyFrame(sampleBaked(S.p));
    updateTime();
    drawTimeline();
  }
  resize();
  freeOnly.visible = S.freeCam;
  armGuides.visible = S.freeCam && S.helpers;
  helperRoot.visible = S.helpers;
  renderer.render(scene, S.freeCam ? freeCam : gameCam);
  requestAnimationFrame(tick);
}

let lastSize = '';
function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  const key = w + 'x' + h + S.freeCam;
  if (key === lastSize || !w || !h) return;
  lastSize = key;
  renderer.setSize(w, h);
  const aspect = w / h, A = 16 / 9;
  const fr = $('#frame16');
  gameCam.aspect = freeCam.aspect = aspect;
  let fw, fh;
  if (aspect >= A) { gameCam.fov = 50; fh = h; fw = h * A; }
  else { gameCam.fov = 2 * Math.atan(Math.tan(25 / DEG) * A / aspect) * DEG; fw = w; fh = w / A; }
  gameCam.updateProjectionMatrix();
  freeCam.updateProjectionMatrix();
  Object.assign(fr.style, { left: (w - fw) / 2 + 'px', top: (h - fh) / 2 + 'px', width: fw + 'px', height: fh + 'px' });
  fr.style.display = S.freeCam ? 'none' : 'block';
  drawTimeline();
}

// ------------------------------------------------------------------------------------------
// Linha do tempo
// ------------------------------------------------------------------------------------------
const tl = $('#tl'), tctx = tl.getContext('2d');
const TL = { labelW: 150, pad: 14, lanes: [], drag: null, W: 0 };

function buildLanes() {
  const out = [{ id: 'ruler', h: 24 },
    { id: 'hand', side: 'L', label: SIDE_PT.L, h: 40 }, { id: 'hand', side: 'R', label: SIDE_PT.R, h: 32 },
    { id: 'shell', label: 'Cartucho na mão', h: 22 }];
  for (const c of curvesFor()) out.push({ id: 'curve', label: c.label, h: 36, curve: c });
  let y = 0;
  for (const l of out) { l.y = y; y += l.h; }
  return out;
}
const tx = (t) => TL.labelW + TL.pad + t * (TL.W - TL.labelW - 2 * TL.pad);
const tFromX = (x) => clamp((x - TL.labelW - TL.pad) / (TL.W - TL.labelW - 2 * TL.pad), 0, 1);
const snapT = (t, fine) => rnd(fine ? Math.round(t * 100) / 100 : Math.round(t * 1000) / 1000, 4);

function curveRange(pts, name) {
  let lo = 0, hi = 0;
  for (const [, v] of pts) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  if (name === 'tilt' || name === 'bolt') hi = Math.max(hi, 1);
  if (hi - lo < 1e-6) hi = lo + (name === 'bump' ? 0.01 : 1);
  return [lo, hi];
}

function drawTimeline() {
  if (!S.anim) return;
  const dpr = devicePixelRatio || 1;
  const W = tl.clientWidth, H = tl.clientHeight;
  if (tl.width !== Math.round(W * dpr) || tl.height !== Math.round(H * dpr)) {
    tl.width = Math.round(W * dpr);
    tl.height = Math.round(H * dpr);
  }
  const c = tctx;
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, W, H);
  TL.W = W;
  TL.lanes = buildLanes();
  const last = TL.lanes[TL.lanes.length - 1];
  if (Math.abs(tl.clientHeight - (last.y + last.h)) > 1) { tl.style.height = last.y + last.h + 'px'; lastSize = ''; }
  c.font = '12px Segoe UI, sans-serif';
  c.textBaseline = 'middle';
  TL.lanes.forEach((l, i) => {
    c.fillStyle = i % 2 ? '#1c1f24' : '#202329';
    c.fillRect(0, l.y, W, l.h);
    if (l.label) {
      c.fillStyle = l.side ? SIDE_COLOR[l.side] : '#8a92a0';
      c.fillText(l.label, 10, l.y + l.h / 2);
    }
  });
  c.fillStyle = '#2b2f37';
  c.fillRect(TL.labelW - 1, 0, 1, H);

  // Régua.
  const ruler = TL.lanes[0];
  for (let i = 0; i <= 100; i++) {
    const x = tx(i / 100);
    const big = i % 10 === 0, mid = i % 5 === 0;
    c.fillStyle = big ? '#7d8592' : mid ? '#565d69' : '#3a3f48';
    c.fillRect(Math.round(x), ruler.y + (big ? 2 : mid ? 12 : 17), 1, ruler.h - (big ? 2 : mid ? 12 : 17));
    if (big) {
      c.fillStyle = '#aab2bf';
      c.font = '11px Segoe UI, sans-serif';
      c.fillText(`${(i / 100).toFixed(1)} · ${(i / 100 * dur()).toFixed(2)}s`, x + 3, ruler.y + 8);
    }
    if (big) { c.fillStyle = 'rgba(255,255,255,.035)'; c.fillRect(Math.round(x), ruler.y + ruler.h, 1, H); }
  }
  c.font = '12px Segoe UI, sans-serif';

  for (const l of TL.lanes) {
    const mid = l.y + l.h / 2;
    if (l.id === 'hand') {
      const keys = S.anim.tracks[l.side];
      for (let i = 0; i + 1 < keys.length; i++) {
        const a = keys[i], b = keys[i + 1];
        const x0 = tx(a.t), x1 = tx(b.t);
        if (samePose(a, b)) { c.fillStyle = '#4a505b'; c.fillRect(x0, mid - 1, x1 - x0, 2); }
        else {
          c.fillStyle = SIDE_COLOR[l.side] + '55';
          c.fillRect(x0, mid - 5, x1 - x0, 10);
          if (b.arc) { c.fillStyle = SIDE_COLOR[l.side] + 'aa'; c.fillRect(x0, mid - 7, x1 - x0, 2); }
        }
      }
      keys.forEach((k, i) => {
        const x = tx(k.t);
        const sel = S.sel.kind === 'key' && S.sel.side === l.side && S.sel.i === i;
        const r = sel ? 8 : 6;
        c.beginPath();
        c.moveTo(x, mid - r); c.lineTo(x + r, mid); c.lineTo(x, mid + r); c.lineTo(x - r, mid); c.closePath();
        c.fillStyle = sel ? '#ffffff' : SIDE_COLOR[l.side];
        c.fill();
        if (nz(k.offset) || nz(k.rot) || k.wrist || (k.fingers && Object.keys(k.fingers).length)) {
          c.fillStyle = '#ff5ec4';
          c.fillRect(x - 2, mid - 2, 4, 4);
        }
        c.fillStyle = sel ? '#ffffff' : '#c9ced6';
        c.font = '10px Segoe UI, sans-serif';
        c.fillText(k.grip, x + 2, i % 2 ? mid + 13 : mid - 13);
        c.font = '12px Segoe UI, sans-serif';
      });
    } else if (l.id === 'shell') {
      S.anim.shell.forEach((w, i) => {
        const sel = S.sel.kind === 'shell' && S.sel.i === i;
        c.fillStyle = sel ? '#e05a5e' : '#9b3a3e';
        c.fillRect(tx(w[0]), l.y + 4, tx(w[1]) - tx(w[0]), l.h - 8);
      });
    } else if (l.id === 'curve') {
      const name = l.curve.name;
      const pts = S.anim.curves[name];
      const [lo, hi] = TL.drag && TL.drag.range && TL.drag.name === name ? TL.drag.range : curveRange(pts, name);
      const vy = (v) => l.y + l.h - 5 - (v - lo) / (hi - lo) * (l.h - 10);
      if (lo < 0) { c.fillStyle = '#3a3f48'; c.fillRect(tx(0), vy(0), tx(1) - tx(0), 1); }
      c.strokeStyle = '#4fb3ff';
      c.lineWidth = 1.5;
      c.beginPath();
      for (let i = 0; i <= 300; i++) {
        const t = i / 300, x = tx(t), y = vy(curveAt(pts, t));
        if (i) c.lineTo(x, y); else c.moveTo(x, y);
      }
      c.stroke();
      pts.forEach((pt, i) => {
        const sel = S.sel.kind === 'curve' && S.sel.name === name && S.sel.i === i;
        c.fillStyle = sel ? '#ffffff' : '#9fd3ff';
        c.beginPath();
        c.arc(tx(pt[0]), vy(pt[1]), sel ? 5 : 3.5, 0, Math.PI * 2);
        c.fill();
      });
      c.fillStyle = '#5d6572';
      c.font = '10px Segoe UI, sans-serif';
      c.fillText(`máx ${+hi.toFixed(4)}`, 10, l.y + l.h - 7);
      c.font = '12px Segoe UI, sans-serif';
    }
  }

  // Cursor.
  if (!S.idle) {
    const x = Math.round(tx(S.p));
    c.fillStyle = '#ff4d4d';
    c.fillRect(x, 0, 1.5, H);
    c.beginPath();
    c.moveTo(x - 6, 0); c.lineTo(x + 7, 0); c.lineTo(x + 0.5, 8); c.closePath();
    c.fill();
  } else {
    c.fillStyle = '#ffcc66';
    c.fillText('PARADO — mostrando a primeira chave de cada mão', TL.labelW + 20, 12);
  }
}

function hitLane(y) { return TL.lanes.find((l) => y >= l.y && y < l.y + l.h); }
function localXY(e) { const r = tl.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }

function nearestIndex(xs, x, tol = 8) {
  let best = -1, bd = tol;
  xs.forEach((v, i) => { const d = Math.abs(v - x); if (d <= bd) { bd = d; best = i; } });
  return best;
}

tl.addEventListener('pointerdown', (e) => {
  if (!S.anim) return;
  const [x, y] = localXY(e);
  const lane = hitLane(y);
  if (!lane || x < TL.labelW) return;
  tl.setPointerCapture(e.pointerId);
  setPlaying(false);
  if (lane.id === 'hand') {
    const keys = S.anim.tracks[lane.side];
    const i = nearestIndex(keys.map((k) => tx(k.t)), x);
    if (i >= 0) {
      select({ kind: 'key', side: lane.side, i });
      TL.drag = { type: 'key', obj: keys[i], x0: x, moved: false };
      return;
    }
  } else if (lane.id === 'shell') {
    for (let i = 0; i < S.anim.shell.length; i++) {
      const w = S.anim.shell[i];
      const x0 = tx(w[0]), x1 = tx(w[1]);
      if (Math.abs(x - x0) < 6 || Math.abs(x - x1) < 6 || (x > x0 && x < x1)) {
        const edge = Math.abs(x - x0) < 6 ? 0 : Math.abs(x - x1) < 6 ? 1 : -1;
        select({ kind: 'shell', i });
        TL.drag = { type: 'shell', obj: w, edge, t0: tFromX(x), w0: w.slice() };
        return;
      }
    }
  } else if (lane.id === 'curve') {
    const name = lane.curve.name, pts = S.anim.curves[name];
    const i = nearestIndex(pts.map((p) => tx(p[0])), x);
    if (i >= 0) {
      select({ kind: 'curve', name, i });
      TL.drag = { type: 'curve', obj: pts[i], name, lane, range: curveRange(pts, name) };
      return;
    }
  }
  TL.drag = { type: 'scrub' };
  setP(tFromX(x));
});

tl.addEventListener('pointermove', (e) => {
  const d = TL.drag;
  const [x, y] = localXY(e);
  if (!d) {
    const lane = hitLane(y);
    tl.style.cursor = lane && lane.id === 'ruler' ? 'ew-resize' : 'default';
    return;
  }
  const t = tFromX(x);
  if (d.type === 'scrub') setP(t);
  else if (d.type === 'key') {
    if (!d.moved && Math.abs(x - d.x0) < 3) return;
    d.moved = true;
    d.obj.t = snapT(t, e.ctrlKey);
    S.p = d.obj.t;
    updateTime();
    edited();
  } else if (d.type === 'curve') {
    const l = d.lane, [lo, hi] = d.range;
    d.obj[0] = snapT(t, e.ctrlKey);
    const v = lo + (l.y + l.h - 5 - y) / (l.h - 10) * (hi - lo);
    d.obj[1] = rnd(e.shiftKey ? d.obj[1] : clamp(v, lo - (hi - lo), hi + (hi - lo)), d.name === 'bump' ? 5 : 3);
    S.p = d.obj[0];
    updateTime();
    edited();
  } else if (d.type === 'shell') {
    const dt = t - d.t0;
    if (d.edge === 0) d.obj[0] = snapT(Math.min(t, d.obj[1] - 0.005), e.ctrlKey);
    else if (d.edge === 1) d.obj[1] = snapT(Math.max(t, d.obj[0] + 0.005), e.ctrlKey);
    else {
      const len = d.w0[1] - d.w0[0];
      d.obj[0] = snapT(clamp(d.w0[0] + dt, 0, 1 - len), e.ctrlKey);
      d.obj[1] = rnd(d.obj[0] + len, 4);
    }
    edited();
  }
});

function endTlDrag() {
  if (!TL.drag) return;
  const type = TL.drag.type;
  TL.drag = null;
  if (type !== 'scrub') {
    commit();
    renderInspector();
    updateMarkers();
    drawTimeline();
    touchLive();
  }
}
tl.addEventListener('pointerup', endTlDrag);
tl.addEventListener('pointercancel', endTlDrag);

tl.addEventListener('dblclick', (e) => {
  if (!S.anim) return;
  const [x, y] = localXY(e);
  const lane = hitLane(y);
  if (!lane || x < TL.labelW) return;
  const t = snapT(tFromX(x), e.ctrlKey);
  if (lane.id === 'hand') {
    const keys = S.anim.tracks[lane.side];
    if (keys.some((k) => Math.abs(tx(k.t) - x) < 8)) return;
    let prev = keys[0];
    for (const k of keys) if (k.t <= t) prev = k;
    const k = JSON.parse(JSON.stringify(prev));
    k.t = t;
    delete k.arc;
    delete k.ease;
    keys.push(k);
    commit();
    select({ kind: 'key', side: lane.side, i: keys.indexOf(k) });
  } else if (lane.id === 'curve') {
    const pts = S.anim.curves[lane.curve.name];
    const pt = [t, rnd(curveAt(pts, t), 5)];
    pts.push(pt);
    commit();
    select({ kind: 'curve', name: lane.curve.name, i: pts.indexOf(pt) });
  } else if (lane.id === 'shell') {
    const w = [t, rnd(Math.min(1, t + 0.1), 4)];
    S.anim.shell.push(w);
    commit();
    select({ kind: 'shell', i: S.anim.shell.indexOf(w) });
  }
  edited();
});

// ------------------------------------------------------------------------------------------
// Painel lateral
// ------------------------------------------------------------------------------------------
let FIELDS = [];
function refreshFields() { FIELDS.forEach((f) => f()); }

function num(get, set, { step = 0.001, digits = 4, min = -Infinity, max = Infinity } = {}) {
  const inp = el('input', { type: 'text', class: 'num', title: 'Arraste para os lados ou digite' });
  const fmt = (v) => (v == null || Number.isNaN(+v) ? '' : (+v).toFixed(digits));
  const put = (v) => { set(rnd(clamp(v, min, max), digits)); edited(); };
  inp.value = fmt(get());
  let sx = 0, sv = 0, down = false, moving = false;
  inp.addEventListener('pointerdown', (e) => {
    if (document.activeElement === inp) return;
    down = true; moving = false; sx = e.clientX; sv = +get() || 0;
    inp.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  inp.addEventListener('pointermove', (e) => {
    if (!down) return;
    const dx = e.clientX - sx;
    if (!moving && Math.abs(dx) < 3) return;
    moving = true;
    put(sv + dx * step * (e.shiftKey ? 0.1 : e.ctrlKey ? 10 : 1));
    inp.value = fmt(get());
  });
  inp.addEventListener('pointerup', () => {
    if (!down) return;
    down = false;
    if (moving) commit();
    else { inp.focus(); inp.select(); }
  });
  inp.addEventListener('change', () => {
    const v = parseFloat(inp.value.replace(',', '.'));
    if (!Number.isNaN(v)) { put(v); commit(); }
    inp.value = fmt(get());
  });
  inp.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') inp.blur();
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      put((+get() || 0) + (e.key === 'ArrowUp' ? 1 : -1) * step * 10 * (e.shiftKey ? 0.1 : 1));
      inp.value = fmt(get());
      commit();
    }
  });
  FIELDS.push(() => { if (document.activeElement !== inp) inp.value = fmt(get()); });
  return inp;
}

function vecRow(label, getArr, setArr, opts = {}, n = 3, names = 'XYZ') {
  const row = el('div', { class: 'row' }, el('label', {}, label));
  for (let i = 0; i < n; i++) {
    row.append(el('span', { class: 'axis' }, names[i] || ''), num(() => (getArr() || [])[i] ?? 0, (v) => {
      const a = (getArr() || Array(n).fill(0)).slice();
      a[i] = v;
      setArr(a);
    }, opts));
  }
  return row;
}

function row(label, ...kids) { return el('div', { class: 'row' }, el('label', {}, label), ...kids); }
function hint(text) { return el('div', { class: 'hint' }, text); }
function btn(text, onclick, cls = '') { return el('button', { class: cls, onclick }, text); }

function selectBox(options, value, onchange) {
  const s = el('select', { onchange: (e) => onchange(e.target.value) });
  for (const [v, label] of options) s.append(el('option', { value: v, selected: v === value }, label));
  s.value = value;
  return s;
}

function fingerEditor({ get, set, defaults, title }) {
  const box = el('div');
  for (const f of FINGERS) {
    const n = f === 'thumb' ? 4 : 3;
    const labels = f === 'thumb' ? THUMB : PHAL;
    const cur = () => (get() || {})[f];
    const manual = !!cur();
    const wrap = el('div', { class: 'finger' + (manual ? ' manual' : '') });
    const auto = defaults(f);
    const head = el('div', { class: 'fhead' },
      el('b', {}, FINGER_PT[f]),
      el('label', {}, el('input', {
        type: 'checkbox', checked: manual,
        onchange: (e) => {
          const d = { ...(get() || {}) };
          if (e.target.checked) d[f] = (defaults(f) || Array(n).fill(0)).map((v) => rnd(v, 2));
          else delete d[f];
          set(d);
          edited();
          commit();
          renderInspector();
        },
      }), ' ' + title),
      !manual && auto ? el('span', { class: 'muted', style: 'font-size:11px' }, 'auto: ' + auto.map((v) => v.toFixed(0) + '°').join(' ')) : null);
    wrap.append(head);
    if (manual) {
      for (let j = 0; j < n; j++) {
        const getV = () => (cur() || [])[j] ?? 0;
        const setV = (v) => { const d = { ...(get() || {}) }; d[f] = (d[f] || Array(n).fill(0)).slice(); d[f][j] = v; set(d); };
        const range = el('input', {
          type: 'range', min: -45, max: 120, step: 0.5, value: getV(),
          oninput: (e) => { setV(+e.target.value); edited(); }, onchange: () => commit(),
        });
        FIELDS.push(() => { if (document.activeElement !== range) range.value = getV(); });
        wrap.append(el('div', { class: 'row' }, el('label', {}, labels[j]), range, num(getV, setV, { step: 0.5, digits: 1 }), '°'));
      }
    }
    box.append(wrap);
  }
  return box;
}

function navTop() {
  const chips = el('div', { class: 'chips' },
    el('button', { class: S.sel.kind === 'global' || S.sel.kind === 'shoulder' ? 'on' : '', onclick: () => select({ kind: 'global' }) }, 'Geral'));
  for (const name of Object.keys(S.anim.grips)) {
    chips.append(el('button', {
      class: S.sel.kind === 'grip' && S.sel.name === name ? 'on' : '', title: 'Editar a empunhadura ' + name,
      onclick: () => select({ kind: 'grip', name }),
    }, '✋ ' + name));
  }
  return el('div', {}, chips, el('div', { class: 'hint', style: 'margin-top:4px' }, 'Empunhaduras (clique para editar)'));
}

function renderInspector() {
  FIELDS = [];
  const side = $('#side');
  side.innerHTML = '';
  if (!S.anim) return;
  side.append(navTop(), el('hr', { style: 'border:0;border-top:1px solid #343944;margin:10px 0' }));
  const s = S.sel;
  if (s.kind === 'key') side.append(keyPanel(s.side, s.i));
  else if (s.kind === 'grip') side.append(gripPanel(s.name));
  else if (s.kind === 'curve') side.append(curvePanel(s.name, s.i));
  else if (s.kind === 'shell') side.append(shellPanel(s.i));
  else side.append(globalPanel());
}

function solvedFor(side, grip, finger) {
  const s = S.solved && S.solved[side] && S.solved[side][grip];
  return s ? s[finger] : null;
}

function keyPanel(side, i) {
  const keys = S.anim.tracks[side];
  const k = keys[i];
  const p = el('div');
  const gripOpts = Object.keys(S.anim.grips).map((g) => [g, g]);
  p.append(el('h2', { style: `color:${SIDE_COLOR[side]}` }, `${SIDE_PT[side]} · chave ${i + 1} de ${keys.length}`),
    el('div', { class: 'btns', style: 'margin-top:0' },
      btn('◀ anterior', () => select({ kind: 'key', side, i: Math.max(0, i - 1) })),
      btn('próxima ▶', () => select({ kind: 'key', side, i: Math.min(keys.length - 1, i + 1) }))),
    hint(i === 0 ? 'Primeira chave = pose PARADA desta mão (fora da recarga) e início da recarga.'
      : 'A mão vai da chave anterior até esta. Se a empunhadura e o ajuste forem iguais, ela fica parada.'));
  const secs = el('span', { class: 'muted' });
  FIELDS.push(() => { secs.textContent = `${(k.t * dur()).toFixed(3)} s`; });
  p.append(row('Tempo (0 a 1)', num(() => k.t, (v) => { k.t = v; S.p = v; updateTime(); }, { step: 0.001, digits: 3, min: 0, max: 1 }), secs));
  p.append(row('Empunhadura', selectBox(gripOpts, k.grip, (v) => { k.grip = v; edited(); commit(); renderInspector(); }),
    btn('editar', () => select({ kind: 'grip', name: k.grip }))));
  if (i > 0) {
    p.append(row('Movimento até aqui', selectBox(Object.entries(EASES), k.ease || 'smooth', (v) => {
      if (v === 'smooth') delete k.ease; else k.ease = v;
      edited(); commit();
    })));
  }

  p.append(el('h3', {}, 'Arco no caminho'));
  p.append(el('div', { class: 'row' }, el('label', { class: 'wide' }, el('input', {
    type: 'checkbox', checked: !!k.arc, disabled: i === 0,
    onchange: (e) => { if (e.target.checked) k.arc = [0, -0.04, 0]; else delete k.arc; edited(); commit(); renderInspector(); },
  }), ' desviar a mão no meio do caminho até esta chave')));
  if (k.arc) p.append(vecRow('Desvio (m, arma)', () => k.arc, (a) => { k.arc = a; }, { step: 0.001, digits: 4 }));

  p.append(el('h3', {}, 'Ajuste fino da mão nesta chave'));
  p.append(hint('Somado à pose da empunhadura. Também pelo gizmo na vista (W mover, E girar).'));
  p.append(vecRow('Deslocamento (m)', () => k.offset, (a) => { k.offset = a; }, { step: 0.0005, digits: 4 }));
  p.append(hint('Eixos da arma: X esquerda, Y cima, Z frente.'));
  p.append(vecRow('Rotação (°)', () => k.rot, (a) => { k.rot = a; }, { step: 0.25, digits: 2 }));
  p.append(hint('Gira a MÃO em volta do punho (o antebraço fica). Eixos da mão: X lateral, Y costas da mão, Z dedos.'));
  p.append(el('div', { class: 'btns', style: 'margin-top:4px' },
    btn('Zerar deslocamento', () => { delete k.offset; edited(); commit(); }),
    btn('Zerar rotação', () => { delete k.rot; edited(); commit(); })));
  p.append(wristEditor(side, k));
  if (i > 0) {
    const autoOpen = k.open == null;
    p.append(el('div', { class: 'row' }, el('label', {}, 'Dedos abrem no caminho'),
      el('label', { class: 'wide' }, el('input', {
        type: 'checkbox', checked: autoOpen,
        onchange: (e) => { if (e.target.checked) delete k.open; else k.open = keys[i - 1].grip !== k.grip ? 0.7 : 0; edited(); commit(); renderInspector(); },
      }), ' auto'),
      autoOpen ? el('span', { class: 'muted' }, keys[i - 1].grip !== k.grip ? '(0.70)' : '(0)')
        : num(() => k.open, (v) => { k.open = v; }, { step: 0.01, digits: 2, min: 0, max: 1.5 })));
  }

  p.append(el('h3', {}, 'Dedos nesta chave'));
  p.append(hint('Desmarcado = os dedos fecham sozinhos em volta da empunhadura. Graus: 0 = esticado.'));
  p.append(fingerEditor({
    title: 'manual', get: () => k.fingers, set: (d) => { if (Object.keys(d).length) k.fingers = d; else delete k.fingers; },
    defaults: (f) => solvedFor(side, k.grip, f),
  }));

  p.append(el('div', { class: 'btns' },
    btn('Duplicar chave', () => {
      const c = JSON.parse(JSON.stringify(k));
      const next = keys[i + 1];
      c.t = rnd(next ? (k.t + next.t) / 2 : Math.min(1, k.t + 0.03), 4);
      keys.push(c);
      commit();
      select({ kind: 'key', side, i: keys.indexOf(c) });
      edited();
    }),
    btn('Copiar pose', () => {
      S.clipboard = JSON.parse(JSON.stringify({ grip: k.grip, offset: k.offset, rot: k.rot, wrist: k.wrist, fingers: k.fingers }));
      status('Pose copiada (empunhadura, ajuste, pulso e dedos).', 'ok');
    }),
    btn('Colar pose', () => {
      if (!S.clipboard) return;
      for (const f of ['grip', 'offset', 'rot', 'wrist', 'fingers']) {
        if (S.clipboard[f] === undefined) delete k[f]; else k[f] = JSON.parse(JSON.stringify(S.clipboard[f]));
      }
      edited(); commit(); renderInspector();
    }),
    btn('Excluir chave', () => deleteSelected(), 'danger')));
  return p;
}

function wristEditor(side, k) {
  const L = S.info.wrist_limits;
  const box = el('div', { class: 'finger' + (k.wrist ? ' manual' : '') });
  const live = () => {
    const f = S.cur;
    if (!f || !f.exact || !f.wrist || !f.wrist[side]) return null;
    const keys = S.anim.tracks[side];
    const atKey = f.p === null ? keys[0] === k : Math.abs(f.p - k.t) < 1e-9;
    return atKey ? f.wrist[side] : null;
  };
  const deg = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}°`;
  const info = el('div', { class: 'hint' });
  FIELDS.push(() => {
    const w = live();
    if (!w) { info.textContent = 'Leve o cursor até esta chave para ver o pulso.'; info.style.color = ''; return; }
    const out = w[2] < L.x[0] - 0.5 || w[2] > L.x[1] + 0.5 || w[3] < L.y[0] - 0.5 || w[3] > L.y[1] + 0.5;
    info.textContent = `Agora: flexão ${deg(w[0])}, desvio ${deg(w[1])}. O ombro pedia ${deg(w[2])}, ${deg(w[3])}`
      + (out ? ' — fora do alcance do pulso: o antebraço saiu da direção do ombro. Gire a mão na empunhadura'
        + ' (giro / palma) ou mova o ombro até o pedido caber nos limites.' : '.');
    info.style.color = out ? '#ffb86b' : '';
  });
  box.append(el('div', { class: 'fhead' }, el('b', {}, 'Pulso'),
    el('label', {}, el('input', {
      type: 'checkbox', checked: !!k.wrist,
      onchange: (e) => {
        if (e.target.checked) { const w = live(); k.wrist = clampWrist(w ? [w[0], w[1]] : [0, 0]); } else delete k.wrist;
        edited(); commit(); renderInspector();
      },
    }), ' manual'),
    k.wrist ? null : el('span', { class: 'muted', style: 'font-size:11px' }, 'auto: segue o ombro, cotovelo fora da tela')));
  if (k.wrist) {
    const get = (j) => () => (k.wrist || [0, 0])[j] ?? 0;
    const set = (j) => (v) => { const w = (k.wrist || [0, 0]).slice(0, 2); w[j] = v; k.wrist = clampWrist(w); };
    box.append(el('div', { class: 'row' }, el('label', {}, 'Flexão X'),
      num(get(0), set(0), { step: 0.25, digits: 1, min: L.x[0], max: L.x[1] }),
      el('span', { class: 'muted' }, `° (${L.x[0]} a +${L.x[1]})`)));
    box.append(el('div', { class: 'row' }, el('label', {}, 'Desvio Y'),
      num(get(1), set(1), { step: 0.25, digits: 1, min: L.y[0], max: L.y[1] }),
      el('span', { class: 'muted' }, `° (${L.y[0]} a +${L.y[1]})`)));
  }
  box.append(info, hint('A mão fica na arma e o antebraço gira em volta do punho. 0, 0 = mão reta com o antebraço.'
    + ' Flexão + = dedos para o lado da palma; desvio + = para o polegar, − = para o mindinho. O antebraço torce'
    + ' junto com a mão (o pulso não torce). Auto = o pulso segue a direção do ombro até o limite e, se o cotovelo'
    + ' aparecer na tela, dobra o que puder para tirá-lo de vista. Gizmo: "Pulso" (R).'));
  return box;
}

function gripUsers(name) {
  const out = [];
  for (const side of ['L', 'R']) S.anim.tracks[side].forEach((k, i) => { if (k.grip === name) out.push([side, i]); });
  return out;
}

function gripPanel(name) {
  const g = S.anim.grips[name];
  const p = el('div');
  const users = gripUsers(name);
  p.append(el('h2', {}, `Empunhadura “${name}”`));
  p.append(hint('Cilindro onde a mão segura: a palma encosta nele e os dedos fecham em volta. Mudar aqui muda TODAS as chaves que usam esta empunhadura.'));
  const chips = el('div', { class: 'chips' });
  users.forEach(([side, i]) => chips.append(el('button', {
    style: `color:${SIDE_COLOR[side]}`, onclick: () => select({ kind: 'key', side, i }),
  }, `${side === 'L' ? 'esq' : 'dir'} #${i + 1} (${S.anim.tracks[side][i].t.toFixed(2)})`)));
  p.append(row('Usada por', users.length ? chips : el('span', { class: 'muted' }, 'nenhuma chave')));
  const nameIn = el('input', {
    type: 'text', value: name, style: 'width:140px',
    onkeydown: (e) => { e.stopPropagation(); if (e.key === 'Enter') e.target.blur(); },
    onchange: (e) => {
      const nn = e.target.value.trim().replace(/\s+/g, '_');
      if (!nn || nn === name) return;
      if (S.anim.grips[nn]) { setError(`já existe uma empunhadura “${nn}”`); e.target.value = name; return; }
      const grips = {};
      for (const [k, v] of Object.entries(S.anim.grips)) grips[k === name ? nn : k] = v;
      S.anim.grips = grips;
      for (const side of ['L', 'R']) for (const k of S.anim.tracks[side]) if (k.grip === name) k.grip = nn;
      S.sel = { kind: 'grip', name: nn };
      rebuildGripHelpers();
      edited(); commit(); renderInspector();
    },
  });
  p.append(row('Nome', nameIn));
  const partOpts = [['', '(arma)'], ...S.info.animated.map((n) => [n, `peça: ${n}`])];
  p.append(row('Presa a', selectBox(partOpts, g.part || '', (v) => { g.part = v || null; edited(); commit(); })));
  p.append(hint('Presa a uma peça, a mão acompanha a peça (bomba, carregador) quando ela se move.'));
  p.append(el('h3', {}, 'Posição e orientação (espaço da arma)'));
  p.append(vecRow('Centro (m)', () => g.c, (a) => { g.c = a; }, { step: 0.0005, digits: 4 }));
  p.append(vecRow('Eixo → polegar', () => g.axis, (a) => { g.axis = a; }, { step: 0.01, digits: 3 }));
  p.append(hint('Direção do cilindro; o polegar aponta para este lado (seta verde).'));
  p.append(vecRow('Palma', () => g.palm, (a) => { g.palm = a; }, { step: 0.01, digits: 3 }));
  p.append(hint('Do eixo do cilindro para a palma (seta rosa): de que lado a mão encosta.'));
  p.append(vecRow('Raio (m)', () => radii(g), (a) => { g.r = a; }, { step: 0.0005, digits: 4, min: 0.001 }, 2, ['P', 'L']));
  p.append(hint('P = na direção da palma (espessura), L = lateral (largura).'));
  p.append(el('h3', {}, 'Mão'));
  p.append(row('Giro no cilindro (°)', num(() => g.tilt || 0, (v) => { g.tilt = v; }, { step: 0.5, digits: 2 })));
  p.append(row('Oposição polegar (°)', num(() => g.opp ?? 28.65, (v) => { g.opp = v; }, { step: 0.5, digits: 2 })));
  const hasReach = !!g.reach;
  p.append(el('div', { class: 'row' }, el('label', {}, 'Limite de curvatura'), el('label', { class: 'wide' }, el('input', {
    type: 'checkbox', checked: !hasReach,
    onchange: (e) => { if (e.target.checked) g.reach = null; else g.reach = [95, 105, 80]; edited(); commit(); renderInspector(); },
  }), ' padrão (95°, 105°, 80°)')));
  if (hasReach) p.append(vecRow('Limite (°)', () => g.reach, (a) => { g.reach = a; }, { step: 0.5, digits: 1 }, 3, ['1', '2', '3']));
  p.append(el('h3', {}, 'Dedos fixos (em todas as chaves desta empunhadura)'));
  p.append(hint('Ex.: o indicador no gatilho. Uma chave ainda pode sobrescrever com "Dedos nesta chave".'));
  const side = users.length ? users[0][0] : 'L';
  p.append(fingerEditor({
    title: 'fixo', get: () => g.fix, set: (d) => { g.fix = d; }, defaults: (f) => solvedFor(side, name, f),
  }));
  p.append(el('div', { class: 'btns' },
    btn('Duplicar empunhadura', () => {
      let nn = name + '_2', n = 2;
      while (S.anim.grips[nn]) nn = `${name}_${++n}`;
      S.anim.grips[nn] = JSON.parse(JSON.stringify(g));
      rebuildGripHelpers();
      commit();
      select({ kind: 'grip', name: nn });
      edited();
    }),
    btn('Excluir', () => deleteSelected(), 'danger')));
  return p;
}

function curvePanel(name, i) {
  const c = CURVES.find((x) => x.name === name);
  const pts = S.anim.curves[name];
  const pt = pts[i];
  const p = el('div');
  p.append(el('h2', {}, `Curva “${c.label}” · ponto ${i + 1} de ${pts.length}`), hint(c.hint),
    el('div', { class: 'btns', style: 'margin-top:0' },
      btn('◀ anterior', () => select({ kind: 'curve', name, i: Math.max(0, i - 1) })),
      btn('próximo ▶', () => select({ kind: 'curve', name, i: Math.min(pts.length - 1, i + 1) }))));
  p.append(row('Tempo (0 a 1)', num(() => pt[0], (v) => { pt[0] = v; S.p = v; updateTime(); }, { step: 0.001, digits: 3, min: 0, max: 1 })));
  p.append(row('Valor', num(() => pt[1], (v) => { pt[1] = v; }, { step: c.step, digits: c.digits + 1 })));
  if (i > 0) {
    p.append(row('Chegada', selectBox(Object.entries(EASES), pt[2] || 'smooth', (v) => {
      if (v === 'smooth') pt.length = 2; else pt[2] = v;
      edited(); commit();
    })));
  }
  p.append(hint('Na linha do tempo: arraste o ponto (Shift trava o valor), duplo clique cria outro.'));
  p.append(el('div', { class: 'btns' }, btn('Excluir ponto', () => deleteSelected(), 'danger')));
  return p;
}

function shellPanel(i) {
  const w = S.anim.shell[i];
  const p = el('div');
  p.append(el('h2', {}, `Cartucho na mão · janela ${i + 1}`),
    hint('Enquanto o cursor estiver dentro da janela, um cartucho é desenhado na palma da mão esquerda.'));
  p.append(row('Início', num(() => w[0], (v) => { w[0] = v; }, { step: 0.001, digits: 3, min: 0, max: 1 })));
  p.append(row('Fim', num(() => w[1], (v) => { w[1] = v; }, { step: 0.001, digits: 3, min: 0, max: 1 })));
  p.append(el('div', { class: 'btns' }, btn('Excluir janela', () => deleteSelected(), 'danger')));
  return p;
}

function globalPanel() {
  const a = S.anim;
  const p = el('div');
  p.append(el('h2', {}, `Geral — ${S.hero} (${S.info.kind})`));
  p.append(el('h3', {}, 'Inclinação da arma na recarga'));
  p.append(hint('Pose máxima; ao longo da recarga ela é multiplicada pela curva "Inclinação (peso)".'));
  const labels = ['Rolar (°)', 'Arfar (°)', 'Guinar (°)', 'Desloc. X (m)', 'Desloc. Y (m)', 'Desloc. Z (m)'];
  labels.forEach((lab, j) => p.append(row(lab, num(() => a.tilt[j], (v) => { a.tilt[j] = v; },
    j < 3 ? { step: 0.25, digits: 2 } : { step: 0.001, digits: 4 }))));
  p.append(el('h3', {}, 'Ombros (espaço da vista)'));
  p.append(hint('Ficam fora da tela. Se a mão for longe demais, o ombro é puxado para a frente. Câmera livre (F) mostra os ombros.'));
  for (const side of ['R', 'L']) {
    p.append(vecRow(SIDE_PT[side], () => a.shoulders[side], (v) => { a.shoulders[side] = v; }, { step: 0.002, digits: 3 }));
    const on = S.sel.kind === 'shoulder' && S.sel.side === side;
    p.append(el('div', { class: 'btns', style: 'margin:0 0 6px' }, btn(on ? 'gizmo ativo' : 'mover com gizmo', () => select(on ? { kind: 'global' } : { kind: 'shoulder', side }), on ? 'on' : '')));
  }
  p.append(el('h3', {}, 'Cotovelos (para onde dobram)'));
  for (const side of ['R', 'L']) p.append(vecRow(SIDE_PT[side], () => a.poles[side], (v) => { a.poles[side] = v; }, { step: 0.01, digits: 3 }));
  p.append(el('h3', {}, 'Cartucho na mão (janelas)'));
  a.shell.forEach((w, i) => p.append(row(`Janela ${i + 1}`, num(() => w[0], (v) => { w[0] = v; }, { step: 0.001, digits: 3 }),
    num(() => w[1], (v) => { w[1] = v; }, { step: 0.001, digits: 3 }),
    btn('×', () => { a.shell.splice(i, 1); edited(); commit(); renderInspector(); }, 'danger'))));
  p.append(el('div', { class: 'btns', style: 'margin-top:2px' }, btn('+ janela', () => { a.shell.push([0.2, 0.4]); edited(); commit(); renderInspector(); })));
  p.append(el('h3', {}, 'Prévia'));
  p.append(row('Duração (s)', num(() => a.duration, (v) => { a.duration = v; }, { step: 0.01, digits: 2, min: 0.2 })));
  p.append(hint('Só para tocar a prévia e mostrar segundos: no combate a recarga dura 1,6 s.'));
  p.append(el('h3', {}, 'Notas'));
  const ta = el('textarea', {
    onkeydown: (e) => e.stopPropagation(),
    oninput: (e) => { a.notes = e.target.value; refreshStatus(); }, onchange: () => commit(),
  });
  ta.value = a.notes || '';
  p.append(ta);
  return p;
}

function select(sel) {
  S.sel = sel || { kind: 'global' };
  if (S.sel.kind === 'key') {
    setPlaying(false);
    const k = S.anim.tracks[S.sel.side][S.sel.i];
    if (k) setP(k.t);
  } else if (S.sel.kind === 'curve') {
    setPlaying(false);
    setP(S.anim.curves[S.sel.name][S.sel.i][0]);
  }
  renderInspector();
  drawTimeline();
  updateMarkers();
  updateGripHelpers();
  syncProxy();
}

function deleteSelected() {
  const s = S.sel;
  if (s.kind === 'key') {
    const keys = S.anim.tracks[s.side];
    if (keys.length <= 1) { setError('a mão precisa de pelo menos uma chave'); return; }
    keys.splice(s.i, 1);
    commit();
    select({ kind: 'key', side: s.side, i: Math.min(s.i, keys.length - 1) });
  } else if (s.kind === 'curve') {
    S.anim.curves[s.name].splice(s.i, 1);
    commit();
    select({ kind: 'global' });
  } else if (s.kind === 'shell') {
    S.anim.shell.splice(s.i, 1);
    commit();
    select({ kind: 'global' });
  } else if (s.kind === 'grip') {
    if (gripUsers(s.name).length) { setError(`a empunhadura “${s.name}” ainda é usada por chaves`); return; }
    delete S.anim.grips[s.name];
    rebuildGripHelpers();
    commit();
    select({ kind: 'global' });
  } else return;
  edited();
  updateMarkers();
}

// ------------------------------------------------------------------------------------------
// Barra superior e atalhos
// ------------------------------------------------------------------------------------------
function setCam(free) {
  S.freeCam = free;
  orbit.enabled = free;
  tc.camera = free ? freeCam : gameCam;
  $('#cam').textContent = free ? 'Câmera: livre' : 'Câmera: jogo';
  $('#camlabel').textContent = free ? 'Câmera livre (F volta para a do jogo)' : 'Câmera do jogo (FOV 50°, 16:9)';
  lastSize = '';
  if (free) updateArmGuides();
}
function setGizmo(mode) {
  S.gizmo = mode;
  $('#gmove').classList.toggle('on', mode === 'translate');
  $('#grot').classList.toggle('on', mode === 'rotate');
  $('#gwrist').classList.toggle('on', mode === 'wrist');
  syncProxy();
}

$('#play').onclick = () => setPlaying(!S.playing);
$('#loop').onclick = () => { S.loop = !S.loop; $('#loop').classList.toggle('on', S.loop); };
$('#speed').onchange = (e) => { S.speed = +e.target.value; };
$('#idle').onclick = () => {
  setPlaying(false);
  S.idle = !S.idle;
  $('#idle').classList.toggle('on', S.idle);
  updateTime();
  drawTimeline();
  if (S.idle && S.idleFrame) applyFrame(S.idleFrame);
  touchLive();
};
$('#cam').onclick = () => setCam(!S.freeCam);
$('#gmove').onclick = () => setGizmo('translate');
$('#grot').onclick = () => setGizmo('rotate');
$('#gwrist').onclick = () => setGizmo('wrist');
$('#helpers').onclick = () => { S.helpers = !S.helpers; $('#helpers').classList.toggle('on', S.helpers); };
$('#helpbtn').onclick = () => $('#help').classList.add('show');
$('#help').onclick = (e) => { if (e.target.id === 'help') $('#help').classList.remove('show'); };
$('#undo').onclick = undo;
$('#redo').onclick = redo;
$('#save').onclick = save;
$('#download').onclick = () => {
  commit();
  const blob = new Blob([JSON.stringify(S.anim, null, 2) + '\n'], { type: 'application/json' });
  const a = el('a', { href: URL.createObjectURL(blob), download: `${S.hero}_fp_anim.json` });
  document.body.append(a);
  a.click();
  a.remove();
};
$('#import').onclick = () => $('#file').click();
$('#file').onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  let data;
  try { data = JSON.parse(await file.text()); } catch (err) { setError('JSON inválido: ' + err.message); return; }
  if (data.hero && data.hero !== S.hero) {
    if (!confirm(`Este arquivo é de “${data.hero}”, mas o editor está em “${S.hero}”. Importar mesmo assim?`)) return;
  }
  const res = await api('/api/bake', { hero: S.hero, anim: data, times: [0] });
  if (!res.ok) { setError('arquivo importado inválido: ' + res.error); return; }
  commit();
  const prev = S.committed;
  setAnim(data, false);
  S.undo.push(prev);
  S.redo = [];
  status('Importado. Clique em "Salvar no jogo" para gravar.', 'ok');
  doBake();
};
$('#revert').onclick = async () => {
  if (isDirty() && !confirm('Descartar as alterações não salvas?')) return;
  await loadHero(S.hero);
};
$('#hero').onchange = async (e) => {
  if (isDirty() && !confirm('Há alterações não salvas. Trocar de herói mesmo assim?')) { e.target.value = S.hero; return; }
  await loadHero(e.target.value);
};
addEventListener('beforeunload', (e) => { if (isDirty()) { e.preventDefault(); e.returnValue = ''; } });

addEventListener('keydown', (e) => {
  if (e.target.matches && e.target.matches('input, select, textarea')) return;
  const k = e.key.toLowerCase();
  if (e.ctrlKey && k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
  if (e.ctrlKey && (k === 'y' || (k === 'z' && e.shiftKey))) { e.preventDefault(); redo(); return; }
  if (e.ctrlKey && k === 's') { e.preventDefault(); save(); return; }
  if (e.ctrlKey || e.altKey) return;
  if (k === ' ') { e.preventDefault(); setPlaying(!S.playing); }
  else if (k === 'arrowleft' || k === 'arrowright') {
    e.preventDefault();
    setPlaying(false);
    const step = 1 / SAMPLES * (e.shiftKey ? 0.25 : 1);
    setP(S.p + (k === 'arrowleft' ? -step : step));
  } else if (k === 'home') setP(0);
  else if (k === 'end') setP(1);
  else if (k === 'delete' || k === 'backspace') { e.preventDefault(); deleteSelected(); }
  else if (k === 'w') setGizmo('translate');
  else if (k === 'e') setGizmo('rotate');
  else if (k === 'r') setGizmo('wrist');
  else if (k === 'f') setCam(!S.freeCam);
  else if (k === 'h') $('#helpers').click();
  else if (k === 'escape') select({ kind: 'global' });
});
addEventListener('resize', () => { lastSize = ''; });

// ------------------------------------------------------------------------------------------
// Início
// ------------------------------------------------------------------------------------------
(async () => {
  try {
    const list = await api('/api/heroes');
    for (const info of list) {
      S.infos[info.hero] = info;
      $('#hero').append(el('option', { value: info.hero }, info.hero));
    }
    const first = S.infos[location.hash.slice(1)] ? location.hash.slice(1) : list[0].hero;
    $('#hero').value = first;
    setCam(false);
    requestAnimationFrame(tick);
    await loadHero(first);
  } catch (err) {
    setError('não consegui falar com o servidor do editor: ' + err.message);
  }
})();

// Acesso para depuração pelo console do navegador.
window.fpEditor = { S, proxy, gameCam, freeCam, tc, select, setP, get arms() { return arms; }, THREE };
