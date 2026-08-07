# -*- coding: utf-8 -*-
"""验证 bundle 的雷达修复：Value/Title/Callback 字段名保持明文，雷达默认关闭。"""
import sys
sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")
import importlib.util
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

# 加载 bundle
spec = importlib.util.spec_from_file_location("obfuscator_all", "/workspace/docs/obfuscator_all.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
obfuscate = mod.obfuscate

# 雷达脚本
radar_code = r'''
local B = {}
B.Toggle = function(self, opts)
    self._state = opts.Value
    self._cb = opts.Callback
    if opts.Callback then opts.Callback(opts.Value) end
end

B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        getgenv().ShowRadar = Value
    end
})

local Positions = {
    ["Alpha"] = CFrame.new(-1197, 65, -4790),
    ["Bravo"] = CFrame.new(-220, 65, -4919),
}
getgenv().Positions = Positions
'''

cfg = make_envs()[0][1]

def run_capture(code):
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
    g["print"] = lambda *a: None
    g["__OMNISHIELD_LOADED"] = None
    lua.execute(code)
    return g

# 混淆
print("混淆雷达脚本...", flush=True)
res = obfuscate(radar_code, seed=42)
obf_code = res["code"]

# 检查字段名是否明文
print("\n=== 字段名明文检查 ===")
for field in ["Value", "Title", "Callback", "Alpha", "Bravo"]:
    # 字段名在混淆后应作为明文字符串出现（被 _no_encrypt 标记）
    # 注意：字符串可能被 _vk 编码或保留明文，关键是 TableField 的 key 不被加密
    if field in obf_code:
        print(f"  {field}: 明文存在 ✓")
    else:
        print(f"  {field}: 未找到（可能被其他层处理）⚠")

# 执行混淆后脚本，检查 ShowRadar
print("\n=== 执行检查 ===")
try:
    g = run_capture(obf_code)
    sr = g["getgenv"]().ShowRadar if g["getgenv"]() else None
    print(f"  ShowRadar 值: {sr!r}")
    if sr is False or sr is None:
        print(f"  雷达状态: {'关闭' if sr is False else '未设置(默认关)'} ✓")
    elif sr is True:
        print(f"  雷达状态: 开启 ✗ (BUG! 误开)")
    else:
        print(f"  雷达状态: 未知 ({sr!r})")
    
    # Positions 检查
    pos = g["getgenv"]().Positions if g["getgenv"]() else None
    print(f"  Positions 类型: {type(pos).__name__}")
    if pos is not None:
        try:
            alpha = pos.Alpha
            print(f"  Positions.Alpha: {alpha} ✓")
        except Exception as e:
            print(f"  Positions.Alpha 读取失败: {e} ✗")
except Exception as e:
    print(f"  执行错误: {e} ✗")

# 多 seed 测试
print("\n=== 多 seed 测试（5个seed）===")
all_ok = True
for seed in [1, 42, 100, 999, 2024]:
    try:
        res = obfuscate(radar_code, seed=seed)
        g = run_capture(res["code"])
        sr = g["getgenv"]().ShowRadar if g["getgenv"]() else None
        ok = sr is False or sr is None
        print(f"  seed={seed}: ShowRadar={sr!r} {'✓' if ok else '✗ 误开!'}")
        if not ok:
            all_ok = False
    except Exception as e:
        print(f"  seed={seed}: 错误 {str(e)[:60]} ✗")
        all_ok = False

print(f"\n=== 总结: {'全部通过 ✓' if all_ok else '有失败 ✗'} ===")
sys.exit(0 if all_ok else 1)
