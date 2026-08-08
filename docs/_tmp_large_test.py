# -*- coding: utf-8 -*-
"""Large script test: generate ~100KB Lua source, obfuscate, verify runs."""
import sys, time
sys.path.insert(0, "/workspace/src")
from lupa import LuaRuntime
from obfuscator_core import obfuscate

def gen_large_script():
    """Generate a large Lua script with diverse constructs."""
    parts = []
    parts.append('-- Large test script')
    # 50 local functions
    for i in range(50):
        parts.append(f'''
local function func_{i}(a, b)
    local x = a + b
    local y = a * b
    if x > y then
        return x - y
    elseif x == y then
        return 0
    else
        return y - x
    end
end''')
    # 20 GLOBAL tables with methods (accessible via _G)
    for i in range(20):
        parts.append(f'''
obj_{i} = {{value = {i}, name = "obj_{i}"}}
function obj_{i}:getValue() return self.value end
function obj_{i}:setName(n) self.name = n end
function obj_{i}:double() return self.value * 2 end''')
    # Nested closures
    parts.append('''
local function makeAdder(n)
    return function(x) return x + n end
end
local add5 = makeAdder(5)
local add10 = makeAdder(10)''')
    # String processing
    parts.append('''
local function processString(s)
    local result = ""
    for i = 1, #s do
        local c = string.sub(s, i, i)
        if c >= "a" and c <= "z" then
            result = result .. string.upper(c)
        else
            result = result .. c
        end
    end
    return result
end''')
    # Numeric computations
    parts.append('''
local function computeSum(n)
    local sum = 0
    for i = 1, n do sum = sum + i end
    return sum
end

local function fibonacci(n)
    if n < 2 then return n end
    local a, b = 0, 1
    for i = 2, n do a, b = b, a + b end
    return b
end''')
    # Array operations
    parts.append('''
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
end''')
    # Main execution
    parts.append('''
-- Run computations
local total = 0
for i = 1, 50 do
    total = total + func_0(i, i * 2)
end

local obj_sum = 0
for i = 0, 19 do
    local v = _G["obj_" .. tostring(i)]
    if v then obj_sum = obj_sum + v:getValue() end
end

local s1 = add5(100)
local s2 = add10(200)
local str_result = processString("hello world 123")
local sum_result = computeSum(100)
local fib_result = fibonacci(20)
local sorted = bubbleSort({5, 3, 8, 1, 9, 2, 7, 4, 6})

print("TOTAL=" .. total)
print("OBJ_SUM=" .. obj_sum)
print("ADD5=" .. s1)
print("ADD10=" .. s2)
print("STR=" .. str_result)
print("SUM=" .. sum_result)
print("FIB=" .. fib_result)
print("SORTED=" .. sorted[1] .. "," .. sorted[2] .. "," .. sorted[3])
''')
    return "\n".join(parts)


def main():
    src = gen_large_script()
    src_size = len(src)
    print(f"Source size: {src_size} bytes ({src_size/1024:.1f} KB)", flush=True)

    seeds = [1, 42, 999]
    for seed in seeds:
        t0 = time.time()
        try:
            result = obfuscate(src, seed=seed, disable_vm=True, disable_vm_pro=False)
            code = result["code"]
            stats = result["stats"]
            vm_status = stats.get("vm_pro", "?")
            obf_time = time.time() - t0
            code_size = len(code)

            outputs = []
            lua = LuaRuntime(unpack_returned_tuples=True)
            g = lua.globals()
            g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
            t1 = time.time()
            lua.execute(code)
            exec_time = time.time() - t1

            out_str = "\n".join(outputs)
            ok = ("TOTAL=" in out_str and "OBJ_SUM=" in out_str and
                  "ADD5=105" in out_str and "ADD10=210" in out_str and
                  "STR=HELLO WORLD 123" in out_str and "SUM=5050" in out_str and
                  "FIB=6765" in out_str and "SORTED=1,2,3" in out_str)

            print(f"  seed={seed}: vm_pro={vm_status}  "
                  f"src={src_size}B obf={code_size}B ({code_size/1024:.1f}KB)  "
                  f"obf_time={obf_time:.2f}s exec_time={exec_time:.2f}s  "
                  f"{'PASS' if ok else 'FAIL'}", flush=True)
            if not ok:
                print(f"    OUTPUT:\n{out_str[:500]}", flush=True)
        except Exception as e:
            print(f"  seed={seed}: EXCEPTION {str(e)[:200]}", flush=True)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
