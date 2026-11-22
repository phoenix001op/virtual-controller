(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// ---------------------------------------------------------------- games
// Control ids: L1 L2 R1 R2 | TRI CIR CRO SQU | DU DD DL DR | T1 T2 T3 (top bar) E1 E2 (right bar) | P1 P2 (pedals, car layout)
//              SU SD SL SR (left stick dirs) | TAP TAP2 (look-zone tap / 2-finger tap)
// Key names come from the server (/keys). To add a game: add an entry here, nothing else.
const GAMES = {
  gta: {
    name: 'GTA Vice City', short: 'GTA VC', note: 'wasmarcade.com/vice-city',
    labels: { T1: 'ESC', T2: 'ENTER', T3: 'HORN', E1: 'CAM', E2: 'RADIO' },
    map: {
      L1: 'Q', L2: 'C', R1: 'E', R2: 'MOUSE_LEFT',
      TRI: 'F', CIR: 'SHIFT', CRO: 'SPACE', SQU: 'CTRL',
      DU: 'UP', DD: 'DOWN', DL: 'LEFT', DR: 'RIGHT',
      T1: 'ESC', T2: 'ENTER', T3: 'H', E1: 'V', E2: 'R',
      SU: 'W', SD: 'S', SL: 'A', SR: 'D', TAP: 'MOUSE_LEFT', TAP2: 'MOUSE_RIGHT',
    },
  },
  mc: {
    name: 'Minecraft', short: 'MINECRAFT', note: 'wasmarcade.com/minecraft (Java 1.8.8)',
    labels: { T1: 'PAUSE', T2: 'ENTER', T3: 'CHAT', E1: 'VIEW', E2: 'DROP' },
    map: {
      L1: 'WHEEL_UP', L2: 'MOUSE_RIGHT', R1: 'WHEEL_DOWN', R2: 'MOUSE_LEFT',
      TRI: 'E', CIR: 'SHIFT', CRO: 'SPACE', SQU: 'CTRL',
      DU: '2', DD: '4', DL: '1', DR: '3',
      T1: 'ESC', T2: 'ENTER', T3: 'T', E1: 'F5', E2: 'Q',
      SU: 'W', SD: 'S', SL: 'A', SR: 'D', TAP: 'MOUSE_LEFT', TAP2: 'MOUSE_RIGHT',
    },
  },
};
GAMES.car = {
  name: 'Car game', short: 'CAR', layout: 'car', note: 'Steering wheel, gas, brake, handbrake, nitro…',
  labels: { L1: 'GEAR ▼', L2: 'LIGHTS', R1: 'GEAR ▲', R2: 'RESET', TRI: 'NITRO', SQU: 'HORN', CIR: 'LOOK BACK', CRO: 'HAND BRAKE',
            T1: 'PAUSE', T2: 'ENTER', T3: 'EXIT CAR', E1: 'CAMERA', E2: 'RADIO', P1: 'BRAKE', P2: 'GAS', RV: 'REVERSE' },
  map: {
    L1: 'Q', L2: 'L', R1: 'E', R2: 'R', TRI: 'SHIFT', CIR: 'B', CRO: 'SPACE', SQU: 'H',
    DU: 'UP', DD: 'DOWN', DL: 'LEFT', DR: 'RIGHT', T1: 'ESC', T2: 'ENTER', T3: 'F', E1: 'C', E2: 'V',
    P1: 'S', P2: 'W', RV: 'S', SL: 'A', SR: 'D', TAP: 'MOUSE_LEFT', TAP2: 'MOUSE_RIGHT',
  },
};
const TITLES = {
  L1: 'L1', L2: 'L2', R1: 'R1', R2: 'R2', TRI: '△ Triangle', CIR: '○ Circle', CRO: '✕ Cross', SQU: '□ Square',
  DU: 'D-pad up', DD: 'D-pad down', DL: 'D-pad left', DR: 'D-pad right',
  SU: 'Stick up', SD: 'Stick down', SL: 'Stick left', SR: 'Stick right',
  TAP: 'Look-area tap', TAP2: 'Look-area 2-finger tap',
};
const SHORT = { SPACE: 'SPC', MOUSE_LEFT: 'LMB', MOUSE_RIGHT: 'RMB', MOUSE_MIDDLE: 'MMB', WHEEL_UP: 'WHEEL▲',
  WHEEL_DOWN: 'WHEEL▼', PAGEUP: 'PGUP', PAGEDOWN: 'PGDN', BACKSPACE: 'BKSP', UP: '↑', DOWN: '↓', LEFT: '←',
  RIGHT: '→', ENTER: 'ENT', CAPSLOCK: 'CAPS', INSERT: 'INS', DELETE: 'DEL', COMMA: ',', PERIOD: '.',
  SLASH: '/', SEMICOLON: ';', QUOTE: "'", LBRACKET: '[', RBRACKET: ']', MINUS: '-', EQUALS: '=', BACKSLASH: '\\',
  BACKTICK: '`', RSHIFT: 'R-SHIFT', RCTRL: 'R-CTRL', RALT: 'R-ALT' };
const short = n => (n ? SHORT[n] || n : '—');
const FALLBACK_GROUPS = [['Letters', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')], ['Mouse', ['MOUSE_LEFT', 'MOUSE_RIGHT', 'MOUSE_MIDDLE', 'WHEEL_UP', 'WHEEL_DOWN']],
  ['Special', ['SPACE', 'ENTER', 'ESC', 'TAB', 'SHIFT', 'CTRL', 'ALT', 'UP', 'DOWN', 'LEFT', 'RIGHT']], ['Numbers', '0123456789'.split('')]];

// ---------------------------------------------------------------- saved config
const LS = 'vc.controller.v2';
let cfg = { game: 'gta', over: { gta: {}, mc: {}, car: {} }, sens: 2, stick: 1, invert: false, haptic: true, labels: true, code: '' };
try {
  let s = localStorage.getItem(LS);
  if (!s) { const o = JSON.parse(localStorage.getItem('vc.controller.v1') || '{}'); delete o.map; s = JSON.stringify(o); }
  const j = JSON.parse(s || '{}');
  cfg = { ...cfg, ...j, over: { gta: {}, mc: {}, car: {}, ...(j.over || {}) } };
} catch (_) {}
if (!GAMES[cfg.game]) cfg.game = 'gta';
const save = () => { try { localStorage.setItem(LS, JSON.stringify(cfg)); } catch (_) {} };
const urlCode = new URLSearchParams(location.search).get('code');
if (urlCode && /^[A-Za-z0-9]{6,8}$/.test(urlCode)) cfg.code = urlCode.toUpperCase();

const game = () => GAMES[cfg.game];
const keyOf = id => { const o = cfg.over[cfg.game] || {}; return id in o ? o[id] : game().map[id]; };
const setKey = (id, name) => { (cfg.over[cfg.game] = cfg.over[cfg.game] || {})[id] = name; save(); refreshLabels(); };
const titleOf = id => (game().labels[id] ? game().labels[id] + ' button' : TITLES[id] || id);

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
        showPair(d.wait ? 'Too many wrong tries — wait a minute.' : 'Wrong code, or the laptop program is not running.');
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
let reverse = false;       // car layout: while on, the GAS pedal drives backwards (sends the REVERSE key)
const active = new Set();   // control ids currently held (buttons, tap pulses)
const sticks = new Set();   // left-stick direction ids currently held
function sendKeys(force) {
  const set = new Set();
  for (const id of active) { const k = keyOf(id === 'P2' && reverse ? 'RV' : id); if (k) set.add(k); }
  for (const id of sticks) { const k = keyOf(id); if (k) set.add(k); }
  const keys = [...set].sort(), sig = keys.join(',');
  if (sig === lastSig && !force) return;
  lastSig = sig;
  tx({ t: 'k', keys });
}
let stickReset = null, lookReset = null, wheelReset = null;
function releaseAll(notify = true) {
  active.clear(); sticks.clear();
  $$('.c.on').forEach(el => el.classList.remove('on'));
  stickReset && stickReset(); lookReset && lookReset(); wheelReset && wheelReset();
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
$$('.shoulder,.small,.dp,.face,.pedal').forEach(bindButton);

// ---------------------------------------------------------------- floating joystick helper
// Places a ring where the finger lands and reports the finger offset (in ring radii) to callbacks.
function floatingStick(zone, ring, knob, { onStart, onMove, onEnd }) {
  let pid = null, cx = 0, cy = 0, R = 1;
  const offset = e => {
    const r = zone.getBoundingClientRect();
    const dx = e.clientX - (r.left + cx), dy = e.clientY - (r.top + cy);
    return { dx, dy, dist: Math.hypot(dx, dy), R };
  };
  const draw = o => {
    const k = Math.min(o.dist, R * 0.62) / (o.dist || 1);
    knob.style.transform = `translate3d(${o.dx * k}px,${o.dy * k}px,0)`;
  };
  zone.addEventListener('pointerdown', e => {
    if (remap || pid !== null || e.target.closest('.sub')) return;
    e.preventDefault(); pid = e.pointerId; zone.setPointerCapture(pid);
    const r = zone.getBoundingClientRect(); R = ring.offsetWidth / 2;
    cx = Math.min(Math.max(e.clientX - r.left, R), Math.max(R, r.width - R));
    cy = Math.min(Math.max(e.clientY - r.top, R), Math.max(R, r.height - R));
    ring.style.left = cx + 'px'; ring.style.top = cy + 'px'; ring.classList.add('live');
    buzz(); onStart && onStart(e);
    const o = offset(e); draw(o); onMove(o);
  });
  zone.addEventListener('pointermove', e => { if (e.pointerId === pid) { const o = offset(e); draw(o); onMove(o); } });
  const end = e => { if (e.pointerId === pid) { reset(); onEnd && onEnd(e); } };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => zone.addEventListener(ev, end));
  const reset = () => { pid = null; ring.classList.remove('live'); ring.style.left = ''; ring.style.top = ''; knob.style.transform = ''; };
  return reset;
}

// ---------------------------------------------------------------- left stick (8-way -> keys)
(() => {
  const DIRS = [['SR'], ['SU', 'SR'], ['SU'], ['SU', 'SL'], ['SL'], ['SD', 'SL'], ['SD'], ['SD', 'SR']];
  const reset = floatingStick($('#stickzone'), $('#stick'), $('#knob'), {
    onMove: ({ dx, dy, dist, R }) => {
      const next = new Set();
      if (dist > R * 0.28) {
        const ang = Math.atan2(-dy, dx) * 180 / Math.PI;
        DIRS[(Math.round(ang / 45) + 8) % 8].forEach(d => next.add(d));
      }
      if (next.size !== sticks.size || [...next].some(d => !sticks.has(d))) {
        sticks.clear(); next.forEach(d => sticks.add(d)); sendKeys();
      }
    },
    onEnd: () => { sticks.clear(); sendKeys(); },
  });
  stickReset = () => { reset(); sticks.clear(); };
})();

// reverse toggle (car layout): tap to switch GAS between forward and backward
const revBtn = $('#revbtn');
function updateRev() {
  revBtn.classList.toggle('on', reverse);
  const gas = $('[data-id="P2"]'), b = gas.querySelector(':scope > b'), k = gas.querySelector(':scope > .kb');
  b.textContent = reverse ? 'REVERSING' : (game().labels.P2 || 'GAS'); k.textContent = short(keyOf(reverse ? 'RV' : 'P2'));
}
revBtn.addEventListener('pointerdown', e => {
  if (remap) return;
  e.preventDefault(); reverse = !reverse; buzz(); updateRev(); sendKeys();
});

// ---------------------------------------------------------------- steering wheel (car layout): drag sideways -> A / D
(() => {
  const zone = $('#wheelzone'), wheel = $('#wheel');
  let pid = null, x0 = 0;
  const steer = v => {
    wheel.style.transform = `rotate(${v * 110}deg)`;
    const want = new Set(); if (v < -0.18) want.add('SL'); else if (v > 0.18) want.add('SR');
    if (want.size !== sticks.size || [...want].some(d => !sticks.has(d))) { sticks.clear(); want.forEach(d => sticks.add(d)); sendKeys(); }
  };
  zone.addEventListener('pointerdown', e => {
    if (remap || pid !== null || e.target.closest('.wk')) return;
    e.preventDefault(); pid = e.pointerId; zone.setPointerCapture(pid); x0 = e.clientX; zone.classList.add('live'); buzz();
  });
  zone.addEventListener('pointermove', e => { if (e.pointerId === pid) steer(Math.max(-1, Math.min(1, (e.clientX - x0) / (zone.clientWidth * 0.28)))); });
  const end = e => { if (e.pointerId === pid) { wheelReset(); sticks.clear(); sendKeys(); } };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => zone.addEventListener(ev, end));
  wheelReset = () => { pid = null; zone.classList.remove('live'); wheel.style.transform = ''; sticks.clear(); };
})();

// ---------------------------------------------------------------- look joystick (continuous mouse movement)
const LOOK_SPEED = 500;      // mouse px per second at full deflection, per 1.0 of "Look speed"
const LOOK_DEADZONE = 0.12;
(() => {
  const zone = $('#lookzone');
  let vx = 0, vy = 0, on = false, raf = 0, last = 0, rx = 0, ry = 0;
  // tap detection (a short touch with no travel = click; second finger = right click)
  const ptr = new Map(); let t0 = 0, moved = 0, maxN = 0;

  function loop(t) {
    if (!on) { raf = 0; return; }
    const dt = Math.min(0.05, (t - last) / 1000); last = t;
    const mag = Math.min(1, Math.hypot(vx, vy));
    if (mag > LOOK_DEADZONE) {
      const k = Math.pow((mag - LOOK_DEADZONE) / (1 - LOOK_DEADZONE), 1.4) * LOOK_SPEED * cfg.sens;
      rx += (vx / mag) * k * dt; ry += (vy / mag) * k * dt * (cfg.invert ? -1 : 1);
      const ix = Math.trunc(rx), iy = Math.trunc(ry); rx -= ix; ry -= iy;
      if (ix || iy) sendMove(ix, iy);
    }
    raf = requestAnimationFrame(loop);
  }
  const reset = floatingStick(zone, $('#look'), $('#lknob'), {
    onStart: () => { on = true; vx = vy = rx = ry = 0; last = performance.now(); if (!raf) raf = requestAnimationFrame(loop); },
    onMove: ({ dx, dy, R }) => { vx = dx / (R * 0.8); vy = dy / (R * 0.8); },
    onEnd: () => { on = false; vx = vy = 0; },
  });
  lookReset = () => { reset(); on = false; vx = vy = 0; ptr.clear(); };

  // extra pointers (2nd finger) and tap bookkeeping run alongside the stick
  zone.addEventListener('pointerdown', e => {
    if (remap || e.target.closest('.sub')) return;
    if (!ptr.size) { t0 = performance.now(); moved = 0; maxN = 0; }
    ptr.set(e.pointerId, { x: e.clientX, y: e.clientY }); maxN = Math.max(maxN, ptr.size);
  });
  zone.addEventListener('pointermove', e => {
    const p = ptr.get(e.pointerId); if (!p) return;
    moved += Math.abs(e.clientX - p.x) + Math.abs(e.clientY - p.y); p.x = e.clientX; p.y = e.clientY;
  });
  const up = e => {
    if (!ptr.delete(e.pointerId) || ptr.size) return;
    if (e.type === 'pointerup' && performance.now() - t0 < 240 && moved < 10) pulse(maxN >= 2 ? 'TAP2' : 'TAP');
  };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => zone.addEventListener(ev, up));
})();

