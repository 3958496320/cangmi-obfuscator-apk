# -*- coding: utf-8 -*-
"""
端到端语义等价测试 + 万行脚本仿真测试。

流程：
  1. 对每个语义用例：原始代码 → obfuscate → 混淆代码
  2. 在 6 种仿真忍者注入器环境下分别运行原始 / 混淆代码
  3. 对比 stdout（错误消息行号归一化），验证语义等价
  4. 额外：混淆 big10k.lua，在仿真环境运行，验证不卡死、不报错
"""
import os, sys, time, traceback, subprocess
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_ninja_quicktest import build_shim_lua, make_envs

# ------------------------------------------------------------
# 加载混淆器
# ------------------------------------------------------------
print("加载混淆器...", flush=True)
try:
    from obfuscator_core import obfuscate
    print("混淆器加载 OK", flush=True)
except Exception as e:
    print("混淆器加载失败:", e, flush=True)
    traceback.print_exc()
    sys.exit(2)


# ------------------------------------------------------------
# 语义等价用例（原始 Lua 代码 → 预期输出）
# 用 (name, code, expected_outputs) 表示；expected_outputs 为可能的合法输出集合
# ------------------------------------------------------------
SEMANTIC_CASES = [
    ("算术运算",
     'local a=10 local b=3 print(a+b, a-b, a*b, a//b, a%b)',
     {"13\t7\t30\t3\t1"}),
    ("浮点除法",
     'local a=10 local b=4 print(a/b)',
     {"2.5"}),
    ("字符串拼接",
     'local s="abc".."def".."ghi" print(s, #s)',
     {"abcdefghi\t9"}),
    ("字符串长度中文",
     'local s="苍米独家" print(#s, s)',
     {"12\t苍米独家"}),
    ("条件分支",
     'local x=5 if x>3 then print("big") elseif x==3 then print("eq") else print("small") end',
     {"big"}),
    ("for循环求和",
     'local s=0 for i=1,100 do s=s+i end print(s)',
     {"5050"}),
    ("while循环",
     'local i=1 local s=0 while i<=5 do s=s+i i=i+1 end print(s)',
     {"15"}),
    ("函数调用",
     'local function f(x,y) return x*x+y end print(f(3,4))',
     {"13"}),
    ("递归阶乘",
     'local function fact(n) if n<=1 then return 1 end return n*fact(n-1) end print(fact(5))',
     {"120"}),
    ("表操作",
     'local t={} for i=1,5 do t[i]=i*i end local s=0 for _,v in ipairs(t) do s=s+v end print(s)',
     {"55"}),
    ("多返回值",
     'local function m() return 1,2,3 end local a,b,c=m() print(a,b,c)',
     {"1\t2\t3"}),
    ("pcall成功",
     'local ok,r=pcall(function() return 42 end) print(ok,r)',
     {"True\t42", "true\t42"}),
    ("pcall失败_行号归一化",
     'local ok,err=pcall(function() error("boom") end) print(ok, (tostring(err):gsub("^.-:%d+: ", "ERR: ")))',
     {"False\tERR: boom", "false\tERR: boom"}),
    ("math函数",
     'print(math.floor(3.7), math.ceil(3.2), math.abs(-5), math.max(1,9,3))',
     {"3\t4\t5\t9"}),
    ("string方法",
     'print(string.upper("abc"), string.sub("hello",2,4), string.rep("x",3))',
     {"ABC\tell\txxx"}),
    ("嵌套闭包",
     'local function counter() local n=0 return function() n=n+1 return n end end local c=counter() print(c(),c(),c())',
     {"1\t2\t3"}),
    ("表元方法",
     'local t=setmetatable({},{__add=function(a,b) return setmetatable({x=a.x+b.x},{}) end}) t.x=10 local r=t+{x=5} print(r.x)',
     {"15"}),
    ("局部变量作用域",
     'local x=1 do local x=10 print(x) end print(x)',
     {"10\n1"}),
]


# ------------------------------------------------------------
# 运行单条 Lua 代码，捕获 print 输出，返回 (ok, output_or_err)
# ------------------------------------------------------------
def run_lua_capture(code, cfg):
    """在仿真环境运行 code，捕获所有 print 输出，返回 (ok, output)"""
    try:
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
        out_lines = []
        g["print"] = lambda *a: out_lines.append("\t".join(str(x) for x in a))
        g["__OMNISHIELD_LOADED"] = None
        lua.execute(code)
        return True, "\n".join(out_lines)
    except Exception as e:
        return False, "EXC: " + str(e).replace("\n", " ")[:150]


def normalize(s):
    """归一化输出：错误消息中的行号 :数字: → :N:；浮点尾零"""
    import re
    s = re.sub(r":\d+:", ":N:", s)
    return s


