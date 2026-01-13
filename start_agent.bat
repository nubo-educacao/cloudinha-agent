@echo off
echo Starting Cloudinha Agent Server on port 8080...
call .venv\Scripts\activate
set PORT=8080
set PYTHONUNBUFFERED=1
python server.py
pause
