@echo off
echo ======================================
echo   SOLO LEVELING FITNESS SYSTEM
echo ======================================
echo.
echo Starting the Hunter Training System...
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/update requirements
echo Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo Server starting...
echo.
echo Access the application at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the Flask server
cd backend
python app.py

pause
