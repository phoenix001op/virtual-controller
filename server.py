import secrets, socket
from pathlib import Path
from aiohttp import web, WSMsgType
from pynput.keyboard import Controller, Key

ROOT=Path(__file__).parent
CODE=f"{secrets.randbelow(1000000):06d}"
kb=Controller()
held=set()
KEYS={"W":"w","A":"a","S":"s","D":"d","CTRL":Key.ctrl,"SHIFT":Key.shift,
"SPACE":Key.space,"ENTER":Key.enter,"ESC":Key.esc,"F":"f","C":"c","H":"h",
"V":"v","R":"r","E":"e","Q":"q","HOME":Key.home,"INSERT":Key.insert,
"DELETE":Key.delete,"PAGEUP":Key.page_up,"PAGEDOWN":Key.page_down,
"UP":Key.up,"DOWN":Key.down,"LEFT":Key.left,"RIGHT":Key.right}
def release_all():
    for n in list(held):
        try: kb.release(KEYS[n])
        except: pass
        held.discard(n)
def update(names):
    wanted={n for n in names if n in KEYS}
    for n in held-wanted:
        kb.release(KEYS[n]); held.discard(n)
    for n in wanted-held:
        kb.press(KEYS[n]); held.add(n)
def ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try: s.connect(("8.8.8.8",80)); return s.getsockname()[0]
    except: return "127.0.0.1"
    finally: s.close()
async def page(req): return web.FileResponse(ROOT/"laptop.html")
async def mobile(req): return web.FileResponse(ROOT/"mobile.html")
async def status(req): return web.json_response({"code":CODE})
async def ws_handler(req):
    role=req.query.get("role")
    ws=web.WebSocketResponse(heartbeat=20); await ws.prepare(req)
    if role=="laptop":
        try:
            async for msg in ws: pass
        finally: release_all()
    elif role=="mobile":
        paired=False
        try:
            async for msg in ws:
                if msg.type!=WSMsgType.TEXT: continue
                import json
                try: data=json.loads(msg.data)
                except: continue
                if data.get("type")=="pair":
                    paired=str(data.get("code",""))==CODE
                    await ws.send_json({"type":"paired","ok":paired})
                elif paired and data.get("type")=="keys": update(data.get("keys",[]))
        finally: release_all()
    return ws
app=web.Application()
app.router.add_get("/",page); app.router.add_get("/laptop",page)
app.router.add_get("/mobile",mobile); app.router.add_get("/status",status)
app.router.add_get("/ws",ws_handler)
if __name__=="__main__":
    print("Laptop: http://localhost:8765/laptop")
    print(f"Phone:  http://{ip()}:8765/mobile")
    print(f"Pairing code: {CODE}")
    web.run_app(app,host="0.0.0.0",port=8765)
