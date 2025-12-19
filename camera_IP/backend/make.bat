@echo off
REM ============================================
REM Backend API - Quick Start Script for Windows
REM Default: Chỉ cần gõ "make.bat" là chạy luôn
REM ============================================

setlocal enabledelayedexpansion

REM Default action: check-and-run
if "%1"=="" goto check-and-run
if "%1"=="help" goto help
if "%1"=="setup-venv" goto setup-venv
if "%1"=="install" goto install
if "%1"=="setup" goto setup
if "%1"=="run" goto run
if "%1"=="dev" goto dev
if "%1"=="start" goto start
if "%1"=="test" goto test
if "%1"=="clean" goto clean
if "%1"=="info" goto info
if "%1"=="status" goto status
if "%1"=="docs" goto docs
if "%1"=="check-models" goto check-models
if "%1"=="quickstart" goto quickstart

echo Unknown command: %1
goto help

REM ============================================
REM Default: Check venv and run
REM ============================================
:check-and-run
echo.
echo [96m========================================[0m
echo [96m   Backend API - Starting...[0m
echo [96m========================================[0m
echo.

REM Check if venv exists
echo [93mChecking virtual environment...[0m
if not exist "venv\" (
    echo [91mVirtual environment not found. Creating...[0m
    echo.
    call :setup-venv
    if errorlevel 1 exit /b 1
) else (
    echo [92mVirtual environment found[0m
    REM Check if packages are installed
    call venv\Scripts\activate.bat
    python -c "import fastapi" 2>nul
    if errorlevel 1 (
        echo [93mPackages not installed. Installing...[0m
        call :install
        if errorlevel 1 exit /b 1
    ) else (
        echo [92mPackages OK[0m
    )
)

echo.
echo [93mChecking model files...[0m
if not exist "models\license_plate.pt" (
    echo [91mError: models\license_plate.pt not found![0m
    echo [93mPlease add model file to models\ directory[0m
    exit /b 1
)
echo [92mModel files OK[0m
echo.
goto run

:help
echo.
echo [92mCamera IP Backend - License Plate Detection[0m
echo.
echo [93mQUICK START:[0m
echo   Just run: [96mmake.bat[0m (no arguments)
echo   It will auto-create venv and start server!
echo.
echo [94mOther commands:[0m
echo   [96mmake.bat[0m               - Auto check venv + run (DEFAULT)
echo   [96mmake.bat setup-venv[0m    - Create virtual environment
echo   [96mmake.bat install[0m       - Install Python dependencies (requires venv)
echo   [96mmake.bat setup[0m         - Complete setup (venv + deps + models)
echo   [96mmake.bat run[0m           - Run production server
echo   [96mmake.bat dev[0m           - Run development server with auto-reload
echo   [96mmake.bat start[0m         - Start API and go2rtc together
echo   [96mmake.bat test[0m          - Run tests
echo   [96mmake.bat clean[0m         - Clean cache files
echo   [96mmake.bat info[0m          - Show system information
echo   [96mmake.bat status[0m        - Check if server is running
echo   [96mmake.bat docs[0m          - Show API documentation URLs
echo   [96mmake.bat check-models[0m  - Check if model files exist
echo   [96mmake.bat quickstart[0m    - Complete quickstart (setup + run)
echo.
echo [92mServer URLs:[0m
echo   API:        http://localhost:5000
echo   Swagger UI: http://localhost:5000/docs
echo   WebSocket:  ws://localhost:5000/ws/detections
echo.
goto end

REM ============================================
REM Setup virtual environment
REM ============================================
:setup-venv
echo [92mCreating virtual environment...[0m
python -m venv venv
if errorlevel 1 (
    echo [91mFailed to create virtual environment![0m
    echo [93mMake sure Python is installed and in PATH[0m
    exit /b 1
)

echo [92mActivating virtual environment...[0m
call venv\Scripts\activate.bat

echo [92mUpgrading pip...[0m
python -m pip install --upgrade pip

echo [92mInstalling dependencies...[0m
pip install -r requirements.txt
if errorlevel 1 (
    echo [91mInstallation failed![0m
    exit /b 1
)

echo [92mVirtual environment setup complete![0m
goto end

REM ============================================
REM Install dependencies (requires venv)
REM ============================================
:install
if not exist "venv\" (
    echo [91mError: venv not found. Run 'make.bat setup-venv' first.[0m
    exit /b 1
)

echo [92mInstalling Python dependencies...[0m
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo [91mInstallation failed![0m
    exit /b 1
)
echo [92mInstallation complete![0m
goto end

REM ============================================
REM Complete setup
REM ============================================
:setup
echo [92mRunning setup...[0m
call :setup-venv
if errorlevel 1 exit /b 1
call :check-models
echo [92mSetup complete! You can now run 'make.bat run' or 'make.bat dev'[0m
goto end

REM ============================================
REM Check model files
REM ============================================
:check-models
echo [94mChecking model files...[0m
if not exist "models\license_plate.pt" (
    echo [91mError: models\license_plate.pt not found![0m
    exit /b 1
)
if not exist "models\ocr.onnx" (
    echo [93mWarning: models\ocr.onnx not found (optional)[0m
)
echo [92mModel files OK[0m
goto end

REM ============================================
REM Run production server
REM ============================================
:run
if not exist "venv\" (
    echo [91mError: venv not found. Run 'make.bat setup' first.[0m
    exit /b 1
)
echo [92mStarting production server...[0m
echo [96mServer: http://localhost:5000[0m
echo [96mAPI Docs: http://localhost:5000/docs[0m
echo [96mWebSocket: ws://localhost:5000/ws/detections[0m
echo.
call venv\Scripts\activate.bat && python main.py
goto end

REM ============================================
REM Run development server
REM ============================================
:dev
if not exist "venv\" (
    echo [91mError: venv not found. Run 'make.bat setup' first.[0m
    exit /b 1
)
echo [92mStarting development server with auto-reload...[0m
echo [96mServer: http://localhost:5000[0m
echo [96mAPI Docs: http://localhost:5000/docs[0m
echo [96mWebSocket: ws://localhost:5000/ws/detections[0m
echo.
call venv\Scripts\activate.bat && uvicorn main:app --reload --port 5000
goto end

REM ============================================
REM Start with go2rtc
REM ============================================
:start
echo [92mStarting API and go2rtc...[0m
npm start
goto end

REM ============================================
REM Run tests
REM ============================================
:test
if not exist "venv\" (
    echo [91mError: venv not found. Run 'make.bat setup' first.[0m
    exit /b 1
)
echo [92mRunning detection tests...[0m
call venv\Scripts\activate.bat
if exist "test_detection.py" (
    python test_detection.py
) else (
    echo [93mtest_detection.py not found[0m
)
goto end

REM ============================================
REM Clean cache files
REM ============================================
:clean
echo [93mCleaning cache files...[0m
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo [92mClean complete![0m
goto end

REM ============================================
REM Show system information
REM ============================================
:info
echo [94mSystem Information:[0m
echo.
echo Python version:
python --version
echo.
echo pip version:
pip --version
echo.
if exist "venv\" (
    echo [92mVirtual environment: EXISTS[0m
    call venv\Scripts\activate.bat
    echo.
    echo Installed packages in venv:
    pip list | findstr /i "fastapi uvicorn torch ultralytics opencv"
) else (
    echo [93mVirtual environment: NOT FOUND[0m
)
goto end

REM ============================================
REM Check server status
REM ============================================
:status
echo [94mChecking server status...[0m
curl -s http://localhost:5000/health >nul 2>&1
if errorlevel 1 (
    echo [91mServer is not running[0m
) else (
    echo [92mServer is running[0m
)
goto end

REM ============================================
REM Show API documentation URLs
REM ============================================
:docs
echo [92mAPI Documentation URLs:[0m
echo.
echo Swagger UI: http://localhost:5000/docs
echo ReDoc:      http://localhost:5000/redoc
echo.
echo [93mMake sure the server is running first![0m
goto end

REM ============================================
REM Quickstart
REM ============================================
:quickstart
echo [92mRunning quickstart...[0m
call :setup
if errorlevel 1 (
    echo [91mSetup failed![0m
    exit /b 1
)
call :run
goto end

:end
endlocal
