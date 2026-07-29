# -*- coding: utf-8 -*-
"""
main.py
=======
Ultimate Ninja Obfuscator 命令行入口。

用法示例：
    python main.py input.lua -o output.lua
    python main.py input.lua -o output.lua --debug
    python main.py input.lua -o output.lua --seed 12345
    python main.py input.lua -o output.lua --reserve Foo Bar _G
    python main.py input.lua -o output.lua --expire 1735689600
    python main.py input.lua -o output.lua --disable-dyninst --disable-chunk-split
    python main.py input.lua -o output.lua --disable-anti-heuristic --disable-adaptive
    python main.py input.lua -o output.lua --force-profile medium
    python main.py input.lua -o output.lua --disable-loadstring

支持的开关（第 9~12 层均可单独关闭，满足技术红线）：
    --disable-dyninst          关闭第 9 层（动态指令替换）
    --disable-chunk-split      关闭第 10 层（代码块分割）
    --disable-anti-heuristic   关闭第 11 层（反启发式探测）
    --disable-adaptive         关闭第 12 层自适应（强制全开）
    --disable-loadstring       关闭第 8 层的 loadstring（其余保护保留）
"""

from __future__ import annotations
import argparse
import sys
import os

# 确保能 import 同目录下的模块（直接 python main.py 运行时）
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from obfuscator_core import obfuscate


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ultimate-ninja-obfuscator",
        description="终极·极限·兼容·自适应 Roblox Luau 脚本混淆工具（12 层）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input", help="输入 Luau 源码文件路径")
    p.add_argument("-o", "--output", help="输出文件路径（不指定则写到 stdout）")
    p.add_argument("--seed", type=int, default=None,
                   help="随机种子（指定则可复现；默认随机）")
    p.add_argument("--debug", action="store_true",
                   help="调试模式：注入隐蔽日志 + 输出统计到 stderr")
    p.add_argument("--reserve", nargs="*", default=[],
                   help="自定义保留名列表（不被重命名/加密），空格分隔")
    p.add_argument("--expire", type=int, default=None,
                   help="时间炸弹过期时间戳（秒，UTC）；不指定则不启用")
    # 第 9~12 层开关
    p.add_argument("--disable-dyninst", action="store_true",
                   help="关闭第 9 层（动态指令替换）")
    p.add_argument("--disable-chunk-split", action="store_true",
                   help="关闭第 10 层（代码块分割）")
    p.add_argument("--disable-anti-heuristic", action="store_true",
                   help="关闭第 11 层（反启发式探测）")
    p.add_argument("--disable-adaptive", action="store_true",
                   help="关闭第 12 层自适应（强制全开）")
    p.add_argument("--disable-loadstring", action="store_true",
                   help="关闭第 8 层的 loadstring（其余保护保留）")
    p.add_argument("--force-profile", choices=["small", "medium", "large"],
                   default=None, help="强制档位（调试用）")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    # 读取输入
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        sys.stderr.write(f"[error] 无法读取输入文件 {args.input}: {e}\n")
        return 2

    # 执行混淆
    try:
        result = obfuscate(
            src=src,
            seed=args.seed,
            debug=args.debug,
            reserve_names=set(args.reserve) if args.reserve else None,
            expire_ts=args.expire,
            disable_dyninst=args.disable_dyninst,
            disable_chunk_split=args.disable_chunk_split,
            disable_anti_heuristic=args.disable_anti_heuristic,
            disable_adaptive=args.disable_adaptive,
            force_profile=args.force_profile,
            disable_loadstring=args.disable_loadstring,
        )
    except Exception as e:
        sys.stderr.write(f"[error] 混淆失败: {e}\n")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 3

    code = result["code"]

    # 输出
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(code)
        except OSError as e:
            sys.stderr.write(f"[error] 无法写入输出文件 {args.output}: {e}\n")
            return 4
        sys.stderr.write(
            f"[ok] 已写出 {len(code)} 字节到 {args.output} "
            f"(profile={result['profile'].get('name')})\n")
    else:
        sys.stdout.write(code)
        if not code.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
