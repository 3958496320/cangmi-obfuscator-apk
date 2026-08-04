@echo off
chcp 65001 >nul
title CangMi Obfuscator - Build EXE
cd /d "%~dp0"

echo ============================================
echo   CangMi Obfuscator - Build to EXE
echo   (CangMi Exclusive Obfuscator)
echo ============================================
echo.
echo This script packages the whole project into a single EXE.
echo After packaging, double-click the EXE to run (no Python needed).
echo.
echo Requirement: PyInstaller must be installed
echo   pip install pyinstaller
echo.

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

echo [ERROR] Python not found. Please install Python 3.7+
pause
exit /b 1

:found
echo [info] Using Python: %PYTHON_CMD%
echo.

REM Auto-install PyInstaller if missing
"%PYTHON_CMD%" -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [info] PyInstaller not found, installing...
    "%PYTHON_CMD%" -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] PyInstaller install failed. Run manually: pip install pyinstaller
        pause
        exit /b 1
    )
    echo [ok] PyInstaller installed
    echo.
)

echo [info] Building (may take 1-3 minutes)...
echo.
"%PYTHON_CMD%" build_exe.py

if %errorlevel%==0 (
    echo.
    echo ============================================
    echo [ok] Build complete!
    echo Output: dist\CangMiObfuscator.exe
    echo Double-click the EXE to run (no Python needed)
    echo ============================================
    echo.
    echo Open output folder?
    choice /c yn /m "Y=open folder N=exit"
    if errorlevel 2 exit /b 0
    explorer "dist"
) else (
    echo.
    echo [ERROR] Build failed, see error above
)
pause
