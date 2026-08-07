# -*- coding: utf-8 -*-
"""验证 docs/obfuscator_all.py（网站 bundle）修复后能正常工作。"""
import sys, time
sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

# 用 bundle 而非 src
print("加载 bundle (docs/obfuscator_all.py)...", flush=True)
import importlib.util
spec = importlib.util.spec_from_file_location("obfuscator_all", "/workspace/docs/obfuscator_all.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
obfuscate = mod.obfuscate
print("bundle 加载 OK", flush=True)

# 完整环境
cfg = make_envs()[0][1]

cases = [
    ("算术", 'local a=10 local b=3 print(a+b, a-b, a*b, a//b, a%b)', "13\t7\t30\t3\t1"),
    ("递归", 'local function f(n) if n<=1 then return 1 end return n*f(n-1) end print(f(5))', "120"),
    ("循环", 'local s=0 for i=1,100 do s=s+i end print(s)', "5050"),
]

def run_capture(code, cfg):
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
    out = []
    g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
    g["__OMNISHIELD_LOADED"] = None
    lua.execute(code)
    return "\n".join(out)

total = passed = 0
for name, code, expected in cases:
    total += 1
    sys.stdout.write("{:<10} ... ".format(name))
    sys.stdout.flush()
    try:
        # 原始
        out_o = run_capture(code, cfg)
        # 混淆
        res = obfuscate(code, seed=42)
        out_b = run_capture(res["code"], cfg)
        if out_o == out_b and out_o == expected:
            sys.stdout.write("PASS\n")
            passed += 1
        else:
            sys.stdout.write("FAIL (原={!r} 混淆={!r} 期望={!r})\n".format(out_o[:40], out_b[:40], expected[:40]))
    except Exception as e:
        sys.stdout.write("FAIL (exc {})\n".format(str(e)[:60]))

print("-" * 40, flush=True)
print("bundle 测试: {}/{} 通过".format(passed, total), flush=True)
print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====", flush=True)
sys.exit(0 if passed == total else 1)
