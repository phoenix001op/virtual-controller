"""Online-mode test: starts relay.py + agent.py (dry-run) and plays phone / laptop-viewer against them.
Run from the repo root:  python tests/test_relay.py   (needs aiohttp; optional playwright for the page check)"""
import asyncio, json, os, subprocess, sys, tempfile, time
import aiohttp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT, CODE = 8766, "ABCD2345"
BASE = f"http://localhost:{PORT}"
res = []


def check(name, ok, info=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))


def start(args, log):
    return subprocess.Popen([sys.executable, "-u", *args], cwd=ROOT, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                            env={**os.environ, "PORT": str(PORT)})


def events(log):
    return [l.split("event:")[1].split() for l in open(log).read().splitlines() if "event:" in l]


async def recv(ws, t, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            m = await ws.receive(timeout=end - time.time())
        except asyncio.TimeoutError:
            break
        if m.type == aiohttp.WSMsgType.TEXT:
            d = json.loads(m.data)
            if d.get("t") == t:
                return d
        elif m.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
            return None
    return None


async def main():
    tmp = tempfile.mkdtemp()
    relay = start(["relay.py"], f"{tmp}/relay.log")
    await asyncio.sleep(1.5)
    alog = f"{tmp}/agent.log"
    agent = start(["agent.py", "--relay", BASE, "--code", CODE, "--dry-run", "--verbose"], alog)
    await asyncio.sleep(1.5)
    try:
        async with aiohttp.ClientSession() as s:
            check("relay health + status", (await (await s.get(BASE + "/status")).json()).get("hosted") is True)
            codes = [(await s.get(BASE + p)).status for p in ("/mobile", "/laptop", "/static/mobile.js", "/keys")]
            check("pages served", codes == [200] * 4, str(codes))

            # second agent with same code is refused
            dup = subprocess.run([sys.executable, "agent.py", "--relay", BASE, "--code", CODE, "--dry-run"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=15)
            check("duplicate code refused", "already in use" in (dup.stdout + dup.stderr), dup.stdout + dup.stderr)

            # viewer (laptop page) connects with the code
            v = await s.ws_connect(f"ws://localhost:{PORT}/ws?role=laptop&code={CODE}")
            st = await recv(v, "state")
            check("viewer gets state snapshot", st is not None and st["phone"] is False, str(st))

            phone = await s.ws_connect(f"ws://localhost:{PORT}/ws?role=mobile")
            await phone.send_str(json.dumps({"t": "pair", "code": "WRONG123"}))
            r = await recv(phone, "paired")
            check("wrong code rejected", r and r["ok"] is False, str(r))
            await phone.send_str(json.dumps({"t": "k", "keys": ["W"]}))
            await asyncio.sleep(0.3)
            check("unpaired phone cannot press keys", not events(alog))
            await phone.send_str(json.dumps({"t": "pair", "code": CODE.lower()}))
            r = await recv(phone, "paired")
            check("correct code accepted (case-insensitive)", r and r["ok"] is True, str(r))
            st = await recv(v, "state")
            check("viewer sees phone connected", st and st["phone"] is True, str(st))

            await phone.send_str(json.dumps({"t": "k", "keys": ["W", "SPACE"]}))
            await phone.send_str(json.dumps({"t": "m", "x": 5, "y": -3}))
            await asyncio.sleep(0.4)
            ev = events(alog)
            check("keys + mouse reach the agent", ["down", "W"] in ev and ["down", "SPACE"] in ev and ["move", "5", "-3"] in ev, str(ev))
            st = await recv(v, "state")
            check("viewer sees held keys", st and set(st["keys"]) == {"SPACE", "W"}, str(st))
            t0 = time.time()
            await phone.send_str(json.dumps({"t": "p", "ts": 123.5}))
            pong = await recv(phone, "pong")
            check("ping round trip through agent", pong and pong["ts"] == 123.5, str(pong))
            await phone.send_str(json.dumps({"t": "k", "keys": []}))
            await asyncio.sleep(0.3)
            ev = events(alog)
            check("release works", ["up", "W"] in ev and ["up", "SPACE"] in ev, str(ev))

            # phone drops while holding a key => agent releases it
            await phone.send_str(json.dumps({"t": "k", "keys": ["D"]}))
            await asyncio.sleep(0.3)
            await phone.close()
            await asyncio.sleep(0.5)
            check("key released when phone disconnects", ["up", "D"] in events(alog), str(events(alog)))

            # brute-force lock-out
            bad = await s.ws_connect(f"ws://localhost:{PORT}/ws?role=mobile")
            seen_wait = False
            for i in range(8):
                await bad.send_str(json.dumps({"t": "pair", "code": f"ZZZZ{i}99"}))
                r = await recv(bad, "paired")
                seen_wait = seen_wait or bool(r and r.get("wait"))
            await bad.send_str(json.dumps({"t": "pair", "code": CODE}))
            r = await recv(bad, "paired")
            check("brute force is locked out (even with the right code)", seen_wait and r and r["ok"] is False, str(r))
            await bad.close()
    finally:
        agent.terminate(); relay.terminate()

    # real phone page through the relay (optional)
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("(skipping page test: playwright not installed)")
    else:
        relay = start(["relay.py"], f"{tmp}/relay2.log"); await asyncio.sleep(1.5)
        agent = start(["agent.py", "--relay", BASE, "--code", CODE, "--dry-run", "--verbose"], alog); await asyncio.sleep(1.5)
        try:
            async with async_playwright() as p:
                kw = {"executable_path": os.environ["CHROME"]} if os.environ.get("CHROME") else {}
                b = await p.chromium.launch(args=["--no-sandbox"], **kw)
                ctx = await b.new_context(viewport={"width": 800, "height": 360}, has_touch=True, is_mobile=True)
                pg = await ctx.new_page()
                await pg.goto(BASE + "/mobile")
                await pg.fill("#code", "abcd2345"); await pg.click("#pairgo")
                await pg.wait_for_selector("#pair", state="hidden", timeout=5000)
                check("phone page pairs through relay", True)
                await pg.wait_for_function("document.querySelector('#pill').textContent.includes('ms')", timeout=5000)
                cdp = await ctx.new_cdp_session(pg)
                r = await pg.eval_on_selector('[data-id="CRO"]', "e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
                await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": r[0], "y": r[1], "id": 1}]})
                await asyncio.sleep(0.2)
                await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                await asyncio.sleep(0.3)
                ev = events(alog)
                check("tapping SPACE button on the page presses SPACE on the agent", ["down", "SPACE"] in ev and ["up", "SPACE"] in ev, str(ev))
                await b.close()
        finally:
            agent.terminate(); relay.terminate()
    print(f"\n{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)


asyncio.run(main())
