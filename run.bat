@echo off
cd /d %~dp0
if not exist .venv\Scripts\activate.bat (
  echo Please run install_and_run.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate
python app.py
