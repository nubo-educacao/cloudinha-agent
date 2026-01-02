@echo off
echo Starting Cloudinha Agent Server on port 8002...
call .venv\Scripts\activate
python server.py
pause
