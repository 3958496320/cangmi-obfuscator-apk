# -*- coding: utf-8 -*-
"""决定性测试：模拟真实 UI 库（Toggle 创建不调 Callback），检查 ShowRadar 是否被意外设成 true。
另测多 seed，看 Value=false 是否始终正确。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from obfuscator_core import obfuscate
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

# 模拟真实 WindUI 行为：Toggle 创建时只存状态，不调 Callback
code = r'''
getgenv().ShowRadar = nil
local B = {}
B._state = nil
B._cb = nil
B.Toggle = function(self, opts)
    self._state = opts.Value
    self._cb = opts.Callback
end

B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        getgenv().ShowRadar = Value
    end
})

print("启动后 ShowRadar =", tostring(getgenv().ShowRadar))
print("opts.Value 存入 _state =", tostring(B._state))
'''

cfg = make_envs()[0][1]
def run(code_to_run, label):
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
    try:
        lua.execute(code_to_run)
        return True, out
    except Exception as e:
        return False, ["EXC: " + str(e)[:150]]

print("===== 原始 =====", flush=True)
ok, out = run(code, "原始")
for l in out: print(l, flush=True)

print("\n===== 多 seed 测试（看 Value=false 是否始终正确）=====", flush=True)
for seed in [1, 42, 100, 999, 12345]:
    res = obfuscate(code, seed=seed)
    ok, out = run(res["code"], "seed={}".format(seed))
    status = "PASS" if ok and any("ShowRadar =\tnil" in l for l in out) and any("= false" in l or "=false" in l.lower() for l in out) else "CHECK"
    if not ok: status = "FAIL"
    line1 = out[0] if out else "(无输出)"
    line2 = out[1] if len(out)>1 else ""
    print("seed={:<6} {} | {} | {}".format(seed, status, line1, line2), flush=True)
