(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// ---------------------------------------------------------------- config
// Defaults follow the wasmarcade GTA Vice City key list.
const DEFAULTS = {
  L1: 'Q', L2: 'C', R1: 'E', R2: 'MOUSE_LEFT',
  TRI: 'F', CIR: 'SHIFT', CRO: 'SPACE', SQU: 'CTRL',
  DU: 'UP', DD: 'DOWN', DL: 'LEFT', DR: 'RIGHT',
  ESC: 'ESC', ENTER: 'ENTER', HORN: 'H', CAM: 'V', RADIO: 'R',
  SU: 'W', SD: 'S', SL: 'A', SR: 'D',
  TAP: 'MOUSE_LEFT', TAP2: 'MOUSE_RIGHT',
};
const TITLES = {
  L1: 'L1', L2: 'L2', R1: 'R1', R2: 'R2', TRI: '△ Triangle', CIR: '○ Circle', CRO: '✕ Cross', SQU: '□ Square',
  DU: 'D-pad up', DD: 'D-pad down', DL: 'D-pad left', DR: 'D-pad right',
  ESC: 'ESC button', ENTER: 'ENTER button', HORN: 'HORN button', CAM: 'CAM button', RADIO: 'RADIO button',
  SU: 'Stick up', SD: 'Stick down', SL: 'Stick left', SR: 'Stick right',
  TAP: 'Touchpad tap', TAP2: 'Touchpad 2-finger tap',
};
const SHORT = { SPACE: 'SPC', MOUSE_LEFT: 'LMB', MOUSE_RIGHT: 'RMB', MOUSE_MIDDLE: 'MMB', WHEEL_UP: 'WHEEL▲',
  WHEEL_DOWN: 'WHEEL▼', PAGEUP: 'PGUP', PAGEDOWN: 'PGDN', BACKSPACE: 'BKSP', UP: '↑', DOWN: '↓', LEFT: '←',
  RIGHT: '→', ENTER: 'ENT', SHIFT: 'SHIFT', CAPSLOCK: 'CAPS', INSERT: 'INS', DELETE: 'DEL', COMMA: ',', PERIOD: '.',
  SLASH: '/', SEMICOLON: ';', QUOTE: "'", LBRACKET: '[', RBRACKET: ']', MINUS: '-', EQUALS: '=', BACKSLASH: '\\',
  BACKTICK: '`', RSHIFT: 'R-SHIFT', RCTRL: 'R-CTRL', RALT: 'R-ALT' };
const short = n => (n ? SHORT[n] || n : '—');
const FALLBACK_GROUPS = [['Letters', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')], ['Numbers', '0123456789'.split('')],
  ['Special', ['SPACE', 'ENTER', 'ESC', 'TAB', 'SHIFT', 'CTRL', 'ALT', 'UP', 'DOWN', 'LEFT', 'RIGHT']],
  ['Mouse', ['MOUSE_LEFT', 'MOUSE_RIGHT', 'MOUSE_MIDDLE', 'WHEEL_UP', 'WHEEL_DOWN']]];

const LS = 'vc.controller.v1';
let cfg = { map: { ...DEFAULTS }, sens: 2, stick: 1, invert: false, haptic: true, labels: true, code: '' };
try { const s = JSON.parse(localStorage.getItem(LS) || '{}'); cfg = { ...cfg, ...s, map: { ...DEFAULTS, ...(s.map || {}) } }; } catch (_) {}
const save = () => { try { localStorage.setItem(LS, JSON.stringify(cfg)); } catch (_) {} };
const urlCode = new URLSearchParams(location.search).get('code');
if (urlCode && /^\d{6}$/.test(urlCode)) cfg.code = urlCode;

// ---------------------------------------------------------------- network
let ws = null, paired = false, lastSig = null, pendingCode = '', retry = 0, retryT = 0, pingT = 0;
const pill = $('#pill');
const setPill = (t, bad) => { pill.textContent = t; pill.classList.toggle('bad', !!bad); };
const raw = o => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); };
const tx = o => { if (paired) raw(o); };

