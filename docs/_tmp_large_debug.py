# -*- coding: utf-8 -*-
"""Isolate which large-script features break vm_pro."""
import sys, random
sys.path.insert(0, "/workspace/src")
from lupa import LuaRuntime
from obfuscator_core import obfuscate

TESTS = [
    # 1. Many local functions in sequence
    ("many_funcs", '''
local function f1(a, b) return a + b end
local function f2(a, b) return a - b end
local function f3(a, b) return a * b end
print(f1(1, 2), f2(5, 3), f3(4, 6))
''', "3\t2\t24"),

    # 2. Local function called in loop
    ("func_in_loop", '''
local function f(a, b) return a + b end
local total = 0
for i = 1, 10 do total = total + f(i, i * 2) end
print(total)
''', "165"),

    # 3. _G dynamic access
    ("g_dynamic", '''
x = 42
local v = _G["x"]
print(v)
''', "42"),

    # 4. _G with tostring
    ("g_tostring", '''
obj_0 = {value = 10}
local v = _G["obj_" .. tostring(0)]
print(v.value)
''', "10"),

    # 5. Method call on global table
    ("method_global", '''
obj_0 = {value = 10}
function obj_0:getVal() return self.value end
local v = _G["obj_" .. tostring(0)]
print(v:getVal())
''', "10"),

    # 6. string.sub
    ("string_sub", '''
local s = "hello"
local c = string.sub(s, 1, 1)
print(c)
''', "h"),

    # 7. string.upper
    ("string_upper", '''
local s = "hello"
print(string.upper(s))
''', "HELLO"),

    # 8. String comparison >= <=
    ("str_compare", '''
local c = "a"
if c >= "a" and c <= "z" then print("LOWER") end
''', "LOWER"),

    # 9. Closure factory
    ("closure_factory", '''
local function makeAdder(n) return function(x) return x + n end end
local add5 = makeAdder(5)
print(add5(100))
''', "105"),

    # 10. Bubble sort
    ("bubble_sort", '''
local function bubbleSort(arr)
    local n = #arr
    for i = 1, n - 1 do
        for j = 1, n - i do
            if arr[j] > arr[j + 1] then
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
            end
        end
    end
    return arr
end
local sorted = bubbleSort({5, 3, 8, 1, 9, 2, 7, 4, 6})
print(sorted[1], sorted[2], sorted[3])
''', "1\t2\t3"),

    # 11. Multiple return values from function in loop
    ("multi_ret_loop", '''
local function f(a, b) return a + b, a - b end
local s1, s2 = 0, 0
for i = 1, 5 do
    local x, y = f(i, i * 2)
    s1 = s1 + x
    s2 = s2 + y
end
print(s1, s2)
''', "45\t-15"),

    # 12. tostring in concat
    ("tostring_concat", '''
local s = "obj_" .. tostring(0)
print(s)
''', "obj_0"),

    # 13. Function declaration as global (not local)
    ("global_func", '''
function foo(a, b) return a + b end
print(foo(3, 4))
''', "7"),

    # 14. Table with method + global access
    ("table_method_global", '''
obj = {value = 42}
function obj:getValue() return self.value end
function obj:setName(n) self.name = n end
function obj:double() return self.value * 2 end
print(obj:getValue(), obj:double())
obj:setName("test")
print(obj.name)
''', "42\t84\ntest"),
]

def run_one(name, src, expected, seed=42):
    try:
        result = obfuscate(src, seed=seed, disable_vm=True, disable_vm_pro=False)
        code = result["code"]
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
        lua.execute(code)
        out_str = "\n".join(outputs)
        if expected in out_str:
            return True, out_str[:80]
        return False, f"exp='{expected}' got='{out_str[:80]}'"
    except Exception as e:
        return False, str(e).replace("\n", " ")[:200]

def main():
    total = passed = 0
    for name, src, expected in TESTS:
        for seed in [1, 42, 99]:
            total += 1
            ok, info = run_one(name, src, expected, seed)
            label = f"{name}_s{seed}"
            if ok:
                passed += 1
                print(f"[{label:25s}] PASS  {info}", flush=True)
            else:
                print(f"[{label:25s}] FAIL  {info}", flush=True)
    print("=" * 60)
    print(f"总计: {total}  通过: {passed}  失败: {total-passed}")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
