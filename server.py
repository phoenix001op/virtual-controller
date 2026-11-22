"""Virtual controller receiver.

Runs on the laptop that is running the game. The phone (web/mobile.html) sends
key / mouse events over a WebSocket; this server replays them as real keyboard
and mouse input with pynput.

    python server.py                 # normal use
    python server.py --code 123456   # fixed pairing code (no re-typing after restart)
    python server.py --dry-run       # no real input, just log events (for testing)
"""
import argparse
import asyncio
import hmac
import json
import secrets
import socket
import sys
import time
from pathlib import Path

from aiohttp import web, WSMsgType

ROOT = Path(__file__).parent
WEB = ROOT / "web"

# ---------------------------------------------------------------------------
# Key catalogue (single source of truth; the phone fetches it from /keys)
# ---------------------------------------------------------------------------
LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
DIGITS = [str(i) for i in range(10)]
FKEYS = [f"F{i}" for i in range(1, 13)]
SPECIAL = ["SPACE", "ENTER", "ESC", "TAB", "BACKSPACE", "SHIFT", "CTRL", "ALT",
           "RSHIFT", "RCTRL", "RALT", "CAPSLOCK"]
NAV = ["UP", "DOWN", "LEFT", "RIGHT", "HOME", "END", "INSERT", "DELETE",
       "PAGEUP", "PAGEDOWN"]
SYMBOLS = {"COMMA": ",", "PERIOD": ".", "SLASH": "/", "SEMICOLON": ";",
           "QUOTE": "'", "LBRACKET": "[", "RBRACKET": "]", "MINUS": "-",
           "EQUALS": "=", "BACKSLASH": "\\", "BACKTICK": "`"}
MOUSE = ["MOUSE_LEFT", "MOUSE_RIGHT", "MOUSE_MIDDLE"]
WHEEL = ["WHEEL_UP", "WHEEL_DOWN"]  # momentary: one notch per press

KEY_GROUPS = [
    ("Letters", LETTERS), ("Mouse", MOUSE + WHEEL), ("Special", SPECIAL),
    ("Arrows / nav", NAV), ("Numbers", DIGITS), ("F-keys", FKEYS),
    ("Symbols", list(SYMBOLS)),
]
ALL_NAMES = {n for _, names in KEY_GROUPS for n in names}


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class DryRunBackend:
    """Records events instead of injecting them (tests / no display)."""

    names = ALL_NAMES

    def __init__(self):
        self.events = []

    def _log(self, *e):
        self.events.append((round(time.time(), 4),) + e)
        del self.events[:-5000]

    def key_down(self, n): self._log("down", n)
    def key_up(self, n): self._log("up", n)
    def move(self, dx, dy): self._log("move", dx, dy)
    def wheel(self, notches): self._log("wheel", notches)


class PynputBackend:
    def __init__(self):
        from pynput.keyboard import Controller as KC, Key
        from pynput.mouse import Controller as MC, Button

        self.kb, self.mouse = KC(), MC()
        self.Button = Button
        k = {}
        for c in LETTERS:
            k[c] = c.lower()
        for d in DIGITS:
            k[d] = d
        for f in FKEYS:
            k[f] = getattr(Key, f.lower(), None)
        special = {"SPACE": "space", "ENTER": "enter", "ESC": "esc", "TAB": "tab",
                   "BACKSPACE": "backspace", "SHIFT": "shift_l", "CTRL": "ctrl_l",
                   "ALT": "alt_l", "RSHIFT": "shift_r", "RCTRL": "ctrl_r",
                   "RALT": "alt_r", "CAPSLOCK": "caps_lock",
                   "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
                   "HOME": "home", "END": "end", "INSERT": "insert",
                   "DELETE": "delete", "PAGEUP": "page_up", "PAGEDOWN": "page_down"}
        for name, attr in special.items():
            k[name] = getattr(Key, attr, None)
        k.update(SYMBOLS)
        self.keys = {n: v for n, v in k.items() if v is not None}
        self.buttons = {"MOUSE_LEFT": Button.left, "MOUSE_RIGHT": Button.right,
                        "MOUSE_MIDDLE": Button.middle}
        self.names = set(self.keys) | set(self.buttons) | set(WHEEL)

    def key_down(self, n):
        if n in self.buttons:
            self.mouse.press(self.buttons[n])
        elif n in self.keys:
            self.kb.press(self.keys[n])

    def key_up(self, n):
        if n in self.buttons:
            self.mouse.release(self.buttons[n])
        elif n in self.keys:
            self.kb.release(self.keys[n])

    def move(self, dx, dy):
        self.mouse.move(dx, dy)  # relative SendInput / XTest move

    def wheel(self, notches):
        self.mouse.scroll(0, notches)


