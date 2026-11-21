@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
start "" http://localhost:8765/laptop
python server.py
pause
