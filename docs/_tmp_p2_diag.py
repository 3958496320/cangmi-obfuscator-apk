# -*- coding: utf-8 -*-
"""诊断 P2 生成的 Lua 代码语法错误"""
import sys
import random
sys.path.insert(0, "/workspace/src")

from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile

src = 'print("HELLO_VM")'
rng = random.Random(0)
gen = NameGenerator(rng)
ast = parse_source(src)
code = vm_pro_compile(ast, rng, gen)

# 找到错误行附近
lines = code.split('\n')
for i, line in enumerate(lines):
    if '=' in line and ']' in line:
        # 找含模式 R[RK[...]] 的行
        if 'RK' in line:
            print(f"Line {i+1}: {line}", flush=True)

# 也打印出有问题的行
print("\n--- Lines with potential issues ---", flush=True)
for i, line in enumerate(lines):
    # 查找不匹配的括号
    if '_rk[' in line:
        print(f"  L{i+1}: {line.strip()}", flush=True)
