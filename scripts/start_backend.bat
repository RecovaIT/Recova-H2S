@echo off
cd /d "%~dp0\..\backend"
echo Starting Recova FastAPI backend on http://127.0.0.1:8000...
call ".venv\Scripts\activate.bat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
