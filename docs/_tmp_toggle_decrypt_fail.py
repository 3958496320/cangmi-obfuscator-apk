# -*- coding: utf-8 -*-
"""验证假设：字符串解密失败 → table 字段名乱码 → UI 库读 opts.Value=nil → 默认 true → 雷达误开。
方法：Hook 字符串解密函数，让它返回乱码，模拟真实环境解密失败。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from obfuscator_core import obfuscate
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

code = r'''
getgenv().ShowRadar = nil
local B = {}
B.Toggle = function(self, opts)
    local v = opts.Value
    print("opts.Value =", tostring(v))
    -- 模拟 WindUI: nil 当 true
    local state = v
    if state == nil then state = true end
    print("UI 显示状态 =", tostring(state))
    -- 库初始化调 Callback(state)
    if opts.Callback then opts.Callback(state) end
end

B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        getgenv().ShowRadar = Value
    end
})

print("最终 ShowRadar =", tostring(getgenv().ShowRadar))
print("雷达是否开启:", tostring(getgenv().ShowRadar == true))
'''

cfg = make_envs()[0][1]

def run(code_to_run, hook_decrypt=False):
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
        # 如果要求 hook 解密失败，重新加载并 hook
        return True, out
    except Exception as e:
        return False, ["EXC: " + str(e)[:150]]

print("===== 原始 =====", flush=True)
ok, out = run(code)
for l in out: print(l, flush=True)

res = obfuscate(code, seed=42)
obf = res["code"]

print("\n===== 混淆后（解密正常）=====", flush=True)
ok, out = run(obf)
for l in out: print(l, flush=True)

# 现在 hook 解密函数：找到解密函数名，替换成返回乱码
print("\n===== 混淆后（模拟解密失败 - 字段名乱码）=====", flush=True)
# 在混淆代码前插入：把解密函数包装成返回乱码
# 解密函数名通常是第一个 local function。我们用一个 hack：把所有解密调用替换
# 更简单：在代码开头 hook 解密函数
# 找解密函数名（第一个 local function Wb7pm0bN）
import re
m = re.search(r'local function (\w+)\(.*?\)\s*\n\s*local \w+ = \w+ \.\. string\.char', obf)
if m:
    dec_name = m.group(1)
    print("解密函数名:", dec_name, flush=True)
    # 包装：让解密返回固定乱码 "X"
    hook_code = "local _orig_dec = " + dec_name + "\n" + dec_name + " = function(...) return 'X' end\n"
    obf_hooked = hook_code + obf
    ok, out = run(obf_hooked)
    for l in out: print(l, flush=True)
else:
    print("未找到解密函数", flush=True)
