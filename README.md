# GTA Vice City Phone Controller

Use your phone as a controller for GTA Vice City running on your laptop
(e.g. <https://wasmarcade.com/vice-city>). One small Python server runs on the laptop and serves
**both** pages:

| Page | Where | What it does |
|------|-------|--------------|
| `/laptop` | laptop browser | shows the 6-digit pairing code, phone status, live key list, and a test pad |
| `/mobile` | phone browser | the controller (landscape, tuned for a 1600×720 / 6.5" phone). Games: GTA Vice City, Minecraft, Car game |

Open `http://<laptop-ip>:8765/` on either device and the right page loads automatically.

> **Why a local server?** A website cannot press keys inside another tab or program. The Python
> server on the laptop receives the phone's touches over Wi-Fi and replays them as real keyboard and
> mouse input. GitHub Pages / cloud hosting alone cannot do this.

## Online mode (host it once, use from anywhere, no same-Wi-Fi needed)

A website cannot press keys on your laptop, so there are three parts:

1. **Relay** (`relay.py`) - you host this once. It serves the phone/laptop web pages and links the phone to your laptop.
2. **Phone** - opens `https://<your-host>/mobile` and types the pairing code.
3. **Agent** (`agent.py`) - a small program on the laptop that connects *out* to the relay and presses the keys.

### Host the relay (free options)

* **Render**: New + > Web Service > connect this GitHub repo > it detects `Dockerfile` / `render.yaml` > Create.
  (Free instances sleep after ~15 min idle; the first load can take about a minute.)
* **Railway / Fly.io / any VPS**: deploy the repo; start command `python relay.py` (reads `$PORT`). Docker works too.
* GitHub Pages / Netlify static hosting alone will **not** work - the relay is a live server.

### Every time you play

1. On the laptop run **`start_online.bat`** (first time it asks for your relay address, e.g.
   `https://vice-controller.onrender.com`). It prints an 8-character pairing code.
2. On the phone open the same address (`/mobile`) and type the code, tap Connect.
3. Optional: open the address on the laptop to see phone status, held keys and the test pad.
4. Open the game on the laptop and click once inside it. Then play.

The code is new every run (use `python agent.py --code MYCODE12` for a fixed one). Wrong codes are rate-limited
(5 tries then a 1 minute lock). Anyone who gets your code while the agent is running can press keys on your laptop,
so don't share it. Online mode adds the phone-to-server-to-laptop trip, so expect a bit more delay than the local
Wi-Fi mode below; pick a host region close to you.

## Local mode (same Wi-Fi, lowest delay)

### Quick start (Windows)

```bat
python -m pip install -r requirements.txt
python server.py
```

1. Open **http://localhost:8765/laptop** on the laptop. It shows a pairing code and the phone URL.
2. Phone on the **same Wi-Fi**: open the phone URL, type the code. (It is remembered afterwards.)
3. Windows Firewall asks the first time: allow **Private networks**.
4. Click once inside the game (or tap **R2** on the phone, the left mouse button). That captures the mouse so the look
   joystick can turn the camera. `ESC` on the phone releases the mouse.
5. Tap the ⛶ button on the phone for fullscreen landscape.

Handy options: `python server.py --code 123456` (same code every run, no retyping),
`--port 9000`, `--dry-run` (log events instead of pressing keys).

## Choosing a game

Tap the game button (left of ⚙, shows `GTA VC` or `MINECRAFT`) and pick a game. Each game has its own
button names, default keys and its own saved key changes, so remapping Minecraft never affects GTA.

Two sticks: the **left stick** (bottom left) is WASD; the **round look joystick** in the center turns the camera.
Push it a little to turn slowly and further to turn faster; it stops when you let go. Change **Look speed** in the
settings (default 1.0). To capture the mouse in the game, click once inside the game on the laptop, or tap **R2**
(left mouse) on the phone.

### GTA Vice City (wasmarcade.com/vice-city)

| Control | Key | In game |
|---------|-----|---------|
| Left stick | W A S D | walk / drive |
| Look stick | mouse move | camera / aim |
| R2 | left mouse | attack / drive-by |
| △ | F | enter / exit vehicle |
| ✕ | SPACE | sprint / handbrake |
| ○ | SHIFT | sprint / horn |
| □ | CTRL | attack |
| L2 | C | crouch |
| L1 / R1 | Q / E | weapon switch (check in game) |
| D-pad | arrow keys | menus, bike lean |
| ESC / ENTER / HORN / CAM / RADIO | ESC / ENTER / H / V / R | pause, confirm, horn, camera, radio |

### Minecraft (wasmarcade.com/minecraft, Java 1.8.8)

| Control | Key | In game |
|---------|-----|---------|
| Left stick | W A S D | move |
| Look stick | mouse move | look |
| R2 / L2 | left / right mouse | break-attack / place-use |
| L1 / R1 | wheel up / down | hotbar scroll |
| D-pad | 1 2 3 4 | hotbar slots (change to any 1-9) |
| ✕ / ○ / □ | SPACE / SHIFT / CTRL | jump / sneak / sprint |
| △ | E | inventory |
| PAUSE / ENTER / CHAT / VIEW / DROP | ESC / ENTER / T / F5 / Q | pause, confirm, chat, camera view, drop |

### Car game (steering layout)

Left: big **steering wheel** (touch and drag sideways; it turns and holds A or D). Center: **BRAKE** (S) and
**GAS** (W) pedals, and a **REVERSE** toggle: tap it and GAS drives backwards (sends the reverse key, default S; remap with KEYS). Tap again to go forward. Right: NITRO (Shift), HORN (H), LOOK BACK (B), HAND BRAKE (Space), CAMERA (C), RADIO (V).
Top: GEAR ▼/▲ (Q/E), LIGHTS (L), RESET (R), PAUSE, ENTER, EXIT CAR (F). These keys are my best guess for a
generic car game, so use **KEYS** to match whatever the game you play expects.

To add another game, add an entry to `GAMES` at the top of `web/mobile.js`.

## Troubleshooting

* **Phone can't open the page** – same Wi-Fi? Some routers isolate devices ("AP/client isolation");
  use a phone hotspot or the laptop's hotspot instead. Check the firewall prompt.
* **Keys do nothing** – the game window must be focused. If the game runs as administrator, start
  the server as administrator too.
* **Look stick doesn't turn the camera** – the laptop mouse pointer must be over the game and the game
  must have captured the mouse (click inside the game once). Tune ⚙ Look speed; lower it if the camera spins too fast. If the camera feels
  uneven, turn off Windows "Enhance pointer precision".
* **Lag** – use 5 GHz Wi-Fi or a hotspot. The green number in the top bar is the live round-trip
  time in ms.
* Wrong pairing code 5 times locks that device out for 30 s.

## Security

Anyone who knows the pairing code on your network can control your keyboard and mouse, so use it
only on a Wi-Fi you trust. The code is only shown to the laptop itself, never served to the phone.

## Development / tests

* `python tests/test_relay.py` - online mode test (relay + agent + phone page).
* `python server.py --dry-run` – no real input; events are listed at `/debug/events`.
* `tests/test_ui.py` – drives the phone page in headless Chrome (multi-touch, remap, layouts) against a
  dry-run server. Needs `pip install playwright` and Chrome. See `NOTES.md`.
* Real-input path verified on Linux/X11 (Xvfb) with pynput; **not yet tried on a real Windows PC**.
