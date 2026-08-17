# -*- coding: utf-8 -*-
"""VM 语义等价性回归测试。

对每个用例：
1. 直接在 lupa(Lua 5.5) 中执行原始脚本，捕获 print 输出
2. 分别用 vm_pro_compile（VM 直出，含嵌套/非嵌套）与 obfuscate（全管线）混淆
3. 再次执行，输出必须逐行一致
4. 多次迭代（随机种子不同）覆盖 LOADKN 方言比例 / handler 变异 / 变体码随机

用法: python3 test_vm_semantic.py [quick]
"""
import random
import sys

sys.path.insert(0, "/workspace/src")

import lupa

from obfuscator_core import obfuscate, obfuscate_code, NameGenerator, parse_source
from vm_pro import vm_pro_compile

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"

CASES = [
    ("arith_numeric", """
local a = 42
local b = 3.5
local c = a + b * 2 - 1
print(c)
print(a // 7, a % 7)
print((a ^ 2) == 1764)
local neg = -7
print(neg * 3, -neg)
print(2 ^ 31, 2 ^ -1)
"""),
    ("numeric_consts_dense", """
local s = 0
local xs = {5, 12, 33, 47, 58, 61, 74, 86, 99, 100}
for i = 1, #xs do s = s + xs[i] * i end
print(s)
print(1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10)
print(0.5 + 1.25, 100 - 33.3 > 66)
local t = 7
print(t .. "|" .. 9 .. "|" .. 123)
"""),
    ("strings", """
local s1 = "hello"
local s2 = s1 .. " " .. "world"
print(s2, #s2)
print(s2:upper(), s2:sub(1, 5), s2:sub(-5))
print(string.rep("ab", 3), string.format("%s=%d", "x", 42))
print(("key1"):len(), "a" < "b", "z" > "a")
"""),
    ("control_flow", """
for i = 1, 10 do
    if i % 2 == 0 then
        print("even", i)
    elseif i % 3 == 0 then
        print("three", i)
    else
        print("odd", i)
    end
end
local n = 0
while n < 5 do n = n + 1 end
print("n", n)
repeat n = n - 2 until n <= 0
print("n2", n)
for i = 10, 1, -3 do print("down", i) end
"""),
    ("closures_upvalues", """
local function counter()
    local count = 0
    return function()
        count = count + 1
        return count
    end
end
local c1 = counter()
local c2 = counter()
print(c1(), c1(), c1())
print(c2(), c2())
local funcs = {}
for i = 1, 3 do funcs[i] = function() return i * 10 end end
for i = 1, 3 do print("f", funcs[i]()) end
"""),
    ("functions_multiret", """
local function multi()
    return 1, "two", 3.5
end
local a, b, c = multi()
print(a, b, c)
print((multi()))
local function pass(...)
    return select('#', ...), ...
end
print(pass(10, nil, 30))
local function tail(...)
    return multi(...)
end
print(tail())
local t = {multi()}
print(#t, t[1], t[3])
"""),
    ("varargs", """
local function sum(...)
    local s = 0
    for i = 1, select('#', ...) do
        local v = select(i, ...)
        if type(v) == "number" then s = s + v end
    end
    return s
end
print(sum(1, 2, 3, 4, 5))
print(sum())
local function pack(...)
    return {...}, select('#', ...)
end
local t, n = pack(7, 8, 9)
print(n, t[1] + t[2] + t[3])
"""),
    ("tables", """
local t = {}
t.x = 1
t["y"] = 2
t[3] = "three"
print(t.x + t.y, t[3])
local nested = {a = {b = {c = "deep"}}}
print(nested.a.b.c)
local arr = {10, 20, 30}
table.insert(arr, 40)
print(#arr, arr[4])
local keys = {}
for k, v in pairs({p = 1, q = 2}) do keys[#keys + 1] = k .. "=" .. v end
table.sort(keys)
print(keys[1], keys[2])
print(table.concat({1, 2, 3}, ","))
"""),
    ("methods_self", """
local obj = {}
obj.__index = obj
function obj:new(v)
    return setmetatable({val = v}, self)
end
function obj:get()
    return self.val
end
function obj:add(x)
    self.val = self.val + x
    return self
end
local o = obj:new(100)
print(o:get())
print(o:add(5):add(5):get())
"""),
    ("recursion_pcall", """
local function fib(n)
    if n < 2 then return n end
    return fib(n - 1) + fib(n - 2)
end
print(fib(20))
local ok, err = pcall(function() error("boom") end)
print(ok, err ~= nil)
local ok2, v = pcall(function() return "fine" end)
print(ok2, v)
"""),
    ("bitwise", """
local a = 0xF0
local b = 0x0F
print(a ~ b, a & b, a | b, a ~ a)
print(1 << 10, 1024 >> 3)
print(~0, 5 // 2, -5 // 2, 5.0 // 2)
"""),
    ("shadowing_scope", """
local x = 1
do
    local x = 10
    print("inner", x)
end
print("outer", x)
local i = 100
for i = 1, 3 do print("loop", i) end
print("after", i)
"""),
]


