# -*- coding: utf-8 -*-
"""box（共享 upvalue）语义专项测试：验证 vm_pro 修复后的闭包语义正确性。"""
import sys
sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import obfuscate

CASES = [
    ("S1_共享upvalue计数器",
     'local n = 0 local function inc() n = n + 1 end inc() inc() inc() print(n)',
     "3"),
    ("S2_两个闭包共享同一变量",
     'local x = 1 local function set(v) x = v end local function get() return x end set(42) print(get())',
     "42"),
    ("S3_计数器工厂_各自独立",
     'local function make() local n = 0 return function() n = n + 1 return n end end '
     'local a = make() local b = make() a() a() b() print(a(), b(), a())',
     "3\t2\t4"),
    ("S4_闭包修改外层可见",
     'local total = 0 local items = {1, 2, 3, 4, 5} '
     'for _, v in ipairs(items) do local function add() total = total + v end add() end print(total)',
     "15"),
    ("S5_for循环变量捕获",
     'local fns = {} for i = 1, 3 do fns[i] = function() return i end end '
     'print(fns[1](), fns[2](), fns[3]())',
     "1\t2\t3"),
    ("S6_forin循环变量捕获",
     'local fns = {} for k, v in pairs({10, 20, 30}) do fns[k] = function() return v end end '
     'print(fns[1](), fns[2](), fns[3]())',
     "10\t20\t30"),
    ("S7_参数捕获工厂",
     'local function makeAdder(n) return function(x) return x + n end end '
     'local a1 = makeAdder(1) local a2 = makeAdder(100) print(a1(9), a2(9))',
     "10\t109"),
    ("S8_捕获函数值调用",
     'local function handler(x) return x * 2 end '
     'local function wrapper() return handler(21) end print(wrapper())',
     "42"),
    ("S9_顶层调用被捕获函数",
     'local function helper() return 7 end '
     'local function user() return helper() end print(helper() + user())',
     "14"),
    ("S10_嵌套两层闭包",
     'local function outer() local a = 1 local function mid() a = a + 10 '
     'local function inner() a = a + 100 return a end return inner end '
     'local i = mid() return i() + a end print(outer())',
     "222"),
    ("S11_闭包捕获表并修改",
     'local t = {count = 0} local function bump() t.count = t.count + 5 end '
     'bump() bump() print(t.count)',
     "10"),
    ("S12_前向声明conn再赋值",
     'local conn local function setup() conn = {Disconnect = function() print("DC") end} end '
     'setup() conn:Disconnect() print("ok")',
     "DC\nok"),
    ("S13_while循环内闭包",
     'local log = {} local i = 0 while i < 3 do i = i + 1 '
     'local function save() log[#log+1] = i end save() end print(log[1], log[2], log[3])',
     "1\t2\t3"),
    ("S14_递归函数被捕获",
     'local function fact(n) if n <= 1 then return 1 end return n * fact(n-1) end '
     'local function call() return fact(5) end print(call())',
     "120"),
    ("S15_互递归",
     'local function isEven(n) if n == 0 then return true end return isOdd(n - 1) end '
     'local function isOdd(n) if n == 0 then return false end return isEven(n - 1) end '
     'print(tostring(isEven(10)), tostring(isOdd(7)))',
     "true\ttrue"),
    ("S16_闭包数组累加",
     'local sum = 0 local fns = {} for i = 1, 5 do fns[i] = function() sum = sum + i end end '
     'for i = 1, 5 do fns[i]() end print(sum)',
     "15"),
]


def run_case(name, src, expected, seed):
    try:
        result = obfuscate(src, seed=seed)
        code = result["code"]
        if not code:
            return False, "obf returned empty"
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()

        def _cap(*args):
            outputs.append("\t".join(str(a) for a in args))
        g["print"] = _cap
        g["__OMNISHIELD_LOADED"] = None
        lua.execute(code)
        out = "\n".join(outputs)
        if str(expected) in out:
            return True, out[:60]
        return False, f"expected '{expected}' got '{out[:60]}'"
    except Exception as e:
        return False, str(e).replace("\n", " ")[:120]


def main():
    total = passed = 0
    fails = []
    for name, src, expected in CASES:
        for seed in (1, 42, 2024):
            total += 1
            ok, msg = run_case(name, src, expected, seed)
            if ok:
                passed += 1
            else:
                fails.append((name, seed, msg))
        # 每 case 只打一行
        ok_seeds = [s for s in (1, 42, 2024)
                    if run_case(name, src, expected, s)[0]]
        status = "PASS" if len(ok_seeds) == 3 else f"FAIL({len(ok_seeds)}/3)"
        print(f"  {name}: {status}", flush=True)
    print(f"\n结果: {passed}/{total} 通过")
    if fails:
        print("失败明细:")
        for name, seed, msg in fails[:10]:
            print(f"  {name} seed={seed}: {msg}")


if __name__ == "__main__":
    main()
