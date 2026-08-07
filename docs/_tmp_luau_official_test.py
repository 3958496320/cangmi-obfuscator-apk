# -*- coding: utf-8 -*-
"""用官方 Roblox Luau CLI（与忍者注入器同款运行时）做语义等价测试。

比 lupa（标准 Lua 5.1）更准确：能暴露 Luau 特性（// 整除、+=、continue、
类型注解等）相关的崩溃，以及 Luau 解析器对混淆产物的真实兼容性。
"""
import sys, os, subprocess, tempfile
sys.path.insert(0, "/workspace/docs")
from obfuscator_all import obfuscate_code

LUAU = "/tmp/luau-bin/luau"

# 纯 Lua 语义用例（不依赖 Roblox API，luau CLI 能直接跑）
CASES = [
    ("算术", 'local a=10 local b=3 print(a+b, a-b, a*b, a//b, a%b)', "13\t7\t30\t3\t1"),
    ("浮点除法", 'local a=10 local b=4 print(a/b)', "2.5"),
    ("字符串拼接", 'local s="abc".."def".."ghi" print(s, #s)', "abcdefghi\t9"),
    ("条件分支", 'local x=5 if x>3 then print("big") elseif x==3 then print("eq") else print("small") end', "big"),
    ("for循环", 'local s=0 for i=1,100 do s=s+i end print(s)', "5050"),
    ("while循环", 'local i=1 local s=0 while i<=5 do s=s+i i=i+1 end print(s)', "15"),
    ("函数调用", 'local function f(x,y) return x*x+y end print(f(3,4))', "13"),
    ("递归阶乘", 'local function fact(n) if n<=1 then return 1 end return n*fact(n-1) end print(fact(5))', "120"),
    ("闭包", 'local function counter() local c=0 return function() c=c+1 return c end end local f=counter() print(f(),f(),f())', "1\t2\t3"),
    ("表操作", 'local t={1,2,3,4,5} local s=0 for _,v in ipairs(t) do s=s+v end print(s)', "15"),
    ("字符串方法", 'local s="hello world" print(string.upper(s), string.sub(s,1,5))', "HELLO WORLD\thello"),
    ("math函数", 'print(math.floor(3.7), math.ceil(3.2), math.abs(-5))', "3\t4\t5"),
    ("位运算", 'print(bit32.band(0xFF, 0x0F), bit32.bor(0xF0, 0x0F))', "15\t255"),
    ("pcall", 'local ok=pcall(function() error("boom") end) print(ok)', "false"),
    ("嵌套表", 'local t={a={b={c=42}}} print(t.a.b.c)', "42"),
    ("continue", 'local s=0 for i=1,10 do if i%2==0 then continue end s=s+i end print(s)', "25"),
    ("复合赋值", 'local x=5 x+=3 x*=2 print(x)', "16"),
    ("字符串格式", 'print(string.format("%d-%s", 42, "ok"))', "42-ok"),
    # Luau 特有语法（lupa/Lua5.1 测不了，忍者注入器会遇到）
    ("类型注解", 'local x: number = 5 local s: string = "hi" print(x, s)', "5\thi"),
    ("and或短路", 'local function f(v) return v and v*2 or 0 end print(f(5), f(nil))', "10\t0"),
    ("嵌套continue", 'local r=0 for i=1,3 do for j=1,3 do if j==2 then continue end r+=1 end end print(r)', "6"),
    ("break嵌套", 'local r=0 for i=1,10 do if i>3 then break end r+=i end print(r)', "6"),
    ("字符串拼接赋值", 'local s="a" s..="b" s..="c" print(s)', "abc"),
    ("if表达式", 'local x = if 5 > 3 then "yes" else "no" print(x)', "yes"),
]

def run_luau(code, timeout=15):
    """用官方 luau CLI 运行代码，返回 (stdout, stderr, rc)。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run([LUAU, path], capture_output=True, text=True, timeout=timeout)
        return r.stdout.rstrip("\n"), r.stderr.rstrip("\n"), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    finally:
        os.unlink(path)

def main():
    print("=" * 60)
    print("官方 Roblox Luau 0.732 语义等价测试（与忍者注入器同款运行时）")
    print("=" * 60)
    passed = failed = 0
    fails = []
    for name, src, expected in CASES:
        # 先验证原始代码在 luau 下的输出（基线）
        o0, e0, rc0 = run_luau(src)
        if o0 != expected:
            print(f"[基线失败] {name}: 期望 {expected!r} 实际 {o0!r}")
            continue
        # 混淆（全保护）
        try:
            obf = obfuscate_code(src, ninja_mode=False)
        except Exception as ex:
            print(f"[混淆失败] {name}: {ex}")
            failed += 1
            fails.append((name, "混淆异常", str(ex)))
            continue
        # 用 luau 跑混淆产物
        o1, e1, rc1 = run_luau(obf)
        if o1 == expected:
            print(f"[PASS] {name}  (混淆产物 {len(obf)} 字符)")
            passed += 1
        else:
            print(f"[FAIL] {name}: 期望 {expected!r}")
            print(f"       实际 stdout={o1!r}")
            print(f"       stderr={e1[:200]!r} rc={rc1}")
            failed += 1
            fails.append((name, o1, e1))
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败 / {len(CASES)} 总计")
    if fails:
        print("\n失败详情:")
        for n, o, e in fails:
            print(f"  - {n}: {o[:80]} | {e[:120]}")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
