# -*- coding: utf-8 -*-
"""
build_exe.py
============
苍米独家混淆 · 一键打包脚本。

使用 PyInstaller 将整个项目打包成单文件 exe，用户双击即可运行，无需安装 Python。

用法：
    python build_exe.py            # 打包成单文件 exe
    python build_exe.py --onedir   # 打包成目录（启动更快）

前置条件：
    pip install pyinstaller

输出：
    dist/苍米独家混淆.exe          (--onefile，单文件)
    dist/苍米独家混淆/             (--onedir，目录)
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "src")
# 注意：APP_NAME 用英文，避免 Windows 资源管理器对中文 exe 名的显示问题
# 程序内部 UI 仍显示"苍米独家混淆"
APP_NAME = "CangMiObfuscator"
ENTRY = os.path.join(SRC_DIR, "gui.py")


def check_pyinstaller() -> bool:
    """检查 PyInstaller 是否已安装。"""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def install_pyinstaller() -> bool:
    """自动安装 PyInstaller。"""
    print("[info] 正在安装 PyInstaller …")
    ret = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        capture_output=False,
    )
    return ret.returncode == 0


def clean_build_dirs():
    """清理旧的 build / dist 目录。"""
    for d in ["build", "dist"]:
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            print(f"[info] 清理 {p}")
            shutil.rmtree(p, ignore_errors=True)
    spec = os.path.join(HERE, f"{APP_NAME}.spec")
    if os.path.exists(spec):
        os.remove(spec)


def build(onefile: bool = True, windowed: bool = True):
    """执行 PyInstaller 打包。

    参数：
        onefile:  True=单文件 exe；False=目录模式。
        windowed: True=无控制台窗口（GUI 程序）；False=保留控制台。
    """
    if not os.path.isfile(ENTRY):
        print(f"[error] 入口文件不存在: {ENTRY}")
        return False

    if not check_pyinstaller():
        if not install_pyinstaller():
            print("[error] PyInstaller 安装失败，请手动执行: pip install pyinstaller")
            return False

    clean_build_dirs()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--add-data", f"{SRC_DIR}{os.pathsep}src",
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    if windowed:
        cmd.append("--windowed")
    # 入口
    cmd.append(ENTRY)

    print("[info] 执行打包命令:")
    print("  " + " ".join(cmd))
    print()

    ret = subprocess.run(cmd, cwd=HERE)
    if ret.returncode != 0:
        print("[error] 打包失败")
        return False

    # 结果
    if onefile:
        out = os.path.join(HERE, "dist", f"{APP_NAME}.exe")
    else:
        out = os.path.join(HERE, "dist", APP_NAME)
    print()
    print("=" * 60)
    print("[ok] 打包成功！")
    print(f"[ok] 输出: {out}")
    if onefile:
        print(f"[ok] 双击 {APP_NAME}.exe 即可运行（无需安装 Python）")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="苍米独家混淆 · 一键打包成 exe")
    parser.add_argument("--onedir", action="store_true",
                        help="打包成目录模式（启动更快，但需分发整个目录）")
    parser.add_argument("--console", action="store_true",
                        help="保留控制台窗口（调试用，可看到错误输出）")
    args = parser.parse_args()

    ok = build(onefile=not args.onedir, windowed=not args.console)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
