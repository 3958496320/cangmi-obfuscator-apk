#!/usr/bin/env python3
"""Check dec function name consistency in obfuscated output."""
import re
import sys

sys.path.insert(0, '/workspace/src')
from obfuscator_core import obfuscate

# Read sample
with open('/workspace/examples/01_original.lua', 'r', encoding='utf-8') as f:
    src = f.read()

# Try multiple seeds
bugs_found = 0
total = 30
for seed in range(1, total + 1):
    result = obfuscate(src, seed=seed)
    code = result['code']

    # Find all `local function NAME(` patterns at top of body (the dec function)
    dec_funcs = re.findall(r'^local function (\w+)\s*\(', code, re.MULTILINE)
    if not dec_funcs:
        print(f"seed={seed}: NO local function found!")
        bugs_found += 1
        continue
    actual_dec = dec_funcs[0]

    # Find all `NAME("...", num, num, num)` patterns - calls to dec function
    dec_calls = re.findall(r'(\w+)\s*\(\s*"[^"]*"\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)', code)

    unique_calls = set(dec_calls)
    if actual_dec in unique_calls and len(unique_calls) == 1:
        pass
    else:
        print(f"seed={seed}: BUG! dec defined as '{actual_dec}' but calls use {unique_calls}")
        bugs_found += 1

print(f"\n{bugs_found}/{total} seeds produced bugs")
