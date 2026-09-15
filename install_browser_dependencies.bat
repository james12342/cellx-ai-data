@echo off
python -m pip install --user -r "%~dp0cellx-extension-api\requirements-browser.txt"
if errorlevel 1 exit /b 1
echo Browser dependencies installed. Microsoft Edge must be installed.
pause
