@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
if exist relay_url.txt goto run
set /p RELAY=Paste your relay address, e.g. https://my-app.onrender.com : 
>relay_url.txt echo %RELAY%
:run
python agent.py
pause
