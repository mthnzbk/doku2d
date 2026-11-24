@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
if exist "%ROOT%\.venv\Scripts\python.exe" (
    "%ROOT%\.venv\Scripts\python.exe" -m doku2d %*
) else (
    where py >nul 2>nul
    if errorlevel 1 (python -m doku2d %*) else (py -m doku2d %*)
)
exit /b %errorlevel%
