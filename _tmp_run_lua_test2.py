#!/usr/bin/env python3
"""Run obfuscated Lua code with full Ninja Injector simulation."""
import sys
import os
import traceback

sys.path.insert(0, '/workspace/docs')
sys.path.insert(0, '/workspace/src')
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs


def run_obf_code(code_path, env_idx=0, verbose=True):
    with open(code_path, 'r', encoding='utf-8') as f:
        code = f.read()

    cfg = make_envs()[env_idx][1]
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    lua.execute(build_shim_lua(cfg))
    env = lua.eval("_G._build_ninja_shim()")
    for k in ["bit32","bit","task","tick","getgenv","getrenv","identifyexecutor",
              "setclipboard","request","writefile","readfile","delfile","isfile",
              "makefolder","Drawing","game","workspace","warn","hookfunction",
              "hookmetamethod","typeof","Instance","Vector3","CFrame","Color3",
              "UDim2","Enum","HttpService","RunService","connect","spawn","delay",
              "wait","loadstring","debug","syn","protect_gui","http_get"]:
        if env[k] is not None or k in ["bit32","bit","task","debug","syn","protect_gui"]:
            g[k] = env[k]
    if verbose:
        import builtins
        g["print"] = lambda *a: builtins.print(*a, flush=True)
    else:
        g["print"] = lambda *a: None
    g["__OMNISHIELD_LOADED"] = None

    try:
        lua.execute(code)
        print("[ok] obfuscated code finished")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python _tmp_run_lua_test2.py <obf.lua> [env_idx=0]")
        sys.exit(1)
    env_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ok = run_obf_code(sys.argv[1], env_idx=env_idx, verbose=True)
    sys.exit(0 if ok else 1)