// ---------------------------------------------------------------- labels / remap UI
function refreshLabels() {
  const g = game();
  $$('[data-id]').forEach(el => {
    const id = el.dataset.id, k = el.querySelector(':scope > .kb'); if (k) k.textContent = short(keyOf(id));
    const b = el.querySelector(':scope > b');
    if (b) { if (el.dataset.def === undefined) el.dataset.def = b.textContent; b.textContent = g.labels[id] ?? el.dataset.def; }
  });
  $('#tap1').textContent = short(keyOf('TAP')); $('#tap2').textContent = short(keyOf('TAP2'));
  $('#btn-game').textContent = g.short;
  document.body.classList.toggle('car', g.layout === 'car');
  document.body.classList.toggle('nolabels', !cfg.labels);
  document.documentElement.style.setProperty('--stick', cfg.stick);
  updateRev();
}
let groups = FALLBACK_GROUPS, pickId = null;
fetch('/keys').then(r => r.json()).then(d => { groups = d.groups; }).catch(() => {});

const picker = $('#picker');
function openPicker(id) {
  pickId = id;
  $('#picktitle').textContent = `${game().short} · ${titleOf(id)}: ${short(keyOf(id))}`;
  const grid = $('#pickgrid'); grid.innerHTML = '';
  for (const [name, keys] of groups) {
    const h = document.createElement('div'); h.className = 'grpname'; h.textContent = name;
    const w = document.createElement('div'); w.className = 'chips';
    for (const k of keys) {
      const b = document.createElement('button'); b.className = 'chip' + (keyOf(id) === k ? ' cur' : '');
      b.textContent = short(k); b.dataset.k = k; w.appendChild(b);
    }
    grid.append(h, w);
  }
  picker.hidden = false;
}
const closePicker = () => { picker.hidden = true; pickId = null; };
function assign(name) { if (pickId) setKey(pickId, name); closePicker(); }
$('#pickgrid').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) assign(b.dataset.k); });
$('#picknone').onclick = () => assign('');
$('#pickreset').onclick = () => { if (pickId) { delete cfg.over[cfg.game][pickId]; save(); refreshLabels(); } closePicker(); };
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

