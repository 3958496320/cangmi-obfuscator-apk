# -*- coding: utf-8 -*-
"""独立测试 vm_pro.py：编译小脚本并在 LuaJIT 下执行验证输出。"""
import os
import sys
import time

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import parse_source, NameGenerator
import random
from vm_pro import vm_pro_compile

# 小测试样本：(源码, 期望输出包含)
SAMPLES = [
    ('print("HELLO_VM")', "HELLO_VM"),
    ('print(1 + 2 * 3)', "7"),
    ('print("a" .. "b" .. "c")', "abc"),
    ('local x = 10 local y = 20 print(x + y)', "30"),
    ('local function f(a, b) return a + b end print(f(3, 4))', "7"),
    ('local t = {10, 20, 30} local s = 0 for _, v in ipairs(t) do s = s + v end print(s)', "60"),
    ('local s = 0 for i = 1, 10 do s = s + i end print(s)', "55"),
    ('local x = 5 if x > 3 then print("BIG") else print("SMALL") end', "BIG"),
    ('local i = 0 while i < 5 do i = i + 1 end print(i)', "5"),
    ('local t = {a = 1, b = 2} print(t.a + t.b)', "3"),
]


def run_one(src, expected, seed):
    try:
        rng = random.Random(seed)
        gen = NameGenerator(rng)
        ast = parse_source(src)
        if not ast:
            return False, "parse failed", 0
        code = vm_pro_compile(ast, rng, gen)
        if not code:
            return False, "vm_pro_compile returned None", 0
        # 在 LuaJIT 执行
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
        lua.execute(code)
        out_str = "\n".join(outputs)
        if expected in out_str:
            return True, out_str[:80], 0
        return False, f"expected '{expected}' got '{out_str[:80]}'", 0
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        return False, msg, 0


def main():
    print("=" * 70, flush=True)
    print("vm_pro.py 独立测试", flush=True)
    print("=" * 70, flush=True)
    total = passed = 0
    failed = []
    for idx, (src, expected) in enumerate(SAMPLES):
        for seed in [1, 2, 3]:
            total += 1
            ok, info, _ = run_one(src, expected, seed)
            label = f"S{idx+1:02d}_seed{seed}"
            if ok:
                passed += 1
                print(f"[{label}] PASS  {info}", flush=True)
            else:
                failed.append(f"{label}: {info}")
                print(f"[{label}] FAIL  {info}", flush=True)
    print("=" * 70, flush=True)
    print(f"总计: {total}  通过: {passed}  失败: {total-passed}", flush=True)
    if failed:
        print("失败列表:", flush=True)
        for f in failed:
            print(f"  - {f}", flush=True)
    print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====", flush=True)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
