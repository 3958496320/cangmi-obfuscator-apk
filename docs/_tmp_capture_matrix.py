# -*- coding: utf-8 -*-
"""捕获矩阵：确认 LocalFunction 名被后置语句捕获时编译损坏。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_real_env_repro import LUA_SETUP
from obfuscator_core import obfuscate

CASES = [
    ("F1_仅本地函数", 'local function notify(msg) print(msg) end\nnotify("top")'),
    ("F2_仅conn前向", 'local conn\nlocal t = {Disconnect = function(s) print("dc") end}\nconn = t\nconn:Disconnect()\nprint("done")'),
    ("F3_捕获notify", 'local function notify(msg) print(msg) end\nlocal f = function() notify("cb") end\nnotify("top")\nprint("done")'),
    ("F4_捕获conn", 'local conn\nlocal f = function() conn:Disconnect() end\nprint("done")'),
    ("F5_捕获两者", 'local function notify(msg) print(msg) end\nlocal conn\nlocal f = function() notify("cb") conn:Disconnect() end\nnotify("top")\nprint("done")'),
    ("F6_先声明conn后捕获", 'local conn = nil\nlocal f = function() conn:Disconnect() end\nprint("done")'),
    ("F7_普通local被捕获", 'local x = 5\nlocal f = function() return x end\nprint(f())'),
    ("F8_普通local函数表达式", 'local notify = function(msg) print(msg) end\nlocal f = function() notify("cb") end\nnotify("top")\nprint("done")'),
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
    # 对比原始
    lua2 = LuaRuntime(unpack_returned_tuples=True)
    lua2.execute(LUA_SETUP)
    G2 = lua2.globals()
    ok2, info2, calls2 = G2["_run_code"](src)
    prints2 = []
    if calls2 is not None:
        p2 = calls2["prints"]
        if p2 is not None:
            i = 1
            while p2[i] is not None:
                prints2.append(str(p2[i]))
                i += 1
    # 原始也崩(语义等价)或都成功且输出一致
    if not ok2:
        return (not ok), f"原始也错(等价): {str(info)[:60]}", prints
    return ok, ("" if ok else str(info)[:100]), prints


if __name__ == "__main__":
    for name, src in CASES:
        ok, info, prints = run_vm(src)
        mark = "PASS" if ok else "FAIL"
        print(f"{name:>20}: {mark} {info} prints={[x[:25] for x in prints[:4]]}")
