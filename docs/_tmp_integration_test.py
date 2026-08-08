# -*- coding: utf-8 -*-
"""Integration test: obfuscate via obfuscate() and run the result."""
import sys
sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import obfuscate

SAMPLES = [
    ('print("HELLO")', "HELLO"),
    ('local x = 10 local y = 20 print(x + y)', "30"),
    ('local function f(a, b) return a + b end print(f(3, 4))', "7"),
    ('local s = 0 for i = 1, 10 do s = s + i end print(s)', "55"),
    ('local t = {10, 20, 30} local sum = 0 for _, v in ipairs(t) do sum = sum + v end print(sum)', "60"),
    ('local function counter() local c = 0 return function() c = c + 1 return c end end local f = counter() print(f()) print(f())', "1\n2"),
]

def run_one(src, expected, seed=42):
    try:
        result = obfuscate(src, seed=seed, disable_vm=False)
        code = result["code"]
        stats = result["stats"]
        vm_pro_status = stats.get("vm_pro", "?")
        
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
        lua.execute(code)
        out_str = "\n".join(outputs)
        
        if expected in out_str:
            return True, f"vm_pro={vm_pro_status} out={out_str[:60]}", len(code)
        return False, f"vm_pro={vm_pro_status} expected='{expected}' got='{out_str[:60]}'", len(code)
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        return False, msg, 0

def main():
    total = passed = 0
    for idx, (src, expected) in enumerate(SAMPLES):
        total += 1
        ok, info, size = run_one(src, expected)
        label = f"I{idx+1:02d}"
        if ok:
            passed += 1
            print(f"[{label}] PASS  ({size}B)  {info}", flush=True)
        else:
            print(f"[{label}] FAIL  {info}", flush=True)
    print("=" * 60)
    print(f"总计: {total}  通过: {passed}  失败: {total-passed}")

if __name__ == "__main__":
    main()