class Injector:
    """Tracks held keys and turns 'full key state' messages into press/release."""

    def __init__(self, backend):
        self.b = backend
        self.held = set()

    def set_keys(self, names):
        wanted = {n for n in names if isinstance(n, str) and n in self.b.names}
        for n in sorted(self.held - wanted):
            self._up(n)
        for n in sorted(wanted - self.held):
            self._down(n)
        return sorted(self.held)

    def _down(self, n):
        self.held.add(n)
        if n == "WHEEL_UP":
            self.b.wheel(1)
        elif n == "WHEEL_DOWN":
            self.b.wheel(-1)
        else:
            self.b.key_down(n)

    def _up(self, n):
        self.held.discard(n)
        if n not in WHEEL:
            try:
                self.b.key_up(n)
            except Exception:
                pass

    def move(self, dx, dy):
        try:
            dx, dy = int(dx), int(dy)
        except (TypeError, ValueError):
            return
        dx, dy = max(-3000, min(3000, dx)), max(-3000, min(3000, dy))
        if dx or dy:
            self.b.move(dx, dy)

    def release_all(self):
        for n in sorted(self.held):
            self._up(n)
        self.held.clear()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def is_local(req):
    remote = req.remote or ""
    if remote in ("127.0.0.1", "::1"):
        return True
    sock = req.transport.get_extra_info("sockname") if req.transport else None
    return bool(sock) and remote == sock[0]  # laptop opening its own LAN address


def nodelay(req):
    sock = req.transport.get_extra_info("socket") if req.transport else None
    if sock is not None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass


NOCACHE = {"Cache-Control": "no-store"}


def file_page(name):
    async def handler(req):
        return web.FileResponse(WEB / name, headers=NOCACHE)
    return handler


async def index(req):
    return await file_page("laptop.html" if is_local(req) else "mobile.html")(req)


async def status(req):
    if is_local(req):
        return web.json_response({"code": req.app["code"], "dry": req.app["dry"],
                                  "port": req.app["port"], "ip": lan_ip()},
                                 headers=NOCACHE)
    return web.json_response({"ok": True}, headers=NOCACHE)


async def keys_list(req):
    return web.json_response({"groups": KEY_GROUPS}, headers=NOCACHE)


async def debug_events(req):
    if not req.app["dry"]:
        raise web.HTTPNotFound()
    b = req.app["injector"].b
    out = b.events[:]
    if req.query.get("clear"):
        b.events.clear()
    return web.json_response(out)


async def broadcast(app, **msg):
    data = json.dumps(msg)
    for ws in list(app["st"]["laptops"]):
        try:
            await ws.send_str(data)
        except Exception:
            app["st"]["laptops"].discard(ws)


def snapshot(app):
    return {"t": "state", "phone": app["st"]["phone"] is not None,
            "keys": sorted(app["injector"].held)}


