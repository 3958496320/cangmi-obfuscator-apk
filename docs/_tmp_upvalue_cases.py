# -*- coding: utf-8 -*-
"""upvalue 捕获类构造最小用例矩阵。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_real_env_repro import LUA_SETUP
from obfuscator_core import obfuscate

CASES = [
    ("up1_闭包捕获本地", 'local x = 1 local f = function() return x + 1 end print(f())'),
    ("up2_前向捕获", 'local conn\nconn = game:GetService("RunService").Heartbeat:Connect(function()\n    conn:Disconnect()\nend)\nprint("done")'),
    ("up3_无前向_先赋值", 'local conn = game:GetService("RunService").Heartbeat:Connect(function()\n    print("cb")\nend)\nprint("done")'),
    ("up4_捕获后改写", 'local n = 0 local f = function() n = n + 1 return n end print(f(), f())'),
    ("up5_嵌套两层捕获", 'local a = 1 local function outer() return function() return a + 1 end end print(outer()())'),
    ("up6_捕获+方法调用", 'local t = game:GetService("Players") local function g() return t.LocalPlayer end print(type(g()))'),
    ("up7_顶层conn后续调用", 'local conn\nlocal function cb() conn:Disconnect() end\ncb()\nprint("done")'),
    ("up8_简单前向局部", 'local v\nlocal f = function() return v end\nv = 42\nprint(f())'),
]


def run_vm(src):
    obf = obfuscate(src, seed=42)["code"]
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(LUA_SETUP)
    G = lua.globals()
    try:
        ok, info, calls = G["_run_code"](obf)
    except Exception as e:
        return False, f"PY:{str(e)[:100]}", []
    prints = []
    if calls is not None:
        p = calls["prints"]
        if p is not None:
            i = 1
            while p[i] is not None:
                prints.append(str(p[i]))
                i += 1
    return bool(ok), str(info)[:110], prints


if __name__ == "__main__":
    for name, src in CASES:
        ok, info, prints = run_vm(src)
        mark = "PASS" if ok else "FAIL"
        print(f"{name:>18}: {mark} {'' if ok else info} prints={[x[:30] for x in prints[:3]]}")
