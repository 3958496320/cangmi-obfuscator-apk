# -*- coding: utf-8 -*-
"""Dump P2 generated Lua code for inspection"""
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

with open("/workspace/docs/_tmp_p2_output.lua", "w") as f:
    f.write(code)
print(f"Written {len(code)} bytes to _tmp_p2_output.lua", flush=True)
print(f"Total lines: {len(code.split(chr(10)))}", flush=True)
