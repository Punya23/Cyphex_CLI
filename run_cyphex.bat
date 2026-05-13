@echo off
echo ==============================================
echo CYPHEX v3 Setup and Run Script
echo ==============================================

echo.
echo 1. Setting up Backend...
if not exist "backend\.venv" (
    echo Creating virtual environment...
    cd backend
    python -m venv .venv
    cd ..
)

echo Installing python dependencies...
cd backend
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
pip install python-multipart -q
cd ..

echo.
echo 2. Setting up Frontend...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo.
echo 3. Starting CYPHEX Services...
echo Starting Backend API (Port 8000)...
start "CYPHEX Backend" cmd /c "cd backend && call .venv\Scripts\activate.bat && set PYTHONUTF8=1 && python backend/api.py"

echo Starting Frontend (Port 5173)...
start "CYPHEX Frontend" cmd /c "cd frontend && npm run dev"

echo.
echo ==============================================
echo CYPHEX v3 is starting up!
echo - Frontend GUI: http://localhost:5173
echo - Backend API:  http://localhost:8000
echo.
echo NOTE: Update "backend\.env" with your CEREBRAS_API_KEY!
echo ==============================================
pause
