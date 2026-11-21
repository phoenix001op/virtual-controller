"""Phone-page UI test. Start first:  python server.py --dry-run --code 123456
Then:  python tests/test_ui.py   (needs: pip install playwright; playwright install chromium)"""
import asyncio, json, os, sys, tempfile, urllib.request
from playwright.async_api import async_playwright

BASE = "http://localhost:8765"
OUT = os.environ.get("OUT_DIR") or tempfile.mkdtemp(prefix="vc-shots-")  # screenshots go here
CHROME = os.environ.get("CHROME")  # optional path to a Chrome binary

def events(clear=True):
    with urllib.request.urlopen(f"{BASE}/debug/events" + ("?clear=1" if clear else "")) as r:
        return json.load(r)

def summary(ev):
    return [e[1:] for e in ev]

async def main():
    results = []
    def check(name, ok, info=""):
        results.append((name, ok))
        print(("PASS " if ok else "FAIL ") + name + (f"  {info}" if info and not ok else ""))

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]) if CHROME else await p.chromium.launch(args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 800, "height": 360}, device_scale_factor=2,
                                  has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await page.goto(BASE + "/mobile")
        await page.wait_for_selector("#pair:not([hidden])")
        await page.screenshot(path=f"{OUT}/01_pair.png")

        # wrong code, then right code
        await page.fill("#code", "000000")
        await page.wait_for_function("document.querySelector('#pairmsg').textContent.includes('Wrong')")
        check("wrong code rejected", True)
        await page.fill("#code", "123456")
        await page.wait_for_selector("#pair", state="hidden")
        check("pairing with correct code", True)
        await page.wait_for_function("document.querySelector('#pill').textContent.includes('ms')")
        check("latency shown in pill", True)
        await page.screenshot(path=f"{OUT}/02_main.png")

        cdp = await ctx.new_cdp_session(page)
        async def touch(kind, pts):
            await cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})
        async def center(sel):
            r = await page.eval_on_selector(sel, "e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
            return r
        events()  # clear

        # ---- every button: press -> down, release -> up
        expected = {"L1": "Q", "L2": "C", "R1": "E", "R2": "MOUSE_LEFT", "TRI": "F", "CIR": "SHIFT", "CRO": "SPACE",
                    "SQU": "CTRL", "DU": "UP", "DD": "DOWN", "DL": "LEFT", "DR": "RIGHT", "ESC": "ESC",
                    "ENTER": "ENTER", "HORN": "H", "CAM": "V", "RADIO": "R"}
        for bid, key in expected.items():
            x, y = await center(f'[data-id="{bid}"]')
            await touch("touchStart", [{"x": x, "y": y, "id": 1}])
            await page.wait_for_timeout(60)
            await touch("touchEnd", [])
            await page.wait_for_timeout(60)
            ev = summary(events())
            ok = ev == [["down", key], ["up", key]]
            check(f"button {bid} -> {key}", ok, str(ev))

        # ---- multi-touch: two thumbs at once (W via stick + SPACE + mouse-left)
        sx, sy = await center("#stickzone")
        fx, fy = await center('[data-id="CRO"]')
        rx, ry = await center('[data-id="R2"]')
        await touch("touchStart", [{"x": sx, "y": sy, "id": 1}])
        await touch("touchMove", [{"x": sx, "y": sy - 40, "id": 1}])          # up
        await page.wait_for_timeout(40)
        await touch("touchMove", [{"x": sx, "y": sy - 40, "id": 1}, ])
        await touch("touchStart", [{"x": sx, "y": sy - 40, "id": 1}, {"x": fx, "y": fy, "id": 2}])
        await touch("touchStart", [{"x": sx, "y": sy - 40, "id": 1}, {"x": fx, "y": fy, "id": 2}, {"x": rx, "y": ry, "id": 3}])
        await page.wait_for_timeout(80)
        held = (await page.evaluate("fetch('/status').then(()=>1)"))  # noop
        ev = summary(events(clear=False))
        downs = {e[1] for e in ev if e[0] == "down"}
        check("multi-touch: W + SPACE + LMB held together", {"W", "SPACE", "MOUSE_LEFT"} <= downs, str(ev))
        await touch("touchEnd", [])
        await page.wait_for_timeout(80)
        ev = summary(events())
        ups = {e[1] for e in ev if e[0] == "up"}
        check("multi-touch: all released", {"W", "SPACE", "MOUSE_LEFT"} <= ups, str(ev))

        # ---- stick 8-way
        cases = {"W": (0, -45), "S": (0, 45), "A": (-45, 0), "D": (45, 0),
                 "W+D": (40, -40), "W+A": (-40, -40), "S+A": (-40, 40), "S+D": (40, 40)}
        for name, (dx, dy) in cases.items():
            events()
            await touch("touchStart", [{"x": sx, "y": sy, "id": 1}])
            await touch("touchMove", [{"x": sx + dx, "y": sy + dy, "id": 1}])
            await page.wait_for_timeout(60)
            ev = summary(events(clear=False))
            downs = {e[1] for e in ev if e[0] == "down"}
            await touch("touchEnd", [])
            await page.wait_for_timeout(60)
            check(f"stick {name}", downs == set(name.split("+")), str(ev))
            events()

        # ---- touchpad: relative move, tap, two-finger tap
        px, py = await center("#pad")
        events()
        await touch("touchStart", [{"x": px, "y": py, "id": 1}])
        for i in range(1, 6):
            await touch("touchMove", [{"x": px + i * 10, "y": py + i * 4, "id": 1}])
            await page.wait_for_timeout(16)
        await touch("touchEnd", [])
        await page.wait_for_timeout(60)
        ev = events()
        mv = [e for e in ev if e[1] == "move"]
        sx_ = sum(e[2] for e in mv); sy_ = sum(e[3] for e in mv)
        check("touchpad sends relative mouse move (sens 2 => ~100,40)", abs(sx_ - 100) <= 2 and abs(sy_ - 40) <= 2, f"{sx_},{sy_} n={len(mv)}")
        check("touchpad drag does not click", not any(e[1] in ("down", "up") for e in ev), str(ev))
        # tap
        await touch("touchStart", [{"x": px, "y": py, "id": 1}]); await page.wait_for_timeout(40); await touch("touchEnd", [])
        await page.wait_for_timeout(120)
        ev = summary(events())
        check("touchpad tap = left click", ev == [["down", "MOUSE_LEFT"], ["up", "MOUSE_LEFT"]], str(ev))
        # two finger tap
        await touch("touchStart", [{"x": px - 20, "y": py, "id": 1}, {"x": px + 20, "y": py, "id": 2}])
        await page.wait_for_timeout(40); await touch("touchEnd", [])
        await page.wait_for_timeout(120)
        ev = summary(events())
        check("touchpad two-finger tap = right click", ev == [["down", "MOUSE_RIGHT"], ["up", "MOUSE_RIGHT"]], str(ev))

        # ---- remap: change SQU from CTRL to Z, check it fires, check it persists after reload
        await page.tap("#btn-remap")
        await page.wait_for_selector("#banner:not([hidden])")
        await page.screenshot(path=f"{OUT}/03_remap.png")
        x, y = await center('[data-id="SQU"]')
        events()
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await touch("touchEnd", [])
        await page.wait_for_selector("#picker:not([hidden])")
        check("remap mode: tap opens picker, nothing fires", events() == [])
        await page.screenshot(path=f"{OUT}/04_picker.png")
        await page.click('#pickgrid .chip[data-k="Z"]')
        await page.wait_for_selector("#picker", state="hidden")
        await page.tap("#btn-remap")
        x, y = await center('[data-id="SQU"]')
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await page.wait_for_timeout(50); await touch("touchEnd", [])
        await page.wait_for_timeout(60)
        ev = summary(events())
        check("remapped SQU -> Z works", ev == [["down", "Z"], ["up", "Z"]], str(ev))
        await page.reload(); await page.wait_for_selector("#pair", state="hidden")
        await page.wait_for_function("document.querySelector('#pill').textContent.includes('ms')")
        lab = await page.eval_on_selector('[data-id="SQU"] .kb', "e=>e.textContent")
        check("remap persists after reload + auto re-pair", lab == "Z", lab)
        # remap to a mouse wheel + mouse button + stick dir
        await page.tap("#btn-remap")
        x, y = await center('[data-id="SU"]')
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await touch("touchEnd", [])
        await page.wait_for_selector("#picker:not([hidden])")
        await page.click('#pickgrid .chip[data-k="UP"]'); await page.wait_for_selector("#picker", state="hidden")
        lab = await page.eval_on_selector('[data-id="SU"] .kb', "e=>e.textContent")
        check("stick direction remappable", lab == "↑", lab)
        await page.tap("#btn-remap")
        # wheel key
        await page.evaluate("window.__vc.cfg.map.CAM='WHEEL_UP'")
        x, y = await center('[data-id="CAM"]'); events()
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await page.wait_for_timeout(50); await touch("touchEnd", [])
        await page.wait_for_timeout(60)
        ev = summary(events())
        check("wheel binding sends one wheel notch", ["wheel", 1] in ev, str(ev))

        # ---- safety: leaving the page releases everything
        await page.evaluate("window.__vc.cfg.map.CAM='V'")
        x, y = await center('[data-id="L1"]'); events()
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await page.wait_for_timeout(60)
        await page.close()
        await asyncio.sleep(0.3)
        ev = summary(events())
        check("closing page releases held key", ["up", "Q"] in ev, str(ev))

        # ---- layouts at other phone sizes
        for w, h in [(800, 300), (851, 393), (667, 375)]:
            pg = await ctx.new_page(); await pg.set_viewport_size({"width": w, "height": h})
            await pg.goto(BASE + "/mobile"); await pg.wait_for_selector("#pair", state="hidden")
            await pg.screenshot(path=f"{OUT}/layout_{w}x{h}.png")
            ov = await pg.evaluate("""()=>{const bad=[];document.querySelectorAll('.c:not(.sk):not(.sub)').forEach(e=>{
              const r=e.getBoundingClientRect();if(r.right>innerWidth+1||r.bottom>innerHeight+1||r.left<-1||r.top<-1)bad.push(e.dataset.id)});return bad}""")
            check(f"layout fits {w}x{h}", not ov, str(ov))
            await pg.close()
        check("no JS errors", not errs, str(errs))
        await b.close()

    print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
    sys.exit(0 if all(ok for _, ok in results) else 1)

asyncio.run(main())
