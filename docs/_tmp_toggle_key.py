# -*- coding: utf-8 -*-
"""定位 bug：混淆后 table 字段名是否被加密成乱码（导致 UI 库读不到 Value）。
方法：B:Toggle 里遍历 opts 的所有 key-value，打印实际 key。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from obfuscator_core import obfuscate
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

code = r'''
local B = {}
B.Toggle = function(self, opts)
    print("=== opts 实际内容 ===")
    for k, v in pairs(opts) do
        print("  key=" .. tostring(k) .. "  value=" .. tostring(v))
    end
    print("=== opts.Value 直接读取 ===")
    print("  opts.Value = " .. tostring(opts.Value))
    print("  opts[\"Value\"] = " .. tostring(opts["Value"]))
    print("  opts.Title = " .. tostring(opts.Title))
    print("  opts.Callback = " .. tostring(opts.Callback))
end

B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        getgenv().ShowRadar = Value
    end
})
'''

cfg = make_envs()[0][1]
def run(code_to_run, label):
    print("\n===== {} =====".format(label), flush=True)
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
    g["print"] = lambda *a: print("\t".join(str(x) for x in a), flush=True)
    g["__OMNISHIELD_LOADED"] = None
    try:
        lua.execute(code_to_run)
    except Exception as e:
        print("错误:", str(e)[:200], flush=True)

run(code, "原始")
res = obfuscate(code, seed=42)
run(res["code"], "混淆后")
