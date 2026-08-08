# -*- coding: utf-8 -*-
"""诊断：看 vm_pro 生成的 Lua 代码。"""
import sys
sys.path.insert(0, "/workspace/src")
import random
from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile

src = 'print("HELLO_VM")'
rng = random.Random(1)
gen = NameGenerator(rng)
ast = parse_source(src)
code = vm_pro_compile(ast, rng, gen)
print(code)
print("=== END ===")