def fmt_lua(x):
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return str(int(x))
        return repr(x)
    if x is None:
        return "nil"
    return str(x)


def run_lua_capture(code):
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    buf = []

    def _print(*args):
        buf.append("\t".join(fmt_lua(a) for a in args))

    lua.globals()["print"] = _print
    lua.execute(code)
    return buf


def check(name, src, obf_fn, iterations):
    expect = run_lua_capture(src)
    fails = 0
    for it in range(iterations):
        try:
            out_code = obf_fn(src)
        except Exception as ex:
            print(f"[FAIL] {name} iter{it}: obfuscate exception: {ex}")
            fails += 1
            continue
        try:
            got = run_lua_capture(out_code)
        except Exception as ex:
            print(f"[FAIL] {name} iter{it}: runtime exception: {ex}")
            fails += 1
            continue
        if got != expect:
            fails += 1
            print(f"[FAIL] {name} iter{it}: output mismatch")
            print(f"  expect({len(expect)}): {expect[:6]}")
            print(f"  got   ({len(got)}): {got[:6]}")
    return fails


def vm_direct(nested):
    def fn(src):
        rng = random.Random()
        chunk = parse_source(src)
        gen = NameGenerator(rng)
        code = vm_pro_compile(chunk, rng, gen,
                              enable_nested_vm=nested,
                              enable_register_virt=True,
                              enable_anti_hook=True)
        if not code:
            raise RuntimeError("vm_pro_compile returned None")
        return code
    return fn


def full_pipeline(src):
    r = obfuscate(src, disable_vm=False, disable_vm_pro=False,
                  disable_dyninst=False, disable_loadstring=False)
    if r["stats"].get("vm_pro") not in ("enabled+nested+regvirt+antihook",
                                        "enabled+regvirt+antihook"):
        raise RuntimeError("vm_pro fallback: %r" % r["stats"].get("vm_pro"))
    return r["code"]


def main():
    total_fail = 0
    total_run = 0
    vm_iters = 2 if QUICK else 3
    pipe_iters = 1 if QUICK else 2
    for name, src in CASES:
        total_run += 1
        f = check(name + "/vm", src, vm_direct(False), vm_iters)
        total_fail += f
    for name, src in CASES:
        total_run += 1
        f = check(name + "/vm-nested", src, vm_direct(True), vm_iters)
        total_fail += f
    if not QUICK:
        for name, src in CASES[:6]:
            total_run += 1
            f = check(name + "/pipeline", src, full_pipeline, pipe_iters)
            total_fail += f
    print("=" * 50)
    if total_fail:
        print(f"RESULT: {total_fail} FAILURES across {total_run} groups")
        sys.exit(1)
    print(f"RESULT: ALL PASS ({total_run} groups)")


if __name__ == "__main__":
    main()
