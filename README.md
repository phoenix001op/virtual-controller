# GTA Vice City Phone Controller

Use your phone as a controller for GTA Vice City running on your laptop
(e.g. <https://wasmarcade.com/vice-city>). One small Python server runs on the laptop and serves
**both** pages:

| Page | Where | What it does |
|------|-------|--------------|
| `/laptop` | laptop browser | shows the 6-digit pairing code, phone status, live key list, and a test pad |
| `/mobile` | phone browser | the controller (landscape, tuned for a 1600×720 / 6.5" phone) |

Open `http://<laptop-ip>:8765/` on either device and the right page loads automatically.

> **Why a local server?** A website cannot press keys inside another tab or program. The Python
> server on the laptop receives the phone's touches over Wi-Fi and replays them as real keyboard and
> mouse input. GitHub Pages / cloud hosting alone cannot do this.

## Quick start (Windows)

```bat
python -m pip install -r requirements.txt
python server.py
```

1. Open **http://localhost:8765/laptop** on the laptop. It shows a pairing code and the phone URL.
2. Phone on the **same Wi-Fi**: open the phone URL, type the code. (It is remembered afterwards.)
3. Windows Firewall asks the first time: allow **Private networks**.
4. Open the game on the laptop, move the laptop mouse pointer **over the game window**, then
   **tap the touchpad once** on the phone. That clicks the game and captures the mouse so the
   touchpad can look around. `ESC` on the phone releases the mouse.
5. Tap the ⛶ button on the phone for fullscreen landscape.

Handy options: `python server.py --code 123456` (same code every run, no retyping),
`--port 9000`, `--dry-run` (log events instead of pressing keys).

## Default layout (from the wasmarcade key list)

| Control | Key | In game |
|---------|-----|---------|
| Left stick (8-way, floating) | W A S D | walk / drive |
| Touchpad drag | mouse move | look / aim |
| Touchpad tap / 2-finger tap | left / right click | fire, capture mouse |
| R2 | left mouse | attack / drive-by |
| △ Triangle | F | enter / exit vehicle |
| ✕ Cross | SPACE | sprint / handbrake |
| ○ Circle | SHIFT | sprint / horn |
| □ Square | CTRL | attack |
| L2 | C | crouch |
| L1 / R1 | Q / E | weapon switch (check your game's setting) |
| D-pad | arrow keys | menus, bike lean |
| CAM / RADIO / HORN | V / R / H | camera, radio, horn |
| ESC / ENTER | ESC / ENTER | pause, confirm |

## Changing keys

Tap **KEYS** (top bar) → every button gets an orange outline → tap the one you want to change →
pick a letter, number, F-key, arrow, **mouse button or wheel** (or press a key on a connected
keyboard). Stick directions and the touchpad taps are remappable too. Tap **DONE** to finish.
Changes are saved on the phone. **⚙ Settings**: look sensitivity, stick size, invert Y, vibration,
key labels, reset all keys.

## Troubleshooting

* **Phone can't open the page** – same Wi-Fi? Some routers isolate devices ("AP/client isolation");
  use a phone hotspot or the laptop's hotspot instead. Check the firewall prompt.
* **Keys do nothing** – the game window must be focused. If the game runs as administrator, start
  the server as administrator too.
* **Touchpad doesn't turn the camera** – the laptop mouse pointer must be over the game and the game
  must have captured the mouse (tap the touchpad once). Tune ⚙ sensitivity. If the camera feels
  uneven, turn off Windows "Enhance pointer precision".
* **Lag** – use 5 GHz Wi-Fi or a hotspot. The green number in the top bar is the live round-trip
  time in ms.
* Wrong pairing code 5 times locks that device out for 30 s.

## Security

Anyone who knows the pairing code on your network can control your keyboard and mouse, so use it
only on a Wi-Fi you trust. The code is only shown to the laptop itself, never served to the phone.

## Development / tests

* `python server.py --dry-run` – no real input; events are listed at `/debug/events`.
* `tests/test_ui.py` – drives the phone page in headless Chrome (multi-touch, remap, layouts) against a
  dry-run server. Needs `pip install playwright` and Chrome. See `NOTES.md`.
* Real-input path verified on Linux/X11 (Xvfb) with pynput; **not yet tried on a real Windows PC**.
