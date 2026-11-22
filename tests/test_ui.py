"""Phone-page UI test. Start first:  python server.py --dry-run --code 123456
Then:  python tests/test_ui.py   (needs: pip install playwright; playwright install chromium)
Optional env: CHROME=/path/to/chrome  OUT_DIR=screenshot-folder"""
import asyncio, json, os, sys, tempfile, urllib.request
from playwright.async_api import async_playwright

BASE = "http://localhost:8765"
OUT = os.environ.get("OUT_DIR") or tempfile.mkdtemp(prefix="vc-shots-")
CHROME = os.environ.get("CHROME")


def events(clear=True):
    with urllib.request.urlopen(f"{BASE}/debug/events" + ("?clear=1" if clear else "")) as r:
        return json.load(r)


def summary(ev):
    return [e[1:] for e in ev]


async def main():
    results = []

    def check(name, ok, info=""):
        results.append(ok)
        print(("PASS " if ok else "FAIL ") + name + (f"  {info}" if info and not ok else ""))

    async with async_playwright() as p:
        kw = {"executable_path": CHROME} if CHROME else {}
        b = await p.chromium.launch(args=["--no-sandbox"], **kw)
        ctx = await b.new_context(viewport={"width": 800, "height": 360}, device_scale_factor=2,
                                  has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await page.goto(BASE + "/mobile")
        await page.wait_for_selector("#pair:not([hidden])")
        await page.fill("#code", "000000")
        await page.wait_for_function("document.querySelector('#pairmsg').textContent.includes('Wrong')")
        check("wrong code rejected", True)
        await page.fill("#code", "123456")
        await page.wait_for_selector("#pair", state="hidden")
        await page.wait_for_function("document.querySelector('#pill').textContent.includes('ms')")
        check("pairing + latency readout", True)
        await page.screenshot(path=f"{OUT}/gta.png")

        cdp = await ctx.new_cdp_session(page)

        async def touch(kind, pts):
            await cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})

        async def center(sel):
            return await page.eval_on_selector(sel, "e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")

        async def press_all(table, label):
            for bid, key in table.items():
                x, y = await center(f'[data-id="{bid}"]')
                events()
                await touch("touchStart", [{"x": x, "y": y, "id": 1}])
                await page.wait_for_timeout(60)
                await touch("touchEnd", [])
                await page.wait_for_timeout(60)
                ev = summary(events())
                if key.startswith("WHEEL"):
                    ok = ["wheel", 1 if key == "WHEEL_UP" else -1] in ev
                else:
                    ok = ev == [["down", key], ["up", key]]
                check(f"{label} {bid} -> {key}", ok, str(ev))

        gta = {"L1": "Q", "L2": "C", "R1": "E", "R2": "MOUSE_LEFT", "TRI": "F", "CIR": "SHIFT", "CRO": "SPACE",
               "SQU": "CTRL", "DU": "UP", "DD": "DOWN", "DL": "LEFT", "DR": "RIGHT", "T1": "ESC", "T2": "ENTER",
               "T3": "H", "E1": "V", "E2": "R"}
        await press_all(gta, "GTA button")

        # ---- left stick 8-way
        sx, sy = await center("#stickzone")
        for name, (dx, dy) in {"W": (0, -45), "S": (0, 45), "A": (-45, 0), "D": (45, 0), "W+D": (40, -40),
                               "W+A": (-40, -40), "S+A": (-40, 40), "S+D": (40, 40)}.items():
            events()
            await touch("touchStart", [{"x": sx, "y": sy, "id": 1}])
            await touch("touchMove", [{"x": sx + dx, "y": sy + dy, "id": 1}])
            await page.wait_for_timeout(60)
            downs = {e[1] for e in summary(events(clear=False)) if e[0] == "down"}
            await touch("touchEnd", [])
            await page.wait_for_timeout(60)
            check(f"stick {name}", downs == set(name.split("+")), str(downs))
            events()

        # ---- LOOK joystick: speed proportional to deflection, stops on release, no clicks
        lx, ly = await center("#lookzone")

        async def look(dx, dy, ms=400):
            events()
            await touch("touchStart", [{"x": lx, "y": ly, "id": 1}])
            await touch("touchMove", [{"x": lx + dx, "y": ly + dy, "id": 1}])
            await page.wait_for_timeout(ms)
            await touch("touchEnd", [])
            await page.wait_for_timeout(100)
            ev = events()
            mv = [e for e in ev if e[1] == "move"]
            t = mv[-1][0] - mv[0][0] if len(mv) > 1 else 0
            return sum(e[2] for e in mv), sum(e[3] for e in mv), len(mv), t, ev

        sx1, sy1, n1, _, ev1 = await look(60, 0)
        check("look stick right => positive X mouse movement", sx1 > 100 and abs(sy1) <= 2, f"{sx1},{sy1}")
        check("look stick sends many small frames (smooth, not one jump)", n1 >= 10, f"n={n1}")
        check("look stick does not click", not any(e[1] in ("down", "up") for e in ev1), str(ev1[:4]))
        sx2, sy2, *_ = await look(-60, 0)
        check("look stick left => negative X", sx2 < -100, f"{sx2}")
        _, sy3, *_ = await look(0, 60)
        check("look stick down => positive Y", sy3 > 100, f"{sy3}")
        _, sy4, *_ = await look(0, -60)
        check("look stick up => negative Y", sy4 < -100, f"{sy4}")
        light, *_ = await look(22, 0)
        full, *_ = await look(60, 0)
        check("small deflection is slower than full deflection", 0 < light < full * 0.6, f"{light} vs {full}")
        dead, *_ = await look(3, 0)
        check("tiny movement inside deadzone sends nothing", dead == 0, f"{dead}")
        await touch("touchStart", [{"x": lx, "y": ly, "id": 1}])
        await touch("touchMove", [{"x": lx + 60, "y": ly, "id": 1}])
        await page.wait_for_timeout(200)
        await touch("touchEnd", [])
        await page.wait_for_timeout(100)
        events()
        await page.wait_for_timeout(300)
        check("mouse movement stops after releasing the look stick", events() == [])

        # ---- tap = left click, two-finger tap = right click (on the look area)
        events()
        await touch("touchStart", [{"x": lx, "y": ly, "id": 1}]); await page.wait_for_timeout(40); await touch("touchEnd", [])
        await page.wait_for_timeout(120)
        ev = summary(events())
        check("look-area tap = left click", ev == [["down", "MOUSE_LEFT"], ["up", "MOUSE_LEFT"]], str(ev))
        await touch("touchStart", [{"x": lx - 20, "y": ly, "id": 1}, {"x": lx + 20, "y": ly, "id": 2}])
        await page.wait_for_timeout(40); await touch("touchEnd", [])
        await page.wait_for_timeout(120)
        ev = summary(events())
        check("look-area two-finger tap = right click", ev == [["down", "MOUSE_RIGHT"], ["up", "MOUSE_RIGHT"]], str(ev))

        # ---- both thumbs: walk (left stick) + look (right stick) + button at the same time
        fx, fy = await center('[data-id="CRO"]')
        events()
        await touch("touchStart", [{"x": sx, "y": sy, "id": 1}])
        await touch("touchMove", [{"x": sx, "y": sy - 45, "id": 1}])
        await touch("touchStart", [{"x": sx, "y": sy - 45, "id": 1}, {"x": lx, "y": ly, "id": 2}])
        await touch("touchMove", [{"x": sx, "y": sy - 45, "id": 1}, {"x": lx + 50, "y": ly, "id": 2}])
        await touch("touchStart", [{"x": sx, "y": sy - 45, "id": 1}, {"x": lx + 50, "y": ly, "id": 2}, {"x": fx, "y": fy, "id": 3}])
        await page.wait_for_timeout(250)
        ev = summary(events(clear=False))
        downs = {e[1] for e in ev if e[0] == "down"}
        check("three fingers: W + look + SPACE together", {"W", "SPACE"} <= downs and any(e[0] == "move" for e in ev), str(ev[:5]))
        await touch("touchEnd", [])
        await page.wait_for_timeout(100)
        ups = {e[1] for e in summary(events()) if e[0] == "up"}
        check("three fingers released", {"W", "SPACE"} <= ups, str(ups))

        # ---- game picker: switch to Minecraft
        await page.screenshot(path=f"{OUT}/gta2.png")
        check("game button shows GTA VC", (await page.inner_text("#btn-game")) == "GTA VC")
        await page.tap("#btn-game")
        await page.wait_for_selector("#games:not([hidden])")
        await page.screenshot(path=f"{OUT}/games.png")
        await page.tap('.gamecard[data-g="mc"]')
        await page.wait_for_selector("#games", state="hidden")
        check("game button now says MINECRAFT", (await page.inner_text("#btn-game")) == "MINECRAFT")
        labels = [await page.inner_text(f'[data-id="{i}"] b') for i in ("T1", "T2", "T3", "E1", "E2")]
        check("per-game button labels changed", labels == ["PAUSE", "ENTER", "CHAT", "VIEW", "DROP"], str(labels))
        await page.screenshot(path=f"{OUT}/minecraft.png")
        mc = {"L1": "WHEEL_UP", "L2": "MOUSE_RIGHT", "R1": "WHEEL_DOWN", "R2": "MOUSE_LEFT", "TRI": "E", "CIR": "SHIFT",
              "CRO": "SPACE", "SQU": "CTRL", "DU": "2", "DD": "4", "DL": "1", "DR": "3", "T1": "ESC", "T2": "ENTER",
              "T3": "T", "E1": "F5", "E2": "Q"}
        await press_all(mc, "MC button")
        # stick still WASD in Minecraft
        events()
        await touch("touchStart", [{"x": sx, "y": sy, "id": 1}]); await touch("touchMove", [{"x": sx, "y": sy - 45, "id": 1}])
        await page.wait_for_timeout(60)
        downs = {e[1] for e in summary(events(clear=False)) if e[0] == "down"}
        await touch("touchEnd", []); await page.wait_for_timeout(60); events()
        check("MC stick forward = W", downs == {"W"}, str(downs))


        # ---- CAR game: steering wheel + pedals + other buttons
        await page.evaluate("window.__vc.setGame('car')")
        await page.screenshot(path=f"{OUT}/car.png")
        check("car layout hides stick/look area", not await page.is_visible("#stickzone") and not await page.is_visible("#lookzone"))
        check("car layout shows wheel + pedals", await page.is_visible("#wheelzone") and await page.is_visible("#pedals"))
        car = {"P2": "W", "P1": "S", "CRO": "SPACE", "TRI": "SHIFT", "SQU": "H", "CIR": "B", "L1": "Q", "R1": "E",
               "L2": "L", "R2": "R", "T1": "ESC", "T2": "ENTER", "T3": "F", "E1": "C", "E2": "V"}
        await press_all(car, "CAR button")
        wx, wy = await center("#wheelzone")
        for name, dx, key in [("left", -70, "A"), ("right", 70, "D")]:
            events()
            await touch("touchStart", [{"x": wx, "y": wy, "id": 1}])
            await touch("touchMove", [{"x": wx + dx, "y": wy, "id": 1}])
            await page.wait_for_timeout(60)
            downs = {e[1] for e in summary(events(clear=False)) if e[0] == "down"}
            rot = await page.eval_on_selector("#wheel", "e=>e.style.transform")
            await touch("touchEnd", []); await page.wait_for_timeout(60)
            ups = {e[1] for e in summary(events()) if e[0] == "up"}
            check(f"steer {name} => {key} held, wheel rotates, released", downs == {key} and key in ups and "rotate" in rot, f"{downs} {ups} {rot}")
        events()
        await touch("touchStart", [{"x": wx, "y": wy, "id": 1}])
        await touch("touchMove", [{"x": wx + 5, "y": wy, "id": 1}]); await page.wait_for_timeout(60)
        small = [e for e in events() if e[1] == "down"]
        await touch("touchEnd", []); events()
        check("tiny wheel movement = no steering (deadzone)", small == [])
        px, py = await center('[data-id="P2"]'); sx2, sy2 = await center("#wheelzone")
        events()
        await touch("touchStart", [{"x": sx2, "y": sy2, "id": 1}]); await touch("touchMove", [{"x": sx2 + 70, "y": sy2, "id": 1}])
        await touch("touchStart", [{"x": sx2 + 70, "y": sy2, "id": 1}, {"x": px, "y": py, "id": 2}])
        await page.wait_for_timeout(80)
        downs = {e[1] for e in summary(events(clear=False)) if e[0] == "down"}
        check("steer right + gas at the same time (D + W)", downs == {"D", "W"}, str(downs))
        await touch("touchEnd", []); await page.wait_for_timeout(80); events()
        await page.evaluate("window.__vc.setGame('gta')")
        lab = await page.inner_text('[data-id="L1"] b')
        check("switching back to GTA restores button text", lab == "L1", lab)
        await page.evaluate("window.__vc.setGame('mc')")

        # ---- remap is per game: change MC cross to X, GTA cross must stay SPACE
        await page.tap("#btn-remap")
        x, y = await center('[data-id="CRO"]')
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await touch("touchEnd", [])
        await page.wait_for_selector("#picker:not([hidden])")
        await page.screenshot(path=f"{OUT}/picker.png")
        await page.click('#pickgrid .chip[data-k="X"]')
        await page.tap("#btn-remap")
        await press_all({"CRO": "X"}, "MC remapped")
        await page.evaluate("window.__vc.setGame('gta')")
        await press_all({"CRO": "SPACE"}, "GTA unaffected by MC remap")
        await page.reload(); await page.wait_for_selector("#pair", state="hidden")
        await page.wait_for_function("document.querySelector('#pill').textContent.includes('ms')")
        check("selected game persists after reload", (await page.inner_text("#btn-game")) == "GTA VC")
        await page.evaluate("window.__vc.setGame('mc')")
        lab = await page.eval_on_selector('[data-id="CRO"] .kb', "e=>e.textContent")
        check("MC remap persists after reload", lab == "X", lab)

        # ---- leaving releases held keys
        x, y = await center('[data-id="L2"]'); events()
        await touch("touchStart", [{"x": x, "y": y, "id": 1}]); await page.wait_for_timeout(60)
        await page.close(); await asyncio.sleep(0.3)
        check("closing the page releases held key", ["up", "MOUSE_RIGHT"] in summary(events()))

        # ---- layouts on other phone sizes (both games)
        for w, h in [(800, 300), (851, 393), (667, 375)]:
            pg = await ctx.new_page(); await pg.set_viewport_size({"width": w, "height": h})
            await pg.goto(BASE + "/mobile"); await pg.wait_for_selector("#pair", state="hidden")
            await pg.evaluate("window.__vc.setGame('car')")
            await pg.screenshot(path=f"{OUT}/layout_car_{w}x{h}.png")
            await pg.evaluate("window.__vc.setGame('mc')")
            await pg.screenshot(path=f"{OUT}/layout_{w}x{h}.png")
            bad = await pg.evaluate("""()=>{const bad=[];document.querySelectorAll('.c:not(.sk):not(.sub),.tool,.pill').forEach(e=>{
              const r=e.getBoundingClientRect();if(r.right>innerWidth+1||r.bottom>innerHeight+1||r.left<-1||r.top<-1)bad.push(e.dataset.id||e.id||e.className)});return bad}""")
            check(f"layout fits {w}x{h}", not bad, str(bad))
            await pg.close()
        check("no JS errors", not errs, str(errs))
        await b.close()

    print(f"\n{sum(results)}/{len(results)} passed. Screenshots in {OUT}")
    sys.exit(0 if all(results) else 1)


asyncio.run(main())
