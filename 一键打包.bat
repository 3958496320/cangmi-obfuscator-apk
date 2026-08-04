@echo off
chcp 65001 >nul
title 苍米独家混淆 · 一键打包成 exe
cd /d "%~dp0"

echo ============================================
echo   苍米独家混淆 · 打包成 exe 安装包
echo ============================================
echo.
echo 此脚本会把整个项目打包成单文件 exe，
echo 打包后双击 exe 即可运行，无需安装 Python。
echo.
echo 前置条件：需要先安装 PyInstaller
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

echo [错误] 找不到 Python，请先安装 Python 3.7+
pause
exit /b 1

:found
echo [info] 使用 Python：%PYTHON_CMD%
echo.

REM 自动安装 PyInstaller（如果未安装）
"%PYTHON_CMD%" -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [info] 未检测到 PyInstaller，正在自动安装...
    "%PYTHON_CMD%" -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [错误] PyInstaller 安装失败，请手动执行: pip install pyinstaller
        pause
        exit /b 1
    )
    echo [ok] PyInstaller 安装成功
    echo.
)

echo [info] 开始打包（可能需要 1-3 分钟）...
echo.
"%PYTHON_CMD%" build_exe.py

if %errorlevel%==0 (
    echo.
    echo ============================================
    echo [ok] 打包完成！
    echo 输出位置: dist\苍米独家混淆.exe
    echo 双击 exe 即可运行，无需安装 Python
    echo ============================================
    echo.
    echo 是否打开输出目录？
    choice /c yn /m "Y=打开目录 N=退出"
    if errorlevel 2 exit /b 0
    explorer "dist"
) else (
    echo.
    echo [错误] 打包失败，请查看上方错误信息
)
pause
