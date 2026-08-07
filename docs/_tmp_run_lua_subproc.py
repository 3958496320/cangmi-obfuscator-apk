# -*- coding: utf-8 -*-
"""子进程 helper：在仿真环境运行指定 Lua 文件，输出 PASS/FAIL/原因。"""
import sys
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

lua_file = sys.argv[1]
env_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
verbose = len(sys.argv) > 3 and sys.argv[3] == "verbose"

cfg = make_envs()[env_idx][1]
try:
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
    code = open(lua_file, encoding="utf-8").read()
    lua.execute(code)
    print("PASS", flush=True)
except Exception as e:
    print("FAIL: " + str(e).replace("\n", " ")[:200], flush=True)