# ------------------------------------------------------------
# 端到端语义等价测试
# ------------------------------------------------------------
def run_semantic_tests():
    print("=" * 70, flush=True)
    print("端到端语义等价测试（原始 vs 混淆）", flush=True)
    print("=" * 70, flush=True)

    total = passed = 0
    fails = []
    # 只在完整环境下做语义对比（其他环境降级可能影响输出，单独验证不报错即可）
    cfg = make_envs()[0][1]
    for name, code, expected in SEMANTIC_CASES:
        total += 1
        sys.stdout.write("{:<22} ... ".format(name))
        sys.stdout.flush()
        t0 = time.time()
        try:
            # 1. 原始
            ok_o, out_o = run_lua_capture(code, cfg)
            if not ok_o:
                sys.stdout.write("FAIL (原始报错: {})\n".format(out_o[:80]))
                fails.append("{} (原始报错)".format(name))
                continue
            # 2. 混淆
            res = obfuscate(code, seed=42)
            obf_code = res["code"]
            ok_b, out_b = run_lua_capture(obf_code, cfg)
            if not ok_b:
                sys.stdout.write("FAIL (混淆报错: {})\n".format(out_b[:80]))
                fails.append("{} (混淆报错)".format(name))
                continue
            # 3. 对比（归一化）
            n_o = normalize(out_o)
            n_b = normalize(out_b)
            # 检查原始输出是否在预期集合内
            if expected and n_o not in expected and out_o not in expected:
                sys.stdout.write("FAIL (原始输出异常: {!r})\n".format(out_o[:80]))
                fails.append("{} (原始输出异常)".format(name))
                continue
            if n_o != n_b:
                sys.stdout.write("FAIL (语义不等价: 原={!r} 混淆={!r})\n".format(n_o[:60], n_b[:60]))
                fails.append("{} (语义不等价)".format(name))
                continue
            elapsed = time.time() - t0
            sys.stdout.write("PASS ({:.2f}s)\n".format(elapsed))
            sys.stdout.flush()
            passed += 1
        except Exception as e:
            sys.stdout.write("FAIL (异常: {})\n".format(str(e)[:80]))
            fails.append("{} (异常)".format(name))
    print("-" * 70, flush=True)
    print("语义等价: {}/{} 通过".format(passed, total), flush=True)
    if fails:
        print("失败:", fails, flush=True)
    return passed, total, fails


# ------------------------------------------------------------
# 混淆代码在 6 种环境下不报错测试
# ------------------------------------------------------------
def run_multi_env_tests():
    print("=" * 70, flush=True)
    print("混淆代码多环境不报错测试（6 环境 × 3 用例）", flush=True)
    print("=" * 70, flush=True)
    # 选 3 个有代表性的用例
    sample_cases = [SEMANTIC_CASES[0], SEMANTIC_CASES[4], SEMANTIC_CASES[8]]
    total = passed = 0
    fails = []
    for env_name, cfg in make_envs():
        for name, code, _ in sample_cases:
            total += 1
            label = "{} / {}".format(env_name, name)
            sys.stdout.write("{:<28} ... ".format(label[:28]))
            sys.stdout.flush()
            try:
                res = obfuscate(code, seed=7)
                ok, out = run_lua_capture(res["code"], cfg)
                if ok:
                    sys.stdout.write("PASS\n")
                    passed += 1
                else:
                    sys.stdout.write("FAIL ({})\n".format(out[:60]))
                    fails.append(label)
            except Exception as e:
                sys.stdout.write("FAIL (exc {})\n".format(str(e)[:60]))
                fails.append(label)
    print("-" * 70, flush=True)
    print("多环境: {}/{} 通过".format(passed, total), flush=True)
    if fails:
        print("失败:", fails, flush=True)
    return passed, total, fails


# ------------------------------------------------------------
# 万行脚本混淆 + 仿真运行测试
# 策略：big10k 含 Roblox 事件循环（RenderStepped:Connect），lupa 仿真环境无法
# 真正 yield wait，会卡在事件循环。因此采用：
#   1. loadstring 验证（语法正确）
#   2. subprocess 隔离执行，超时 8s：
#      - 输出 PASS → 执行完成
#      - 输出 FAIL → API 不兼容（混淆器 bug）
#      - 超时 → 卡在事件循环（与原始行为一致，非混淆器问题）= PASS
#   3. 原始 big10k 对照（应同样超时）
# ------------------------------------------------------------
def _subproc_run(lua_file, env_idx, timeout=8):
    """子进程执行，返回 (status, detail)。status ∈ {PASS, FAIL, TIMEOUT}"""
    try:
        r = subprocess.run(
            ["python3", "/workspace/docs/_tmp_run_lua_subproc.py", lua_file, str(env_idx)],
            capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "").strip()
        if out.startswith("PASS"):
            return "PASS", "执行完成"
        elif out.startswith("FAIL"):
            return "FAIL", out[:120]
        else:
            return "FAIL", "未知输出: " + out[:80]
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ">{}s".format(timeout)


