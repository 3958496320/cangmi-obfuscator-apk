# -*- coding: utf-8 -*-
"""检查混淆后的 Toggle 代码有无可疑赋值。"""
import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import obfuscate

code = r'''
B:Toggle({
    Title = "雷达系统",
    Value = false,
    Callback = function(Value)
        getgenv().ShowRadar = Value
    end
})

local Positions = {
    ["Alpha"] = CFrame.new(-1197, 65, -4790),
    ["Bravo"] = CFrame.new(-220, 65, -4919)
}
'''

res = obfuscate(code, seed=42)
obf = res["code"]
print("混淆后行数:", obf.count("\n")+1, flush=True)

# 搜索可疑模式
import re
print("\n===== 搜索 ShowRadar 相关 =====", flush=True)
for i, line in enumerate(obf.split("\n"), 1):
    if "ShowRadar" in line or "Radar" in line:
        print("{:4}| {}".format(i, line[:120]), flush=True)

print("\n===== 搜索 getgenv 赋值 =====", flush=True)
for i, line in enumerate(obf.split("\n"), 1):
    if "getgenv" in line and ("=" in line or "ShowRadar" in line):
        print("{:4}| {}".format(i, line[:120]), flush=True)

print("\n===== 搜索 = true / =True 可疑赋值 =====", flush=True)
cnt = 0
for i, line in enumerate(obf.split("\n"), 1):
    # 跳过 if/elseif 条件里的 true，只看赋值
    if re.search(r'=\s*true\b', line, re.IGNORECASE) and "if" not in line.lower() and "elseif" not in line.lower() and "and" not in line.lower() and "or" not in line.lower():
        print("{:4}| {}".format(i, line[:120]), flush=True)
        cnt += 1
        if cnt > 20: break

# 写出完整混淆代码供查看
open("/tmp/_toggle_obf.lua", "w", encoding="utf-8").write(obf)
print("\n完整混淆代码已写到 /tmp/_toggle_obf.lua", flush=True)