async def ws_handler(req):
    app = req.app
    role = req.query.get("role")
    if role == "laptop" and not is_local(req):
        raise web.HTTPForbidden(text="open the laptop page on the laptop")
    ws = web.WebSocketResponse(heartbeat=10, compress=False, max_msg_size=8192)
    await ws.prepare(req)
    nodelay(req)

    if role == "laptop":
        app["st"]["laptops"].add(ws)
        await ws.send_str(json.dumps(snapshot(app)))
        try:
            async for _ in ws:
                pass
        finally:
            app["st"]["laptops"].discard(ws)
        return ws

    inj, ip = app["injector"], req.remote
    paired = False
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                d = json.loads(msg.data)
            except ValueError:
                continue
            t = d.get("t")
            if t == "pair":
                fails, until = app["st"]["fails"].get(ip, (0, 0))
                if time.time() < until:
                    await ws.send_str(json.dumps({"t": "paired", "ok": False, "wait": True}))
                    continue
                paired = hmac.compare_digest(str(d.get("code", "")).strip().upper(), app["code"])
                if paired:
                    app["st"]["fails"].pop(ip, None)
                    old = app["st"]["phone"]
                    if old is not None and old is not ws:
                        inj.release_all()
                        await old.close()
                    app["st"]["phone"] = ws
                    await broadcast(app, **snapshot(app))
                else:
                    fails += 1
                    app["st"]["fails"][ip] = (fails, time.time() + (30 if fails >= 5 else 0))
                await ws.send_str(json.dumps({"t": "paired", "ok": paired}))
            elif not paired or app["st"]["phone"] is not ws:
                continue
            elif t == "k":
                keys = d.get("keys", [])
                if isinstance(keys, list):
                    before = set(inj.held)
                    held = inj.set_keys(keys[:40])
                    if set(held) != before:
                        await broadcast(app, **snapshot(app))
            elif t == "m":
                inj.move(d.get("x", 0), d.get("y", 0))
            elif t == "p":
                await ws.send_str(json.dumps({"t": "pong", "ts": d.get("ts")}))
            elif t == "r":
                inj.release_all()
                await broadcast(app, **snapshot(app))
    finally:
        if app["st"]["phone"] is ws:
            app["st"]["phone"] = None
            inj.release_all()
            await broadcast(app, **snapshot(app))
    return ws


def make_app(backend, code, port, dry=False):
    app = web.Application()
    app["injector"] = Injector(backend)
    app["code"], app["port"], app["dry"] = code, port, dry
    app["st"] = {"phone": None, "laptops": set(), "fails": {}}  # mutable state (aiohttp forbids changing app keys after start)
    app.router.add_get("/", index)
    app.router.add_get("/laptop", file_page("laptop.html"))
    app.router.add_get("/mobile", file_page("mobile.html"))
    app.router.add_get("/status", status)
    app.router.add_get("/keys", keys_list)
    app.router.add_get("/debug/events", debug_events)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/static/", WEB, show_index=False,
                          append_version=False)
    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--code", help="fixed 6-digit pairing code (default: random each run)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do not inject real input; log events at /debug/events")
    a = ap.parse_args()

    if a.code and not (a.code.isdigit() and len(a.code) == 6):
        sys.exit("--code must be exactly 6 digits")
    code = a.code or f"{secrets.randbelow(1000000):06d}"

    if a.dry_run:
        backend = DryRunBackend()
    else:
        try:
            backend = PynputBackend()
        except Exception as e:  # ImportError, or no display on Linux
            sys.exit(f"Could not start keyboard/mouse control ({e}).\n"
                     "Run: python -m pip install -r requirements.txt")

    ip = lan_ip()
    print(f"Laptop page : http://localhost:{a.port}/laptop")
    print(f"Phone page  : http://{ip}:{a.port}/mobile")
    print(f"Pairing code: {code}" + ("   (dry-run: no real input)" if a.dry_run else ""))
    web.run_app(make_app(backend, code, a.port, a.dry_run), host=a.host,
                port=a.port, print=None)


if __name__ == "__main__":
    main()