// ---------------------------------------------------------------- game picker
const gamesBox = $('#games');
function setGame(g) {
  if (!GAMES[g]) return;
  reverse = false; releaseAll(); cfg.game = g; save(); refreshLabels();
}
function openGames() {
  const list = $('#gamelist'); list.innerHTML = '';
  for (const [id, g] of Object.entries(GAMES)) {
    const b = document.createElement('button'); b.className = 'gamecard' + (id === cfg.game ? ' cur' : '');
    b.dataset.g = id; b.innerHTML = `<b></b><span></span>`;
    b.firstChild.textContent = g.name; b.lastChild.textContent = g.note;
    list.appendChild(b);
  }
  gamesBox.hidden = false;
}
$('#gamelist').addEventListener('click', e => { const b = e.target.closest('.gamecard'); if (b) { setGame(b.dataset.g); gamesBox.hidden = true; } });
$('#btn-game').onclick = openGames;
$('#gameclose').onclick = () => { gamesBox.hidden = true; };

// ---------------------------------------------------------------- settings
const settings = $('#settings');
function syncSettings() {
  $('#s-sens').value = cfg.sens; $('#o-sens').textContent = cfg.sens.toFixed(1);
  $('#s-stick').value = cfg.stick; $('#o-stick').textContent = cfg.stick.toFixed(2);
  $('#s-invert').checked = cfg.invert; $('#s-haptic').checked = cfg.haptic; $('#s-labels').checked = cfg.labels;
  $('#set-reset').textContent = `Reset ${game().short} keys to default`;
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
    const base = label();
    if (!armed) { armed = setTimeout(() => { armed = 0; btn.textContent = label(); }, 3000); btn.textContent = 'Tap again to confirm'; return; }
    clearTimeout(armed); armed = 0; fn(); btn.textContent = label();
  };
}
twoTap($('#set-reset'), () => `Reset ${game().short} keys to default`, () => { cfg.over[cfg.game] = {}; save(); refreshLabels(); });
twoTap($('#set-forget'), () => 'Forget pairing code', () => { cfg.code = ''; save(); settings.hidden = true; showPair(''); });

// ---------------------------------------------------------------- pairing
const pairBox = $('#pair'), codeIn = $('#code');
function showPair(msg) { pairBox.hidden = false; $('#pairmsg').textContent = msg || ''; codeIn.value = ''; }
function hidePair() { pairBox.hidden = true; }
function submitCode() {
  const c = codeIn.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  if (c.length < 6) { $('#pairmsg').textContent = 'Enter the whole code.'; return; }
  pendingCode = c; raw({ t: 'pair', code: c });
}
$('#pairgo').onclick = submitCode;
codeIn.addEventListener('input', () => { codeIn.value = codeIn.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 8); });
codeIn.addEventListener('keydown', e => { if (e.key === 'Enter') submitCode(); });

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
window.__vc = { cfg, keyOf, setKey, setGame, GAMES };
})();
