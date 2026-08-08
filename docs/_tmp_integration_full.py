# -*- coding: utf-8 -*-
"""Full integration test: obfuscate() with vm_pro + multi-seed stress."""
import sys, random
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
    # 多返回值
    ('local function f(a, b) return a + b, a - b end local x, y = f(10, 3) print(x, y)', "13\t7"),
    # 递归
    ('local function fib(n) if n < 2 then return n end return fib(n-1) + fib(n-2) end print(fib(10))', "55"),
    # 闭包递增
    ('local function counter() local c = 0 return function() c = c + 1 return c end end local f = counter() print(f()) print(f()) print(f())', "1\n2\n3"),
    # 字符串拼接
    ('local s = "" for i = 1, 5 do s = s .. tostring(i) end print(s)', "12345"),
    # 嵌套表
    ('local t = {a = {b = {c = 42}}} print(t.a.b.c)', "42"),
    # 数组找最大值
    ('local t = {10, 20, 30, 40, 50} local max = t[1] for i = 2, #t do if t[i] > max then max = t[i] end end print(max)', "50"),
    # while + break
    ('local i = 1 while true do if i == 5 then break end i = i + 1 end print(i)', "5"),
    # repeat-until
    ('local i = 0 repeat i = i + 1 until i >= 5 print(i)', "5"),
    # 条件嵌套
    ('local x = 10 local y = 20 if x > y then print("X") elseif x == y then print("E") else print("Y") end', "Y"),
    # 全局变量
    ('G_VAR = 42 local function getG() return G_VAR end print(getG())', "42"),
    # 字符串比较
    ('local s = "hello" if s == "hello" then print("MATCH") end', "MATCH"),
    # 长度操作符
    ('local t = {1, 2, 3, 4, 5} print(#t)', "5"),
    # 嵌套循环
    ('local s = 0 for i = 1, 3 do for j = 1, 3 do s = s + 1 end end print(s)', "9"),
    # 方法调用
    ('local t = {x = 10} function t:getX() return self.x end print(t:getX())', "10"),
    # 多重赋值
    ('local a, b, c = 1, 2, 3 print(a + b + c)', "6"),
    # 变量交换
    ('local a, b = 1, 2 a, b = b, a print(a, b)', "2\t1"),
    # 字符串长度
    ('print(#"hello")', "5"),
    # 取模
    ('print(17 % 5)', "2"),
    # 幂运算
    ('print(2 ^ 10)', "1024"),
    # 冒泡排序
    ('local arr = {5, 3, 8, 1, 9, 2} for i = 1, #arr-1 do for j = 1, #arr-i do if arr[j] > arr[j+1] then arr[j], arr[j+1] = arr[j+1], arr[j] end end end print(arr[1], arr[2], arr[3], arr[4], arr[5], arr[6])', "1\t2\t3\t5\t8\t9"),
    # and/or 短路
    ('local x = nil local y = x or "default" print(y)', "default"),
    ('local x = 10 local y = x and 20 print(y)', "20"),
    # table.insert/remove
    ('local t = {} table.insert(t, 10) table.insert(t, 20) print(t[1], t[2])', "10\t20"),
    # string.format
    ('print(string.format("%d-%d", 1, 2))', "1-2"),
]

def run_one(src, expected, seed):
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
            return True, f"vm_pro={vm_pro_status} out={out_str[:50]}", len(code)
        return False, f"vm_pro={vm_pro_status} exp='{expected}' got='{out_str[:50]}'", len(code)
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        return False, msg, 0

def main():
    total = passed = 0
    failed = []
    for idx, (src, expected) in enumerate(SAMPLES):
        for seed in [1, 7, 42, 99, 2024]:
            total += 1
            ok, info, size = run_one(src, expected, seed)
            label = f"I{idx+1:02d}_s{seed}"
            if ok:
                passed += 1
                print(f"[{label}] PASS ({size}B) {info}", flush=True)
            else:
                failed.append(f"{label}: {info}")
                print(f"[{label}] FAIL {info}", flush=True)
    print("=" * 60)
    print(f"总计: {total}  通过: {passed}  失败: {total-passed}")
    if failed:
        print("失败列表:", flush=True)
        for f in failed:
            print(f"  - {f}", flush=True)
    print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====", flush=True)
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
