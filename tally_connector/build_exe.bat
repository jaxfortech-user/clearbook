@echo off
REM Build Clearbook Tally Connector as a standalone Windows EXE
REM Run this from inside the tally_connector\ directory
REM Requires: pip install pyinstaller pywin32 websockets httpx

echo Building ClearbookConnector.exe...

pyinstaller ^
  --onefile ^
  --noconsole ^
  --name "ClearbookConnector" ^
  --add-data "config.json;." ^
  connector.py

echo.
echo Done! EXE is at: dist\ClearbookConnector.exe
echo Distribute dist\ClearbookConnector.exe to the CA firm's Windows machine.
pause