@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_CMD="

where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto :found
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
    goto :found
)

for %%V in (314 313 312 311 310 39 38 37) do (
    if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python%%V\python.exe"
        goto :found
    )
)

echo [error] Python not found. Please install Python 3.7+
pause
exit /b 1

:found
"%PYTHON_CMD%" src\gui.py
if %errorlevel% neq 0 pause
