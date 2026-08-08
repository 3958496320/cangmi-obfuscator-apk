# -*- coding: utf-8 -*-
"""调试 vm_pro.py：打印字节码和生成的 Lua 代码。"""
import sys
import random

sys.path.insert(0, "/workspace/src")

from obfuscator_core import parse_source, NameGenerator
from vm_pro import ProVMCompiler, vm_pro_compile

SAMPLES = {
    "S05": 'local function f(a, b) return a + b end print(f(3, 4))',
    "S07": 'local s = 0 for i = 1, 10 do s = s + i end print(s)',
    "S09": 'local i = 0 while i < 5 do i = i + 1 end print(i)',
    "S10": 'local t = {a = 1, b = 2} print(t.a + t.b)',
}


def debug_one(label, src, seed=1):
    print(f"\n{'='*70}\n{label}: {src}\n{'='*70}")
    rng = random.Random(seed)
    gen = NameGenerator(rng)
    ast = parse_source(src)
    if not ast:
        print("PARSE FAILED")
        return
    comp = ProVMCompiler(rng, gen)
    out = comp.compile_chunk(ast)
    if out is None:
        print("COMPILE RETURNED None")
        return
    # 打印字节码（人类可读）
    print("\n--- BYTECODE (with op names) ---")
    op_names = {v: k for k, v in comp.opcode.items()}
    var_to_real = comp.variant_to_real
    for pc, ins in enumerate(comp.prog[1:], start=1):
        op_code = ins[0]
        real_op = var_to_real.get(op_code, op_code)
        op_name = op_names.get(real_op, f"?{real_op}")
        args = ins[1:]
        print(f"  {pc:3d}  {op_name:10s}  {args}")
    print(f"\n--- CONSTS: {comp.consts}")
    print(f"--- STRS:   {comp.strs}")
    print("\n--- LABELS ---")
    for k, v in sorted(comp._labels.items(), key=lambda x: x[1]):
        print(f"  {v:3d}  {k}")
    print("\n--- GENERATED LUA (first 200 lines) ---")
    for i, line in enumerate(out.split('\n')[:200]):
        print(f"  {i+1:3d}  {line}")


def main():
    for label, src in SAMPLES.items():
        debug_one(label, src, seed=1)


if __name__ == "__main__":
    main()
