"""Laptop agent: presses the keys / moves the mouse that the phone sends through the online relay.

    python agent.py --relay https://your-app.onrender.com
    python agent.py --relay https://your-app.onrender.com --code AB12CD34     # fixed code
    python agent.py --dry-run --verbose ...                                   # test without real input

The relay address can also be saved in a file named relay_url.txt next to this script (start_online.bat does this).
"""
import argparse
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

import aiohttp

from server import DryRunBackend, Injector, PynputBackend

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
J = lambda o: json.dumps(o, separators=(",", ":"))


class Echo(DryRunBackend):
    def _log(self, *e):
        print("  event:", *e, flush=True)
        super()._log(*e)


def ws_url(relay, code):
    base = relay.rstrip("/")
    base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    if not base.startswith(("ws://", "wss://")):
        base = "wss://" + base
    return f"{base}/agent?code={code}"


async def run(relay, code, inj):
    page = relay.rstrip("/")
    if not page.startswith("http"):
        page = "https://" + page
    print("\n=====================================================")
    print(f"  PAIRING CODE:  {code}")
    print(f"  On your phone open:  {page}/mobile   and type the code")
    print(f"  (optional) laptop status page:  {page}/laptop")
    print("=====================================================\n", flush=True)
    state = {"phone": False}
    delay = 1
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.ws_connect(ws_url(relay, code), heartbeat=10, compress=0) as ws:
                    delay = 1
                    print("connected to relay - waiting for phone", flush=True)

                    async def push():
                        await ws.send_str(J({"t": "state", "phone": state["phone"], "keys": sorted(inj.held)}))

                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        try:
                            d = json.loads(msg.data)
                        except ValueError:
                            continue
                        t = d.get("t")
                        if t == "k":
                            before = set(inj.held)
                            keys = d.get("keys", [])
                            if isinstance(keys, list):
                                inj.set_keys(keys[:40])
                            if set(inj.held) != before:
                                await push()
                        elif t == "m":
                            inj.move(d.get("x", 0), d.get("y", 0))
                        elif t == "p":
                            await ws.send_str(J({"t": "pong", "ts": d.get("ts")}))
                        elif t == "r":
                            inj.release_all()
                            await push()
                        elif t == "phone":
                            state["phone"] = bool(d.get("on"))
                            if not state["phone"]:
                                inj.release_all()
                            print("phone", "connected" if state["phone"] else "disconnected", flush=True)
                            await push()
                        elif t == "snap":
                            await push()
            except aiohttp.WSServerHandshakeError as e:
                if e.status == 409:
                    sys.exit("That code is already in use (is another agent running?). Restart to get a new code.")
                print("relay refused connection:", e.status, flush=True)
            except (aiohttp.ClientError, OSError) as e:
                print("relay unreachable, retrying...", type(e).__name__, flush=True)
            inj.release_all()  # never leave keys stuck when the link drops
            state["phone"] = False
            await asyncio.sleep(delay)
            delay = min(10, delay * 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relay", help="address of your hosted relay, e.g. https://my-app.onrender.com")
    ap.add_argument("--code", help="fixed pairing code (6-8 letters/digits). Default: random each run")
    ap.add_argument("--dry-run", action="store_true", help="do not press real keys")
    ap.add_argument("--verbose", action="store_true", help="print every key/mouse event (with --dry-run)")
    a = ap.parse_args()

    relay = a.relay or os.environ.get("VC_RELAY")
    f = Path(__file__).with_name("relay_url.txt")
    if not relay and f.exists():
        relay = f.read_text().strip()
    if not relay:
        sys.exit("Tell me where your relay is:  python agent.py --relay https://your-app.onrender.com")
    code = (a.code or "".join(secrets.choice(ALPHABET) for _ in range(8))).upper()

    if a.dry_run:
        backend = Echo() if a.verbose else DryRunBackend()
    else:
        try:
            backend = PynputBackend()
        except Exception as e:
            sys.exit(f"Could not start keyboard/mouse control ({e}).\nRun: python -m pip install -r requirements.txt")
    try:
        asyncio.run(run(relay, code, Injector(backend)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
