# -*- coding: utf-8 -*-
"""定位产物中修改 readonly table 的具体代码行。"""
import sys, os
sys.path.insert(0, "/workspace/docs")
from obfuscator_all import obfuscate_code

SRC = open("/workspace/docs/radar_input.lua").read()
obf = obfuscate_code(SRC, ninja_mode=True)
lines = obf.split("\n")
print(f"产物总行数: {len(lines)}")
# 错误行 1111（当前版）和 1038（5f8c350）
for target in [1111, 1038]:
    if target <= len(lines):
        print(f"\n=== 第 {target} 行附近 ===")
        for i in range(max(0, target-6), min(len(lines), target+3)):
            mark = " >>>" if i == target-1 else "    "
            print(f"{mark}{i+1}: {lines[i][:160]}")

# 搜索给标准库表赋值的模式： os./math./string./table./coroutine. = 
import re
print("\n=== 搜索给标准库成员赋值的语句 ===")
pat = re.compile(r'\b(os|math|string|table|coroutine|debug|bit32)\s*\.\s*\w+\s*=')
for i, ln in enumerate(lines, 1):
    if pat.search(ln):
        print(f"  L{i}: {ln[:160]}")
