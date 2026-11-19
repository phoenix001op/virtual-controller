# GTA Vice City Mobile Controller

This project serves the laptop receiver page and mobile gamepad from one local Python server. It sends keyboard events to the GTA game running on the laptop.

## Start on the laptop (Windows)

1. Extract/download this repository.
2. Open Command Prompt in the project folder.
3. Run:

```bat
python -m pip install -r requirements.txt
python server.py
```

4. Keep the server running. Open the laptop page shown in Command Prompt (normally `http://localhost:8765/laptop`).
5. On your phone, while connected to the same Wi-Fi, open the phone URL printed in Command Prompt.
6. Enter the six-digit pairing code shown on the laptop page.
7. Click the GTA game window before using the controls.

## Important

The GitHub repository stores the code; it is not the keyboard receiver. A cloud-hosted website cannot directly send key presses into a game running on your personal laptop. The Python receiver must run on the laptop. GitHub Pages alone will not replace it.

The controller sends keyboard events (not a physical Xbox controller), so compatibility depends on GTA's keyboard settings. Use only on a trusted private Wi-Fi network.
