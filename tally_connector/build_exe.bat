@echo off
REM ============================================================
REM  Clearbook Tally Connector — Windows Build Script
REM  Run this from the tally_connector\ directory on a Windows
REM  machine with Python 3.11+ installed.
REM ============================================================

setlocal

echo.
echo  Clearbook Connector Build
echo  ========================
echo.

REM -- Check Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM -- Upgrade pip silently --
echo [1/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM -- Install dependencies --
echo [2/4] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

REM -- Run pywin32 post-install --
echo [3/4] Configuring pywin32...
python -c "import site; exec(open(site.getsitepackages()[0] + '/pywin32_postinstall.py').read())" -- -install >nul 2>&1

REM -- Build with PyInstaller --
echo [4/4] Building ClearbookConnector.exe ...
pyinstaller ClearbookConnector.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed. See output above.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Build complete!
echo   Output: dist\ClearbookConnector.exe
echo  ============================================================
echo.
pause
endlocal
