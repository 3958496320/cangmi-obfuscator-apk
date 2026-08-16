# -*- coding: utf-8 -*-
"""最小化二分：找出 vm_pro 编译哪种构造会产生 nil _fn 崩溃。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_real_env_repro import LUA_SETUP
from obfuscator_core import obfuscate

CASES = [
    ("A_loadstring链", 'loadstring(game:HttpGet("u"))()'),
    ("B_单纯HttpGet", 'local s = game:HttpGet("u") print(type(s))'),
    ("C_GetService", 'local p = game:GetService("Players") print(type(p))'),
    ("D_A加C", 'loadstring(game:HttpGet("u"))() local p = game:GetService("Players") print(type(p))'),
    ("E_方法调用串", 'local r = game:GetService("RunService") print(type(r))'),
    ("F_局部函数", 'local function f(x) return x end print(f(1))'),
    ("G_全局函数调用", 'local x = tostring(5) print(x)'),
    ("H_table方法", 'local t = {m = function(s, a) return a .. "!" end} print(t:m("hi"))'),
]


def run_case(name, src, use_vm_pro=True):
    try:
        obf = obfuscate(src, seed=42, disable_vm_pro=not use_vm_pro)["code"]
    except Exception as e:
        return f"混淆异常: {str(e)[:80]}"
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(LUA_SETUP)
    G = lua.globals()
    try:
        ok, info, calls = G["_run_code"](obf)
    except Exception as e:
        return f"PY异常: {str(e)[:100]}"
    prints = []
    if calls is not None:
        p = calls["prints"]
        if p is not None:
            i = 1
            while p[i] is not None:
                prints.append(str(p[i]))
                i += 1
    out = f"ok={bool(ok)}"
    if not ok:
        out += f" [{str(info)[:90]}]"
    if prints:
        out += " prints=" + " | ".join(x[:40] for x in prints[:4])
    return out


if __name__ == "__main__":
    print("== vm_pro 开启 ==")
    for name, src in CASES:
        print(f"{name:>16}: {run_case(name, src, True)}")
    print("== vm_pro 关闭(12层) ==")
    for name, src in CASES:
        print(f"{name:>16}: {run_case(name, src, False)}")
