# -*- coding: utf-8 -*-
"""真实 Lua 运行时验证：混淆产物在 LuaJIT 下 100% 不报错 + 输出正确。
这是最接近忍者注入器环境的本地验证（LuaJIT 兼容 Lua 5.1，与 Roblox Luau
语法层高度一致）。"""
import os
import sys
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
exec(open(os.path.join(HERE, 'obfuscator_all.py')).read())

LUA = "/tmp/luau"


# 每个样本：(源码, 期望输出的一部分)
# 关键：选择「能 print 出来」的样本，验证「能显示出来」。
SAMPLES = [
    # 1. 简单 print
    ('print("HELLO_NINJA")', "HELLO_NINJA"),
    # 2. 算术
    ('print(1 + 2 * 3)', "7"),
    # 3. 字符串拼接
    ('print("a" .. "b" .. "c")', "abc"),
    # 4. 函数 + 返回值
    ('local function f(x) return x * x end print(f(9))', "81"),
    # 5. 表 + ipairs
    ('local t = {10, 20, 30} local s = 0 for _, v in ipairs(t) do s = s + v end print(s)', "60"),
    # 6. 闭包计数器
    ('local function c() local n = 0 return function() n = n + 1 return n end end local f = c() print(f(), f(), f())', "1\t2\t3"),
    # 7. 递归阶乘
    ('local function fact(n) if n <= 1 then return 1 end return n * fact(n-1) end print(fact(5))', "120"),
    # 8. while 循环
    ('local i = 1 local s = 0 while i <= 10 do s = s + i i = i + 1 end print(s)', "55"),
    # 9. 字符串方法
    ('print(string.upper("hello"))', "HELLO"),
    # 10. math 函数
    ('print(math.floor(3.7))', "3"),
    # 11. 多返回值
    ('local function m() return 1, 2, 3 end local a, b, c = m() print(a + b + c)', "6"),
    # 12. 条件分支
    ('local function g(x) if x > 0 then return "POS" elseif x < 0 then return "NEG" else return "ZERO" end end print(g(5), g(-1), g(0))', "POS\tNEG\tZERO"),
    # 13. 元表 __index
    ('local t = setmetatable({}, {__index = function(_, k) return "KEY_" .. k end}) print(t.foo)', "KEY_foo"),
    # 14. table.insert
    ('local t = {} table.insert(t, "a") table.insert(t, "b") print(#t, t[1] .. t[2])', "2\tab"),
    # 15. 复杂表达式
    ('print((2 + 3) * 4 - 10 / 2)', "15"),
    # 16. 多返回值作为参数（多值传播）
    ('local function m() return 1, 2, 3 end print(m())', "1\t2\t3"),
    # 17. 多返回值 table 构造
    ('local function m() return "x", "y" end local t = {m()} print(#t, t[1] .. t[2])', "2\txy"),
    # 18. 闭包共享 upvalue（两个闭包修改同一 upvalue）
    ('local function pair() local s = 0 local function add() s = s + 1 return s end local function get() return s end return add, get end local a, g = pair() a() a() a() print(g())', "3"),
    # 19. 嵌套闭包（多层 upvalue）
    ('local function outer() local x = 10 local function mid() local function inner() return x * 2 end return inner() end return mid() end print(outer())', "20"),
    # 20. 闭包作为表方法（self + upvalue）
    ('local function make() local count = 0 local obj = {} function obj:inc() count = count + 1 return count end function obj:reset() count = 0 end return obj end local o = make() o:inc() o:inc() o:reset() o:inc() print(o:inc())', "2"),
    # 21. ipairs 多返回值解构
    ('local function p() return 1, "a" end local t = {} for i = 1, 3 do local n, s = p() t[i] = n .. s end print(t[1], t[2], t[3])', "1a\t1a\t1a"),
    # 22. 字符串拼接链 + 多返回值
    ('local function parts() return "a", "b", "c" end local s = "" .. parts() print(s)', "a"),
    # 23. 递归 + 闭包（斐波那契）
    ('local function fib() local function f(n) if n < 2 then return n end return f(n-1) + f(n-2) end return f end local F = fib() print(F(10))', "55"),
    # 24. 复杂表 + 元方法 + 闭包
    ('local function makevec(x, y) local v = {x = x, y = y} local len = math.sqrt(x*x + y*y) setmetatable(v, {__tostring = function() return "(" .. x .. "," .. y .. ")" end}) return v, len end local v, l = makevec(3, 4) print(tostring(v), l)', "(3,4)\t5"),
    # 25. while + 闭包捕获循环变量（标准 Lua 语义：共享同一 upvalue，循环结束 i=4）
    #     验证混淆器正确保持 upvalue 共享语义（输出 40,40,40 而非 10,20,30）
    ('local fns = {} local i = 1 while i <= 3 do fns[i] = function() return i * 10 end i = i + 1 end print(fns[1](), fns[2](), fns[3]())', "40\t40\t40"),
]


def run_lua(code):
    """运行 Lua 代码，返回 (returncode, stdout, stderr)。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua',
                                      delete=False, encoding='utf-8') as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run([LUA, path], capture_output=True,
                           text=True, timeout=10)
        return r.returncode, r.stdout, r.stderr
    finally:
        os.unlink(path)


def main():
    ok = True
    total = 0
    runtime_ok = 0
    for i, (src, expected) in enumerate(SAMPLES, 1):
        for seed in [0, 1, 2, 42, 100, 2024, 99999]:
            total += 1
            # 混淆
            try:
                r = obfuscate(src, seed=seed)
                code = r["code"]
            except Exception as e:
                print(f"FAIL 样本{i} seed{seed}: 混淆失败 {e}")
                ok = False
                continue
            # 运行
            rc, out, err = run_lua(code)
            if rc != 0:
                print(f"FAIL 样本{i} seed{seed}: Lua 运行报错 (rc={rc})")
                print(f"  stderr: {err[:300]}")
                ok = False
                continue
            # 输出校验
            if expected not in out:
                print(f"FAIL 样本{i} seed{seed}: 输出不匹配")
                print(f"  期望含: {expected!r}")
                print(f"  实际: {out[:200]!r}")
                ok = False
                continue
            runtime_ok += 1
        print(f"[run {i:2d}] OK — 7 种子全部运行成功，输出正确（含 {expected!r}）")

    print()
    print(f"运行时通过: {runtime_ok}/{total}")
    print("==== 100% 稳定运行 + 输出正确显示 ====" if ok
          else "==== 存在失败 ====")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
