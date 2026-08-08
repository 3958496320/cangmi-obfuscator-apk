# -*- coding: utf-8 -*-
"""P2 三件套验证测试：自擦除 + 寄存器虚拟化 + 解释器分片嵌套"""
import os
import sys
import random

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile

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
    # 闭包捕获变量
    ('local function makeAdder(n) return function(x) return x + n end end '
     'local add5 = makeAdder(5) local add10 = makeAdder(10) '
     'print(add5(3), add10(3))', "8\t13"),
    # 递归
    ('local function fact(n) if n <= 1 then return 1 end return n * fact(n - 1) end '
     'print(fact(5))', "120"),
    # 嵌套循环
    ('local s = 0 for i = 1, 3 do for j = 1, 3 do s = s + i * j end end print(s)', "36"),
    # 字符串操作
    ('local s = "" for i = 1, 5 do s = s .. tostring(i) end print(s)', "12345"),
    # break
    ('local s = 0 for i = 1, 100 do if i > 5 then break end s = s + i end print(s)', "15"),
    # 负数
    ('print(-5 + 10)', "5"),
    # 比较
    ('print(3 < 5, 5 > 3, 3 == 3)', "true\ttrue\ttrue"),
    # and/or
    ('print(true and "yes" or "no")', "yes"),
    # 多返回值
    ('local function multi() return 1, 2, 3 end local a, b, c = multi() print(a + b + c)', "6"),
    # 局部函数表
    ('local t = {} t.foo = function() return 42 end print(t.foo())', "42"),
    # 数学运算
    ('print(100 // 7)', "14"),
    # 字符串长度
    ('print(#"hello")', "5"),
    # nil 检查
    ('local x = nil if x == nil then print("NIL") end', "NIL"),
    # method call
    ('local t = {x = 10} function t:getx() return self.x end print(t:getx())', "10"),
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
        def _fmt(a):
            if a is True:
                return "true"
            if a is False:
                return "false"
            return str(a)
        g["print"] = lambda *a: outputs.append("\t".join(_fmt(x) for x in a))
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
    print("P2 三件套验证测试 (自擦除 + 寄存器虚拟化 + 分片嵌套)", flush=True)
    print("=" * 70, flush=True)
    total = passed = 0
    failed = []
    for idx, (src, expected) in enumerate(SAMPLES):
        # 每个 sample 测试 3 个种子
        for seed in range(3):
            total += 1
            ok, msg = run_one(src, expected, seed)
            if ok:
                passed += 1
            else:
                failed.append((idx, seed, src[:50], msg))
    print(f"\n{'=' * 70}", flush=True)
    print(f"结果: {passed}/{total} 通过", flush=True)
    if failed:
        print(f"\n失败 {len(failed)} 个:", flush=True)
        for idx, seed, src, msg in failed[:20]:
            print(f"  [{idx}] seed={seed}: {src}", flush=True)
            print(f"       -> {msg}", flush=True)
    else:
        print("全部通过!", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
