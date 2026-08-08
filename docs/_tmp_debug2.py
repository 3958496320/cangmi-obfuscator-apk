# -*- coding: utf-8 -*-
"""Focused debug for E06, E12, E14, E17."""
import sys
import random
import traceback

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import parse_source, NameGenerator
from vm_pro import ProVMCompiler

TESTS = {
    "E06": ('local t = {10, 20, 30, 40, 50} local max = t[1] for i = 2, #t do if t[i] > max then max = t[i] end end print(max)', "50"),
    "E12": ('local i = 1 while true do if i == 5 then break end i = i + 1 end print(i)', "5"),
    "E14": ('local t = {x = 10} function t:getX() return self.x end print(t:getX())', "10"),
    "E17": ('print(#"hello")', "5"),
}


def debug(label, src, seed=1):
    print(f"\n{'='*70}\n{label}: {src}\n{'='*70}")
    rng = random.Random(seed)
    gen = NameGenerator(rng)
    ast = parse_source(src)
    if not ast:
        print("PARSE FAILED")
        return
    comp = ProVMCompiler(rng, gen)
    try:
        out = comp.compile_chunk(ast)
    except Exception as e:
        print(f"\nCOMPILE EXCEPTION: {e}")
        traceback.print_exc()
        return
    if out is None:
        print("COMPILE RETURNED None")
        return

    # 打印字节码
    print("\n--- BYTECODE ---")
    op_names = {v: k for k, v in comp.opcode.items()}
    var_to_real = comp.variant_to_real
    for pc, ins in enumerate(comp.prog[1:], start=1):
        op_code = ins[0]
        real_op = var_to_real.get(op_code, op_code)
        op_name = op_names.get(real_op, f"?{real_op}")
        args = ins[1:]
        print(f"  {pc:3d}  {op_name:10s}  {args}")

    # 执行
    try:
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
        lua.execute(out)
        out_str = "\n".join(outputs)
        print(f"\n--- OUTPUT: {out_str!r}")
    except Exception as e:
        print(f"\n--- RUNTIME ERROR: {e}")


def main():
    for label, (src, _) in TESTS.items():
        debug(label, src, seed=1)


if __name__ == "__main__":
    main()
