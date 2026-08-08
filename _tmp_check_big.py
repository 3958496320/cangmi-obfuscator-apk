#!/usr/bin/env python3
"""Check dec function name consistency on large sample."""
import re
import sys

sys.path.insert(0, '/workspace/src')
from obfuscator_core import obfuscate

# Read sample
with open('/workspace/tests/big10k.lua', 'r', encoding='utf-8') as f:
    src = f.read()

print(f"Input size: {len(src)} bytes")

# Try multiple seeds
bugs_found = 0
total = 5
for seed in range(1, total + 1):
    print(f"\n=== seed={seed} ===")
    result = obfuscate(src, seed=seed)
    code = result['code']
    print(f"Output size: {len(code)} bytes, profile={result['profile'].get('name')}")

    # Find all `local function NAME(` patterns at top of body (the dec function)
    dec_funcs = re.findall(r'^local function (\w+)\s*\(', code, re.MULTILINE)
    if not dec_funcs:
        print(f"  NO local function found!")
        bugs_found += 1
        continue
    actual_dec = dec_funcs[0]
    print(f"  First local function (dec): {actual_dec}")

    # Find all `NAME("...", num, num, num)` patterns - calls to dec function
    dec_calls = re.findall(r'(\w+)\s*\(\s*"[^"]*"\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)', code)

    unique_calls = set(dec_calls)
    print(f"  Unique 4-arg call names: {unique_calls}")
    if actual_dec in unique_calls and len(unique_calls) == 1:
        print(f"  OK: all dec calls use the defined name")
    else:
        print(f"  BUG! dec defined as '{actual_dec}' but calls use {unique_calls}")
        bugs_found += 1

print(f"\n{bugs_found}/{total} seeds produced bugs")
