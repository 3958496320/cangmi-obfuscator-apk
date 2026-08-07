# -*- coding: utf-8 -*-
"""针对性测试 bundle VM 的 JumpTable 改造（覆盖跳转/返回/调用/分支/循环）。"""
import sys
sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")
import importlib.util
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

spec = importlib.util.spec_from_file_location("obfuscator_all", "/workspace/docs/obfuscator_all.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
obfuscate = mod.obfuscate

cfg = make_envs()[0][1]

# 测试用例：覆盖 VM 各种操作码
cases = [
    # 纯算术（LOADK/MOVR/BINOP/RET）
    ("算术", 'local function f(a,b) local c=a+b*2 return c-1 end print(f(3,4))', "10"),
    # if 分支（LOADBOOL/CJMP/JMP）
    ("if分支", 'local function f(n) if n>5 then return "大" else return "小" end end print(f(3), f(8))', "小\t大"),
    # while 循环（CJMP/JMP 反复）
    ("while循环", 'local function f(n) local s=0 local i=1 while i<=n do s=s+i i=i+1 end return s end print(f(100))', "5050"),
    # for 循环（编译为 while）
    ("for循环", 'local function f(n) local s=0 for i=1,n do s=s+i end return s end print(f(10))', "55"),
    # 多返回值（RET n>1）
    ("多返回值", 'local function f() return 1,2,3 end local a,b,c=f() print(a+b+c)', "6"),
    # 嵌套调用（CALL）
    ("函数调用", 'local function sq(x) return x*x end local function f(a,b) return sq(a)+sq(b) end print(f(3,4))', "25"),
    # 一元运算（UNOP -/not/#）
    ("一元运算", 'local function f(a,s) return -a, not a, #s end local x,y,z=f(5,"abc") print(x,y,z) -- -5 / not 5=false / #"abc"=3', "-5\tfalse\t3"),
    # 字符串（LOADSTR）
    ("字符串", 'local function f() return "hello" end print(f())', "hello"),
    # 表操作（NEWTAB/SETTAB/GETTAB）
    ("表操作", 'local function f() local t={} t[1]=10 t[2]=20 return t[1]+t[2] end print(f())', "30"),
    # 复杂递归
    ("递归fib", 'local function fib(n) if n<=2 then return 1 end return fib(n-1)+fib(n-2) end print(fib(10))', "55"),
    # 逻辑短路
    ("短路求值", 'local function f(a,b) return a and b or "none" end print(f(true, "yes"), f(false, "no"))', "yes\tnone"),
]

def run_capture(code):
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    lua.execute(build_shim_lua(cfg))
    env = lua.eval("_G._build_ninja_shim()")
    for k in ["bit32","bit","task","tick","getgenv","getrenv","identifyexecutor",
              "setclipboard","request","writefile","readfile","delfile","isfile",
              "makefolder","Drawing","game","workspace","warn","hookfunction",
              "hookmetamethod","typeof","Instance","Vector3","CFrame","Color3",
              "UDim2","Enum","HttpService","RunService","connect","spawn","delay",
              "wait","loadstring","debug","syn","protect_gui","http_get"]:
        if env[k] is not None or k in ["bit32","bit","task","debug","syn","protect_gui"]:
            g[k] = env[k]
    out = []
    g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
    g["__OMNISHIELD_LOADED"] = None
    lua.execute(code)
    return "\n".join(out)

total = passed = 0
for name, code, expected in cases:
    total += 1
    sys.stdout.write("{:<12} ... ".format(name))
    sys.stdout.flush()
    try:
        out_o = run_capture(code)
        res = obfuscate(code, seed=42)
        out_b = run_capture(res["code"])
        if out_o == out_b and (expected is None or out_o == expected):
            sys.stdout.write("PASS\n")
            passed += 1
        else:
            sys.stdout.write("FAIL\n  原始: {!r}\n  混淆: {!r}\n  期望: {!r}\n".format(out_o[:60], out_b[:60], expected))
    except Exception as e:
        sys.stdout.write("FAIL (exc {})\n".format(str(e)[:80]))

print("-" * 40)
print("VM JumpTable 测试: {}/{} 通过".format(passed, total))
print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====")
sys.exit(0 if passed == total else 1)