function connect() {
  clearTimeout(retryT);
  setPill('connecting…', true);
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws?role=mobile`);
  ws.onopen = () => { retry = 0; if (cfg.code) { pendingCode = cfg.code; raw({ t: 'pair', code: cfg.code }); } else showPair(''); };
  ws.onmessage = e => {
    let d; try { d = JSON.parse(e.data); } catch (_) { return; }
    if (d.t === 'paired') {
      if (d.ok) {
        paired = true; cfg.code = pendingCode; save(); hidePair(); lastSig = null; sendKeys(true);
        clearInterval(pingT); ping(); pingT = setInterval(ping, 1000);
      } else {
        paired = false; cfg.code = ''; save();
        showPair(d.wait ? 'Too many wrong codes — wait 30 s.' : 'Wrong code. Check the laptop page.');
      }
    } else if (d.t === 'pong') {
      setPill(`● ${Math.max(0, Math.round(performance.now() - d.ts))} ms`, false);
    }
  };
  ws.onclose = () => {
    paired = false; clearInterval(pingT); releaseAll(false);
    setPill('offline — retrying', true);
    retryT = setTimeout(connect, Math.min(3000, 400 + 400 * retry++));
  };
}
const ping = () => raw({ t: 'p', ts: performance.now() });

// ---------------------------------------------------------------- key state
const active = new Set();   // control ids currently held (buttons, tap pulses)
const sticks = new Set();   // stick direction ids currently held
function sendKeys(force) {
  const set = new Set();
  for (const id of active) if (cfg.map[id]) set.add(cfg.map[id]);
  for (const id of sticks) if (cfg.map[id]) set.add(cfg.map[id]);
  const keys = [...set].sort(), sig = keys.join(',');
  if (sig === lastSig && !force) return;
  lastSig = sig;
  tx({ t: 'k', keys });
}
function releaseAll(notify = true) {
  active.clear(); sticks.clear();
  $$('.c.on').forEach(el => el.classList.remove('on'));
  stickReset && stickReset();
  if (notify) { lastSig = null; sendKeys(true); }
}
const buzz = () => { if (cfg.haptic && navigator.vibrate) navigator.vibrate(8); };

// mouse deltas: send immediately; if the socket is backed up, merge and flush per frame
let pend = { x: 0, y: 0 }, flushQ = 0;
function sendMove(x, y) {
  pend.x += x; pend.y += y;
  if (ws && ws.readyState === 1 && paired && ws.bufferedAmount < 2048) flushMove();
  else if (!flushQ) flushQ = requestAnimationFrame(() => { flushQ = 0; flushMove(); });
}
function flushMove() {
  if (!pend.x && !pend.y) return;
  tx({ t: 'm', x: pend.x, y: pend.y }); pend = { x: 0, y: 0 };
}
function pulse(id, ms = 55) {
  active.add(id); sendKeys(); buzz();
  setTimeout(() => { active.delete(id); sendKeys(); }, ms);
}

// ---------------------------------------------------------------- buttons
let remap = false;
function bindButton(el) {
  const id = el.dataset.id, pts = new Set();
  el.addEventListener('pointerdown', e => {
    if (remap) return;
    e.preventDefault(); el.setPointerCapture(e.pointerId); pts.add(e.pointerId);
    if (pts.size === 1) { active.add(id); el.classList.add('on'); buzz(); sendKeys(); }
  });
  const up = e => {
    if (!pts.delete(e.pointerId)) return;
    if (!pts.size) { active.delete(id); el.classList.remove('on'); sendKeys(); }
  };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => el.addEventListener(ev, up));
}
$$('.shoulder,.small,.dp,.face').forEach(bindButton);

// ---------------------------------------------------------------- stick (floating, 8-way -> keys)
let stickReset = null;
(() => {
  const zone = $('#stickzone'), stick = $('#stick'), knob = $('#knob');
  let pid = null, cx = 0, cy = 0, R = 1;
  const DIRS = [['SR'], ['SU', 'SR'], ['SU'], ['SU', 'SL'], ['SL'], ['SD', 'SL'], ['SD'], ['SD', 'SR']];
  function move(e) {
    const r = zone.getBoundingClientRect();
    const dx = e.clientX - (r.left + cx), dy = e.clientY - (r.top + cy), dist = Math.hypot(dx, dy);
    const k = Math.min(dist, R * 0.62) / (dist || 1);
    knob.style.transform = `translate3d(${dx * k}px,${dy * k}px,0)`;
    const next = new Set();
    if (dist > R * 0.28) {
      const ang = Math.atan2(-dy, dx) * 180 / Math.PI;
      DIRS[(Math.round(ang / 45) + 8) % 8].forEach(d => next.add(d));
    }
    if (next.size !== sticks.size || [...next].some(d => !sticks.has(d))) {
      sticks.clear(); next.forEach(d => sticks.add(d)); sendKeys();
    }
  }
  zone.addEventListener('pointerdown', e => {
    if (remap || pid !== null) return;
    e.preventDefault(); pid = e.pointerId; zone.setPointerCapture(pid);
    const r = zone.getBoundingClientRect(); R = stick.offsetWidth / 2;
    cx = Math.min(Math.max(e.clientX - r.left, R), Math.max(R, r.width - R));
    cy = Math.min(Math.max(e.clientY - r.top, R), Math.max(R, r.height - R));
    stick.style.left = cx + 'px'; stick.style.top = cy + 'px'; stick.classList.add('live');
    buzz(); move(e);
  });
  zone.addEventListener('pointermove', e => { if (e.pointerId === pid) move(e); });
  const end = e => {
    if (e.pointerId !== pid) return;
    pid = null; stickReset();
    sendKeys();
  };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => zone.addEventListener(ev, end));
  stickReset = () => {
    pid = null; sticks.clear(); stick.classList.remove('live');
    stick.style.left = ''; stick.style.top = ''; knob.style.transform = '';
  };
})();

// ---------------------------------------------------------------- touchpad (relative mouse)
(() => {
  const pad = $('#pad'), dot = $('#dot');
  const ptr = new Map();
  let t0 = 0, moved = 0, maxN = 0, prim = null, rx = 0, ry = 0;
  const showDot = e => {
    const r = pad.getBoundingClientRect();
    dot.style.transform = `translate3d(${e.clientX - r.left}px,${e.clientY - r.top}px,0)`; dot.style.opacity = 1;
  };
  pad.addEventListener('pointerdown', e => {
    if (remap || e.target.closest('.sub')) return;
    e.preventDefault(); pad.setPointerCapture(e.pointerId);
    if (!ptr.size) { t0 = performance.now(); moved = 0; maxN = 0; prim = e.pointerId; rx = ry = 0; }
    ptr.set(e.pointerId, { x: e.clientX, y: e.clientY }); maxN = Math.max(maxN, ptr.size);
    pad.classList.add('on'); if (e.pointerId === prim) showDot(e);
  });
  pad.addEventListener('pointermove', e => {
    const p = ptr.get(e.pointerId); if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
    moved += Math.abs(dx) + Math.abs(dy);
    if (e.pointerId !== prim) return;
    showDot(e);
    rx += dx * cfg.sens; ry += dy * cfg.sens * (cfg.invert ? -1 : 1);
    const ix = Math.trunc(rx), iy = Math.trunc(ry); rx -= ix; ry -= iy;
    if (ix || iy) sendMove(ix, iy);
  });
  const up = e => {
    if (!ptr.delete(e.pointerId)) return;
    if (e.pointerId === prim && ptr.size) prim = ptr.keys().next().value;
    if (ptr.size) return;
    pad.classList.remove('on'); dot.style.opacity = 0;
    if (e.type === 'pointerup' && performance.now() - t0 < 260 && moved < 10) pulse(maxN >= 2 ? 'TAP2' : 'TAP');
  };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => pad.addEventListener(ev, up));
})();

// ---------------------------------------------------------------- labels / remap UI
function refreshLabels() {
  $$('[data-id]').forEach(el => { const k = el.querySelector(':scope > .kb'); if (k) k.textContent = short(cfg.map[el.dataset.id]); });
  $('#tap1').textContent = short(cfg.map.TAP); $('#tap2').textContent = short(cfg.map.TAP2);
  document.body.classList.toggle('nolabels', !cfg.labels);
  document.documentElement.style.setProperty('--stick', cfg.stick);
}
let groups = FALLBACK_GROUPS, pickId = null;
fetch('/keys').then(r => r.json()).then(d => { groups = d.groups; }).catch(() => {});

const picker = $('#picker');
function openPicker(id) {
  pickId = id;
  $('#picktitle').textContent = `${TITLES[id] || id}: ${short(cfg.map[id])}`;
  const grid = $('#pickgrid'); grid.innerHTML = '';
  for (const [name, keys] of groups) {
    const h = document.createElement('div'); h.className = 'grpname'; h.textContent = name;
    const w = document.createElement('div'); w.className = 'chips';
    for (const k of keys) {
      const b = document.createElement('button'); b.className = 'chip' + (cfg.map[id] === k ? ' cur' : '');
      b.textContent = short(k); b.dataset.k = k; w.appendChild(b);
    }
    grid.append(h, w);
  }
  picker.hidden = false;
}
const closePicker = () => { picker.hidden = true; pickId = null; };
function assign(name) { if (pickId) { cfg.map[pickId] = name; save(); refreshLabels(); } closePicker(); }
$('#pickgrid').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) assign(b.dataset.k); });
$('#picknone').onclick = () => assign('');
$('#pickreset').onclick = () => assign(DEFAULTS[pickId] || '');
$('#pickclose').onclick = closePicker;

const CODEMAP = { Space: 'SPACE', Enter: 'ENTER', NumpadEnter: 'ENTER', Escape: 'ESC', Tab: 'TAB', Backspace: 'BACKSPACE',
  ShiftLeft: 'SHIFT', ShiftRight: 'RSHIFT', ControlLeft: 'CTRL', ControlRight: 'RCTRL', AltLeft: 'ALT', AltRight: 'RALT',
  CapsLock: 'CAPSLOCK', ArrowUp: 'UP', ArrowDown: 'DOWN', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', Home: 'HOME', End: 'END',
  Insert: 'INSERT', Delete: 'DELETE', PageUp: 'PAGEUP', PageDown: 'PAGEDOWN', Comma: 'COMMA', Period: 'PERIOD',
  Slash: 'SLASH', Semicolon: 'SEMICOLON', Quote: 'QUOTE', BracketLeft: 'LBRACKET', BracketRight: 'RBRACKET',
  Minus: 'MINUS', Equal: 'EQUALS', Backslash: 'BACKSLASH', Backquote: 'BACKTICK' };
document.addEventListener('keydown', e => {
  if (picker.hidden) return;
  const c = e.code;
  const n = /^Key[A-Z]$/.test(c) ? c[3] : /^Digit\d$/.test(c) ? c[5] : /^F([1-9]|1[0-2])$/.test(c) ? c : CODEMAP[c];
  if (n) { e.preventDefault(); assign(n); }
});

// capture phase: in remap mode every control opens the picker instead of firing
document.addEventListener('pointerdown', e => {
  if (!remap || !picker.hidden) return;
  const c = e.target.closest('.c'); if (!c) return;
  e.preventDefault(); e.stopPropagation(); openPicker(c.dataset.id);
}, true);
const banner = $('#banner'), remapBtn = $('#btn-remap');
remapBtn.onclick = () => {
  remap = !remap; releaseAll();
  document.body.classList.toggle('remap', remap); banner.hidden = !remap; remapBtn.classList.toggle('active', remap);
  remapBtn.textContent = remap ? 'DONE' : 'KEYS';
};

// ---------------------------------------------------------------- settings
const settings = $('#settings');
function syncSettings() {
  $('#s-sens').value = cfg.sens; $('#o-sens').textContent = cfg.sens.toFixed(1);
  $('#s-stick').value = cfg.stick; $('#o-stick').textContent = cfg.stick.toFixed(2);
  $('#s-invert').checked = cfg.invert; $('#s-haptic').checked = cfg.haptic; $('#s-labels').checked = cfg.labels;
}
$('#btn-settings').onclick = () => { syncSettings(); settings.hidden = false; };
$('#setclose').onclick = () => { settings.hidden = true; };
$('#s-sens').oninput = e => { cfg.sens = +e.target.value; $('#o-sens').textContent = cfg.sens.toFixed(1); save(); };
$('#s-stick').oninput = e => { cfg.stick = +e.target.value; $('#o-stick').textContent = cfg.stick.toFixed(2); save(); refreshLabels(); };
$('#s-invert').onchange = e => { cfg.invert = e.target.checked; save(); };
$('#s-haptic').onchange = e => { cfg.haptic = e.target.checked; save(); };
$('#s-labels').onchange = e => { cfg.labels = e.target.checked; save(); refreshLabels(); };
function twoTap(btn, label, fn) {
  let armed = 0;
  btn.onclick = () => {
    if (!armed) { armed = setTimeout(() => { armed = 0; btn.textContent = label; }, 3000); btn.textContent = 'Tap again to confirm'; return; }
    clearTimeout(armed); armed = 0; btn.textContent = label; fn();
  };
}
twoTap($('#set-reset'), 'Reset ALL keys to GTA defaults', () => { cfg.map = { ...DEFAULTS }; save(); refreshLabels(); });
twoTap($('#set-forget'), 'Forget pairing code', () => { cfg.code = ''; save(); settings.hidden = true; showPair(''); });

// ---------------------------------------------------------------- pairing
const pairBox = $('#pair'), codeIn = $('#code');
function showPair(msg) { pairBox.hidden = false; $('#pairmsg').textContent = msg || ''; codeIn.value = ''; }
function hidePair() { pairBox.hidden = true; }
function submitCode() {
  const c = codeIn.value.replace(/\D/g, '');
  if (c.length !== 6) { $('#pairmsg').textContent = 'Enter all 6 digits.'; return; }
  pendingCode = c; raw({ t: 'pair', code: c });
}
$('#pairgo').onclick = submitCode;
codeIn.addEventListener('input', () => { codeIn.value = codeIn.value.replace(/\D/g, '').slice(0, 6); if (codeIn.value.length === 6) submitCode(); });

// ---------------------------------------------------------------- misc
async function toggleFS() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
      try { await screen.orientation.lock('landscape'); } catch (_) {}
    } else await document.exitFullscreen();
  } catch (_) {}
}
$('#btn-fs').onclick = toggleFS; $('#rotatefs').onclick = toggleFS;
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('visibilitychange', () => { if (document.hidden) { releaseAll(); raw({ t: 'r' }); } });
window.addEventListener('blur', () => releaseAll());
window.addEventListener('pagehide', () => raw({ t: 'r' }));
try { navigator.wakeLock && navigator.wakeLock.request('screen').catch(() => {}); } catch (_) {}

refreshLabels(); connect();
window.__vc = { cfg, DEFAULTS };
})();
