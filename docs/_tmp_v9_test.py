# -*- coding: utf-8 -*-
"""v9 新功能测试：函数内联/函数包装/常量数组化/MBA表达式/嵌套VM。"""
import os
import sys
import random

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import (
    parse_source, NameGenerator, obfuscate, obfuscate_code,
    apply_function_inline, apply_function_wrap,
    apply_const_arrayify, apply_mba_expr, apply_const_encrypt,
    generate_code, _BIT32_FALLBACK,
)
from vm_pro import vm_pro_compile


# bit32 回退（standalone 测试需要，完整管道自动注入）
_BIT32_PRELUDE = _BIT32_FALLBACK + "\n"


# 测试样本
SAMPLES = [
    # 基本算术
    ('print(1 + 2)', "3"),
    # 函数调用
    ('local function add(a, b) return a + b end print(add(3, 4))', "7"),
    # 字符串
    ('local s = "hello" print(s)', "hello"),
    # 循环
    ('local s = 0 for i = 1, 10 do s = s + i end print(s)', "55"),
    # 条件
    ('local x = 5 if x > 3 then print("BIG") else print("SMALL") end', "BIG"),
    # 表
    ('local t = {10, 20, 30} print(t[1] + t[2] + t[3])', "60"),
    # 嵌套函数
    ('local function outer() local function inner() return 42 end return inner() end print(outer())', "42"),
    # 多返回值
    ('local function f() return 1, 2, 3 end local a, b, c = f() print(a + b + c)', "6"),
    # 递归
    ('local function fact(n) if n <= 1 then return 1 end return n * fact(n-1) end print(fact(5))', "120"),
    # 全局变量
    ('G_VAL = 99 local function getG() return G_VAL end print(getG())', "99"),
    # 常量重复（测试常量数组化）
    ('local x = 42 local y = 42 local z = 42 print(x + y + z)', "126"),
    # 重复数字（测试MBA表达式）
    ('local a = 5 local b = 5 print(a + b)', "10"),
    # 闭包
    ('local function counter() local c = 0 return function() c = c + 1 return c end end local f = counter() print(f()) print(f())', "1\n2"),
    # while 循环
    ('local i = 0 while i < 5 do i = i + 1 end print(i)', "5"),
    # repeat
    ('local i = 0 repeat i = i + 1 until i >= 3 print(i)', "3"),
]


def test_individual_transforms():
    """测试单个变换函数。"""
    print("=" * 70)
    print("测试 1: 单独变换函数")
    print("=" * 70)
    passed = failed = 0

    for src, expected in SAMPLES:
        for transform_name, transform_fn in [
            ("function_inline", lambda c, r: apply_function_inline(c, r)),
            ("function_wrap", lambda c, r: apply_function_wrap(c, r)),
            ("const_arrayify", lambda c, r: apply_const_arrayify(c, r)),
            ("mba_expr", lambda c, r: apply_mba_expr(c, r)),
            ("const_encrypt", lambda c, r: apply_const_encrypt(c, r)),
        ]:
            try:
                rng = random.Random(42)
                gen = NameGenerator(rng)
                chunk = parse_source(src)
                if not chunk:
                    raise Exception("parse failed")
                transform_fn(chunk, rng)
                # 生成代码并执行（注入 bit32 回退）
                code = generate_code(chunk)
                code = _BIT32_PRELUDE + code
                outputs = []
                lua = LuaRuntime(unpack_returned_tuples=True)
                g = lua.globals()
                g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
                lua.execute(code)
                out_str = "\n".join(outputs)
                if expected in out_str:
                    passed += 1
                else:
                    failed += 1
                    print(f"  FAIL [{transform_name}] src='{src[:50]}' expected='{expected}' got='{out_str[:80]}'")
            except Exception as e:
                failed += 1
                msg = str(e).replace("\n", " ")[:120]
                print(f"  ERR  [{transform_name}] src='{src[:50]}' err='{msg}'")

    print(f"单独变换: 通过 {passed}  失败 {failed}")
    return failed == 0


