@echo off
chcp 65001 >nul
title 苍米独家混淆 · Ultimate Ninja Obfuscator
cd /d "%~dp0"

echo ============================================
echo   苍米独家混淆 v2.0 (12-Layer)
echo   Ultimate Ninja Obfuscator
echo ============================================
echo.

REM ============================================================
REM  自动搜索 Python 位置（不依赖 PATH 环境变量）
REM ============================================================
set "PYTHON_CMD="

REM 1. 先试 PATH 里的 python
where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto :found
)

REM 2. 再试 PATH 里的 py
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
    goto :found
)

REM 3. 搜索常见安装位置（按版本号从新到旧）
for %%V in (314 313 312 311 310 39 38 37) do (
    if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python%%V\python.exe"
        goto :found
    )
    if exist "C:\Python%%V\python.exe" (
        set "PYTHON_CMD=C:\Python%%V\python.exe"
        goto :found
    )
)

REM 4. 兜底：在 %LocalAppData%\Programs\Python 下找任何 Python3xx
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_CMD=%%D\python.exe"
        goto :found
    )
)

REM 5. 找不到 Python
echo [错误] 找不到 Python！
echo.
echo 已尝试以下位置均未找到 python.exe：
echo   - PATH 环境变量中的 python / py
echo   - %%LocalAppData%%\Programs\Python\Python3xx\
echo   - C:\Python3xx\
echo.
echo 解决方法：
echo   1. 确认 Python 已安装（访问 https://www.python.org/downloads/）
echo   2. 如果已安装，请把 python.exe 的完整路径发给我
echo.
pause
exit /b 1

:found
echo [info] 找到 Python：%PYTHON_CMD%
echo [info] 正在启动图形界面...
echo.
"%PYTHON_CMD%" src\gui.py

if %errorlevel% neq 0 (
    echo.
    echo [程序异常退出] 错误代码：%errorlevel%
    echo 按任意键关闭
    pause >nul
)
