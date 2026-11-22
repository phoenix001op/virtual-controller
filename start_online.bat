@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
if not exist relay_url.txt (
  set /p RELAY=Paste your relay address, e.g. https://my-app.onrender.com : 
  echo %RELAY%> relay_url.txt
)
python agent.py
pause
