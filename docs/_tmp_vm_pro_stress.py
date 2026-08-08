# -*- coding: utf-8 -*-
"""扩展压力测试：更复杂的脚本场景，验证 VM 鲁棒性。"""
import os
import sys
import random

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile

# 更复杂的测试样本
SAMPLES = [
    # 嵌套函数调用 + 多返回值
    ('local function f(a, b) return a + b, a - b end local x, y = f(10, 3) print(x, y)', "13\t7"),
    # 递归
    ('local function fib(n) if n < 2 then return n end return fib(n-1) + fib(n-2) end print(fib(10))', "55"),
    # 闭包
    ('local function counter() local c = 0 return function() c = c + 1 return c end end local f = counter() print(f()) print(f()) print(f())', "1\n2\n3"),
    # 字符串拼接
    ('local s = "" for i = 1, 5 do s = s .. tostring(i) end print(s)', "12345"),
    # 嵌套表
    ('local t = {a = {b = {c = 42}}} print(t.a.b.c)', "42"),
    # 数组 + ipairs
    ('local t = {10, 20, 30, 40, 50} local max = t[1] for i = 2, #t do if t[i] > max then max = t[i] end end print(max)', "50"),
    # While + break
    ('local i = 1 while true do if i == 5 then break end i = i + 1 end print(i)', "5"),
    # Repeat-until
    ('local i = 0 repeat i = i + 1 until i >= 5 print(i)', "5"),
    # 条件嵌套
    ('local x = 10 local y = 20 if x > y then print("X") elseif x == y then print("E") else print("Y") end', "Y"),
    # 全局变量
    ('G_VAR = 42 local function getG() return G_VAR end print(getG())', "42"),
    # 字符串比较
    ('local s = "hello" if s == "hello" then print("MATCH") end', "MATCH"),
    # 长度操作符
    ('local t = {1, 2, 3, 4, 5} print(#t)', "5"),
    # 嵌套循环
    ('local s = 0 for i = 1, 3 do for j = 1, 3 do s = s + 1 end end print(s)', "9"),
    # 方法调用
    ('local t = {x = 10} function t:getX() return self.x end print(t:getX())', "10"),
    # 多重赋值
    ('local a, b, c = 1, 2, 3 print(a + b + c)', "6"),
    # 变量交换
    ('local a, b = 1, 2 a, b = b, a print(a, b)', "2\t1"),
    # 字符串长度
    ('print(#"hello")', "5"),
    # 取模
    ('print(17 % 5)', "2"),
    # 幂运算
    ('print(2 ^ 10)', "1024"),
    # 简单冒泡排序
    ('local arr = {5, 3, 8, 1, 9, 2} for i = 1, #arr-1 do for j = 1, #arr-i do if arr[j] > arr[j+1] then arr[j], arr[j+1] = arr[j+1], arr[j] end end end print(arr[1], arr[2], arr[3], arr[4], arr[5], arr[6])', "1\t2\t3\t5\t8\t9"),
]


def run_one(src, expected, seed):
    try:
        rng = random.Random(seed)
        gen = NameGenerator(rng)
        ast = parse_source(src)
        if not ast:
            return False, "parse failed"
        code = vm_pro_compile(ast, rng, gen)
        if not code:
            return False, "vm_pro_compile returned None"
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
        lua.execute(code)
        out_str = "\n".join(outputs)
        if expected in out_str:
            return True, out_str[:80]
        return False, f"expected '{expected}' got '{out_str[:80]}'"
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        return False, msg


def main():
    print("=" * 70, flush=True)
    print("vm_pro.py 扩展压力测试", flush=True)
    print("=" * 70, flush=True)
    total = passed = 0
    failed = []
    for idx, (src, expected) in enumerate(SAMPLES):
        for seed in [1, 2, 3]:
            total += 1
            ok, info = run_one(src, expected, seed)
            label = f"E{idx+1:02d}_seed{seed}"
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
