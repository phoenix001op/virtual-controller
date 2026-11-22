# Project notes (for continuing work in a later session)

## Architecture
* `server.py` – aiohttp app. WebSocket `/ws?role=mobile|laptop`. Protocol (JSON text):
  * phone → server: `{t:"pair",code}`, `{t:"k",keys:[...]}` (FULL set of held key names),
    `{t:"m",x,y}` (relative mouse delta), `{t:"p",ts}` ping, `{t:"r"}` release all
  * server → phone: `{t:"paired",ok}`, `{t:"pong",ts}`; server → laptop: `{t:"state",phone,keys}`
  * Key names come from `KEY_GROUPS` in server.py (also served at `/keys`, used by the remap picker).
    Mouse buttons are `MOUSE_LEFT/RIGHT/MIDDLE`; `WHEEL_UP/DOWN` = one notch per press.
  * `Injector` diffs full key sets into press/release and releases everything on disconnect.
  * Backends: `PynputBackend` (real) and `DryRunBackend` (tests).
  * Pairing code only returned to local requests (`is_local`); 5 wrong tries => 30 s lockout.
* `web/mobile.{html,css,js}` – controller. Games are defined in `GAMES` (mobile.js): per-game default key map + top-bar labels;
  user remaps stored per game in `localStorage['vc.controller.v2'].over[game]`. Control ids: L1 L2 R1 R2 TRI CIR CRO SQU DU DD DL DR
  T1 T2 T3 (top bar) E1 E2 (right bar) SU SD SL SR (left stick) TAP TAP2 (look-area taps) P1 P2 (pedals). `layout:'car'` games get body.car (wheel + pedals instead of stick + look area). Look stick = floating stick that
  integrates mouse deltas per animation frame (speed ~ deflection^1.4, deadzone 0.12). All sizes in `vh` so it fits any landscape phone.
  Config (key map, sensitivity...) lives in `localStorage['vc.controller.v1']`. `DEFAULTS` in
  mobile.js is the default key map; control ids are the `data-id` attributes in mobile.html.
* `web/laptop.html` – pairing code, status, key list, test pad.

## Tests (all passing when last run)
* `tests/test_ui.py` – 92 checks vs `python server.py --dry-run --code 123456`
  (every button in both games, 8-way stick, look stick direction/speed/deadzone/stop, taps, 3-finger multitouch,
  car layout (wheel/pedals), game switching, per-game remap + persistence, release on disconnect, layouts 800x360 / 800x300 / 851x393 / 667x375).
  Run: `pip install playwright`, then `python tests/test_ui.py` (set `CHROME=/path/to/chrome` if needed).
* Real injection was checked on Linux with Xvfb + pynput: keys held/released, relative mouse move,
  mouse button, release on disconnect all correct.

## Not verified / ideas
* NOT tested on real Windows + real phone + the actual game. Weapon-switch default (Q/E) is a guess;
  the user can remap it in the app.
* Possible next steps: cheat-code typer, saved layout profiles / export-import, more games (GTA III, GTA V, Simpsons Hit & Run are on wasmarcade), drag-lock,
  QR code on the laptop page, PWA manifest for browser-bar-free fullscreen.