def run_big_script_test():
    print("=" * 70, flush=True)
    print("万行脚本混淆 + 仿真运行测试", flush=True)
    print("=" * 70, flush=True)
    big_path = "/workspace/tests/big10k.lua"
    if not os.path.exists(big_path):
        print("SKIP: {} 不存在".format(big_path), flush=True)
        return 0, 1, ["big10k 缺失"]
    src = open(big_path, encoding="utf-8").read()
    print("原始: {} 行, {} 字节".format(src.count("\n")+1, len(src)), flush=True)

    sys.stdout.write("混淆中... ")
    sys.stdout.flush()
    t0 = time.time()
    try:
        res = obfuscate(src, seed=123)
        obf = res["code"]
        print("OK ({:.1f}s, {} 行)".format(time.time()-t0, obf.count("\n")+1), flush=True)
    except Exception as e:
        print("混淆失败: {}".format(str(e)[:120]), flush=True)
        return 0, 1, ["混淆失败"]

    # 写出文件供 subprocess 执行
    obf_path = "/tmp/_big_obf.lua"
    open(obf_path, "w", encoding="utf-8").write(obf)

    # 1. loadstring 语法验证（完整环境 + 全缺失）
    print("\n[1] loadstring 语法验证:", flush=True)
    total = passed = 0
    fails = []
    for env_idx, env_name in [(0, "完整环境"), (5, "全缺失")]:
        total += 1
        cfg = make_envs()[env_idx][1]
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
        g["print"] = lambda *a: None
        g["__OBF_CODE"] = obf
        lua.execute(r'''
            local f, err = loadstring(_G.__OBF_CODE, "big_obf")
            _G.__load_ok = (f ~= nil)
            _G.__load_err = err
        ''')
        ok = g["__load_ok"]
        if ok:
            print("  [{}] PASS (语法正确)".format(env_name), flush=True)
            passed += 1
        else:
            err = g["__load_err"]
            print("  [{}] FAIL ({})".format(env_name, str(err)[:80]), flush=True)
            fails.append("loadstring/" + env_name)

    # 2. 原始 big10k 基线对照（应超时=卡在事件循环）
    print("\n[2] 原始 big10k 基线对照 (subprocess 超时 8s):", flush=True)
    total += 1
    st, det = _subproc_run(big_path, 0, 8)
    # 原始预期超时（卡在事件循环）；若 PASS（执行完）或 FAIL（报错）记录
    baseline_timeout = (st == "TIMEOUT")
    print("  [原始/完整环境] {} ({})".format(st, det), flush=True)
    if baseline_timeout:
        passed += 1
    else:
        # 原始未超时，说明仿真环境能跑完，那混淆也应跑完
        fails.append("原始基线未超时")

    # 3. 混淆后执行（完整 + 全缺失），与基线对比
    print("\n[3] 混淆后执行 (subprocess 超时 8s):", flush=True)
    for env_idx, env_name in [(0, "完整环境"), (5, "全缺失")]:
        total += 1
        st, det = _subproc_run(obf_path, env_idx, 8)
        # 判定：与基线行为一致即 PASS
        if baseline_timeout:
            # 基线超时 → 混淆超时=PASS（一致），混淆报错=FAIL
            if st == "TIMEOUT":
                print("  [{}/混淆] PASS (超时=与原始一致，卡在事件循环)".format(env_name), flush=True)
                passed += 1
            elif st == "PASS":
                print("  [{}/混淆] PASS (执行完成)".format(env_name), flush=True)
                passed += 1
            else:
                print("  [{}/混淆] FAIL ({})".format(env_name, det), flush=True)
                fails.append("执行/{}/{}".format(env_name, det[:40]))
        else:
            # 基线未超时 → 混淆应 PASS 或行为一致
            if st == "PASS":
                print("  [{}/混淆] PASS (执行完成)".format(env_name), flush=True)
                passed += 1
            else:
                print("  [{}/混淆] FAIL ({})".format(env_name, det), flush=True)
                fails.append("执行/{}/{}".format(env_name, det[:40]))

    print("-" * 70, flush=True)
    print("万行脚本: {}/{} 通过".format(passed, total), flush=True)
    return passed, total, fails


if __name__ == "__main__":
    p1, t1, f1 = run_semantic_tests()
    p2, t2, f2 = run_multi_env_tests()
    p3, t3, f3 = run_big_script_test()

    total = t1 + t2 + t3
    passed = p1 + p2 + p3
    print("=" * 70, flush=True)
    print("总计: {} 通过 / {}".format(passed, total), flush=True)
    all_fails = f1 + f2 + f3
    if all_fails:
        print("全部失败列表:")
        for f in all_fails:
            print("  - {}".format(f), flush=True)
    print("==== ALL PASS ====" if passed == total and not all_fails else "==== HAS FAIL ====", flush=True)
    sys.exit(0 if passed == total and not all_fails else 1)