def test_full_obfuscate():
    """测试完整混淆管道（12层 + vm_pro）。"""
    print("=" * 70)
    print("测试 2: 完整混淆管道 (obfuscate)")
    print("=" * 70)
    passed = failed = 0

    for src, expected in SAMPLES:
        try:
            result = obfuscate(src, seed=42)
            code = result["code"]
            outputs = []
            lua = LuaRuntime(unpack_returned_tuples=True)
            g = lua.globals()
            g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
            lua.execute(code)
            out_str = "\n".join(outputs)
            if expected in out_str:
                passed += 1
            else:
                failed += 1
                print(f"  FAIL src='{src[:50]}' expected='{expected}' got='{out_str[:80]}'")
        except Exception as e:
            failed += 1
            msg = str(e).replace("\n", " ")[:120]
            print(f"  ERR  src='{src[:50]}' err='{msg}'")

    print(f"完整混淆: 通过 {passed}  失败 {failed}")
    return failed == 0


def test_nested_vm():
    """测试 VM 嵌套 VM。"""
    print("=" * 70)
    print("测试 3: VM 嵌套 VM (enable_nested_vm)")
    print("=" * 70)
    passed = failed = 0

    # 小脚本测试嵌套VM
    small_samples = [
        ('print(1 + 2)', "3"),
        ('local function add(a, b) return a + b end print(add(3, 4))', "7"),
        ('local s = "hello" print(s)', "hello"),
        ('local s = 0 for i = 1, 5 do s = s + i end print(s)', "15"),
        ('local x = 5 if x > 3 then print("BIG") else print("SMALL") end', "BIG"),
    ]

    for src, expected in small_samples:
        try:
            rng = random.Random(42)
            gen = NameGenerator(rng)
            chunk = parse_source(src)
            if not chunk:
                raise Exception("parse failed")
            code = vm_pro_compile(chunk, rng, gen, enable_nested_vm=True)
            if not code:
                raise Exception("vm_pro_compile returned None")
            outputs = []
            lua = LuaRuntime(unpack_returned_tuples=True)
            g = lua.globals()
            g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
            lua.execute(code)
            out_str = "\n".join(outputs)
            if expected in out_str:
                passed += 1
                print(f"  PASS src='{src[:40]}' -> '{out_str[:30]}'")
            else:
                failed += 1
                print(f"  FAIL src='{src[:40]}' expected='{expected}' got='{out_str[:80]}'")
        except Exception as e:
            failed += 1
            msg = str(e).replace("\n", " ")[:120]
            print(f"  ERR  src='{src[:40]}' err='{msg}'")

    print(f"嵌套VM: 通过 {passed}  失败 {failed}")
    return failed == 0


def test_switches():
    """测试 vm_pro 开关组合。"""
    print("=" * 70)
    print("测试 4: VM 开关组合")
    print("=" * 70)
    passed = failed = 0

    src = 'local function add(a, b) return a + b end print(add(3, 4))'
    expected = "7"

    for nested in [False, True]:
        for reg_virt in [True, False]:
            for anti_hook in [True, False]:
                label = f"nested={nested} reg_virt={reg_virt} anti_hook={anti_hook}"
                try:
                    rng = random.Random(42)
                    gen = NameGenerator(rng)
                    chunk = parse_source(src)
                    code = vm_pro_compile(chunk, rng, gen,
                                          enable_nested_vm=nested,
                                          enable_register_virt=reg_virt,
                                          enable_anti_hook=anti_hook)
                    if not code:
                        raise Exception("returned None")
                    outputs = []
                    lua = LuaRuntime(unpack_returned_tuples=True)
                    g = lua.globals()
                    g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
                    lua.execute(code)
                    out_str = "\n".join(outputs)
                    if expected in out_str:
                        passed += 1
                        print(f"  PASS [{label}]")
                    else:
                        failed += 1
                        print(f"  FAIL [{label}] got='{out_str[:80]}'")
                except Exception as e:
                    failed += 1
                    msg = str(e).replace("\n", " ")[:120]
                    print(f"  ERR  [{label}] err='{msg}'")

    print(f"开关组合: 通过 {passed}  失败 {failed}")
    return failed == 0


def main():
    ok1 = test_individual_transforms()
    ok2 = test_full_obfuscate()
    ok3 = test_nested_vm()
    ok4 = test_switches()

    print("=" * 70)
    all_ok = ok1 and ok2 and ok3 and ok4
    print(f"总计: {'ALL PASS' if all_ok else 'HAS FAIL'}")
    print("=" * 70)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
