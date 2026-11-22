"""Online relay: host this on any server (Render, Railway, Fly, a VPS...).

    python relay.py              # listens on $PORT (default 8080)

It serves the phone page (/mobile) and laptop page (/laptop) and connects phone <-> laptop agent by a pairing
code, so both can be on ANY network. It never presses keys itself: the small program `agent.py` running on the
laptop does that. Put the relay behind HTTPS (all hosts above do this for you).
"""
import json
import os
import re
import socket
import time
from pathlib import Path

from aiohttp import web, WSMsgType

from server import KEY_GROUPS

WEB = Path(__file__).parent / "web"
CODE_RE = re.compile(r"^[A-Z0-9]{6,8}$")
NOCACHE = {"Cache-Control": "no-store"}
MAX_FAILS, LOCK_SECONDS = 5, 60
GLOBAL_FAILS_PER_MIN = 120


class Room:
    def __init__(self, code, agent):
        self.code, self.agent, self.phone, self.viewers = code, agent, None, set()


def client_ip(req):
    # behind a hosting proxy the LAST X-Forwarded-For entry is the one the proxy added (not spoofable)
    xff = req.headers.get("X-Forwarded-For", "")
    return xff.split(",")[-1].strip() if xff else (req.remote or "?")


def nodelay(req):
    sock = req.transport.get_extra_info("socket") if req.transport else None
    if sock is not None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass


def throttled(app, ip):
    now = time.time()
    st = app["st"]
    if now - st["gwin"] > 60:
        st["gwin"], st["gfails"] = now, 0
    if st["gfails"] > GLOBAL_FAILS_PER_MIN:
        return True
    return now < st["fails"].get(ip, (0, 0))[1]


def note_fail(app, ip):
    st = app["st"]
    n, _ = st["fails"].get(ip, (0, 0))
    n += 1
    st["gfails"] += 1
    st["fails"][ip] = (n, time.time() + (LOCK_SECONDS if n >= MAX_FAILS else 0))
    if len(st["fails"]) > 5000:
        st["fails"].clear()


async def send(ws, obj):
    try:
        await ws.send_str(obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":")))
    except Exception:
        pass


# ----------------------------------------------------------------------------- pages
def page(name):
    async def h(req):
        return web.FileResponse(WEB / name, headers=NOCACHE)
    return h


async def index(req):
    ua = req.headers.get("User-Agent", "")
    mobile = any(k in ua for k in ("Mobi", "Android", "iPhone", "iPad"))
    return await page("mobile.html" if mobile else "laptop.html")(req)


async def status(req):
    return web.json_response({"hosted": True}, headers=NOCACHE)


async def keys(req):
    return web.json_response({"groups": KEY_GROUPS}, headers=NOCACHE)


async def health(req):
    return web.Response(text="ok")


# ----------------------------------------------------------------------------- laptop agent
async def agent_ws(req):
    app = req.app
    code = req.query.get("code", "")
    if not CODE_RE.match(code):
        raise web.HTTPBadRequest(text="bad code")
    if code in app["rooms"]:
        raise web.HTTPConflict(text="code already in use")
    ws = web.WebSocketResponse(heartbeat=10, compress=False, max_msg_size=16384)
    await ws.prepare(req)
    nodelay(req)
    room = Room(code, ws)
    app["rooms"][code] = room
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            if msg.data.startswith('{"t":"state"'):
                for v in list(room.viewers):
                    await send(v, msg.data)
            elif room.phone is not None:
                await send(room.phone, msg.data)
    finally:
        app["rooms"].pop(code, None)
        for w in [room.phone, *room.viewers]:
            if w is not None:
                try:
                    await w.close()
                except Exception:
                    pass
    return ws


# ----------------------------------------------------------------------------- phone / laptop page
async def client_ws(req):
    app = req.app
    role = req.query.get("role", "mobile")
    ip = client_ip(req)
    ws = web.WebSocketResponse(heartbeat=10, compress=False, max_msg_size=8192)
    await ws.prepare(req)
    nodelay(req)

    if role == "laptop":  # read-only viewer: shows phone status + held keys
        code = req.query.get("code", "").upper()
        room = app["rooms"].get(code)
        if throttled(app, ip) or not room or not CODE_RE.match(code):
            note_fail(app, ip)
            await send(ws, {"t": "denied"})
            await ws.close()
            return ws
        room.viewers.add(ws)
        await send(room.agent, {"t": "snap"})
        try:
            async for _ in ws:
                pass
        finally:
            room.viewers.discard(ws)
        return ws

    room = None
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            if room is not None:
                if app["rooms"].get(room.code) is not room:
                    break
                if room.phone is ws:
                    await send(room.agent, msg.data)
                else:
                    break
                continue
            try:
                d = json.loads(msg.data)
            except ValueError:
                continue
            if d.get("t") != "pair":
                continue
            code = str(d.get("code", "")).strip().upper()
            if throttled(app, ip):
                await send(ws, {"t": "paired", "ok": False, "wait": True})
                continue
            r = app["rooms"].get(code) if CODE_RE.match(code) else None
            if r is None:
                note_fail(app, ip)
                await send(ws, {"t": "paired", "ok": False})
                continue
            app["st"]["fails"].pop(ip, None)
            if r.phone is not None and r.phone is not ws:
                try:
                    await r.phone.close()
                except Exception:
                    pass
            room, r.phone = r, ws
            await send(r.agent, {"t": "phone", "on": True})
            await send(ws, {"t": "paired", "ok": True})
    finally:
        if room is not None and room.phone is ws:
            room.phone = None
            await send(room.agent, {"t": "phone", "on": False})
    return ws


def make_app():
    app = web.Application()
    app["rooms"] = {}
    app["st"] = {"fails": {}, "gwin": 0, "gfails": 0}
    app.router.add_get("/", index)
    app.router.add_get("/mobile", page("mobile.html"))
    app.router.add_get("/laptop", page("laptop.html"))
    app.router.add_get("/status", status)
    app.router.add_get("/keys", keys)
    app.router.add_get("/health", health)
    app.router.add_get("/ws", client_ws)
    app.router.add_get("/agent", agent_ws)
    app.router.add_static("/static/", WEB, show_index=False, append_version=False)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"relay listening on :{port}")
    web.run_app(make_app(), host="0.0.0.0", port=port, print=None)
