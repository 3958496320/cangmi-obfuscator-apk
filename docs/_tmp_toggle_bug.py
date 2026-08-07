# -*- coding: utf-8 -*-
"""复现雷达系统误开 bug：混淆后 Toggle Value=false 变成 true。"""
import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import obfuscate

# 模拟 UI 库 + Toggle 调用
code = r'''
local _toggle_state = nil
local _callback_called = false
local _callback_value = nil

-- 模拟 B:Toggle 的实现
local B = {}
B.Toggle = function(self, opts)
    _toggle_state = opts.Value
    print("Toggle 初始值:", tostring(opts.Value), "Title:", tostring(opts.Title))
    if opts.Callback then
        _callback_called = true
        _callback_value = opts.Value
        opts.Callback(opts.Value)
    end
    return opts.Value
end

-- 用户代码
B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        _G.ShowRadar = Value
        print("Callback 被调用, Value=", tostring(Value))
    end
})

print("最终 _toggle_state=", tostring(_toggle_state))
print("ShowRadar=", tostring(_G.ShowRadar))
print("Callback是否被调用=", tostring(_callback_called))
'''

print("===== 原始代码输出 =====", flush=True)
exec_ns = {}
# 用 lua 跑原始
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs
cfg = make_envs()[0][1]
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
print("--- 原始运行 ---", flush=True)
try:
    lua.execute(code)
except Exception as e:
    print("原始错误:", e, flush=True)

# 混淆
print("\n===== 混淆中 =====", flush=True)
res = obfuscate(code, seed=42)
obf = res["code"]

# 跑混淆后
print("\n===== 混淆后输出 =====", flush=True)
lua2 = LuaRuntime(unpack_returned_tuples=True)
g2 = lua2.globals()
lua2.execute(build_shim_lua(cfg))
env2 = lua2.eval("_G._build_ninja_shim()")
for k in ["bit32","bit","task","tick","getgenv","getrenv","identifyexecutor",
          "setclipboard","request","writefile","readfile","delfile","isfile",
          "makefolder","Drawing","game","workspace","warn","hookfunction",
          "hookmetamethod","typeof","Instance","Vector3","CFrame","Color3",
          "UDim2","Enum","HttpService","RunService","connect","spawn","delay",
          "wait","loadstring","debug","syn","protect_gui","http_get"]:
    if env2[k] is not None or k in ["bit32","bit","task","debug","syn","protect_gui"]:
        g2[k] = env2[k]
g2["print"] = lambda *a: print("\t".join(str(x) for x in a), flush=True)
g2["__OMNISHIELD_LOADED"] = None
print("--- 混淆后运行 ---", flush=True)
try:
    lua2.execute(obf)
except Exception as e:
    print("混淆后错误:", str(e)[:200], flush=True)
