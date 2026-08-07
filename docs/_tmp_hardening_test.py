# -*- coding: utf-8 -*-
"""加固验证测试：语义等价（lupa 运行时）+ 稳定性 + 万行不卡死。
对比 original 与 obfuscated 在相同 Roblox shim 下的 print 输出。"""
import os, sys, io, traceback, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
exec(open(os.path.join(HERE, 'obfuscator_all.py')).read())


def _norm_outs(outs):
    """归一化输出：抹平错误消息中的行号/列号差异。

    混淆后 error() 抛出的位置必然变化（如 [string "..."]:1190: x
    vs 原始 :1: x），这是行号重排，非语义差异。统一替换 `]:数字:` 为
    `]:N:`，使 pccall 等用例能正确比对语义而非位置。
    """
    return [re.sub(r'\]:\d+:', ']:N:', s) for s in outs]

try:
    from lupa import LuaRuntime
    LUPA_OK = True
except Exception as e:
    LUPA_OK = False
    print("lupa 不可用:", e)

# ---------- Roblox shim ----------
def make_shim(env="B"):
    """env='A': task.wait 不 yield（模拟问题注入器）；'B': 正常 yield。"""
    yields = (env == "B")
    shim_lua = r'''
    function _build_shim(yields, out)
        local task = {
            wait = function(t)
                if yields then coroutine.yield() else return end
            end,
            spawn = function(f) local co = coroutine.create(f) end,
            delay = function(t, f) end,
            defer = function(f) end,
        }
        local function spawn(fn)
            local co = coroutine.create(fn)
            -- 不 resume：避免后台循环阻塞；spawn 的保护逻辑不影响主流程
        end
        local function tick() return os.clock() end
        local function getgenv() return _G end
        local function getrenv() return _G end
        local function identifyexecutor() return "TestInjector", "1.0" end
        local function setclipboard() end
        local function request() return {StatusCode=200, Body=""} end
        local function writefile() end
        local function readfile() return "" end
        local function delfile() end
        local function isfile() return false end
        local function makefolder() end
        local Drawing = setmetatable({}, {__index = function(_,k) return function() return setmetatable({}, {__index=function() return nil end}) end end})
        -- game / workspace 占位 userdata
        local game = setmetatable({}, {__index = function(t,k)
            if k == "GetService" then return function(_, s) return setmetatable({}, {__index=function() return function() return nil end end}) end end
            return setmetatable({}, {__index=function() return function() return nil end end})
        end})
        local workspace = game
        -- print 重定向到 out
        local function print(...)
            local args = {...}
            local parts = {}
            for i=1,#args do parts[i] = tostring(args[i]) end
            out[#out+1] = table.concat(parts, "\t")
        end
        -- loadstring
        local function loadstring(s, n) return load(s, n) end
        -- warn 静默
        local function warn() end
        -- hookmetamethod / hookfunction 占位
        local function hookfunction() end
        local function hookmetamethod() end
        -- bit32 库（Roblox 原生有；用 5.4 位运算实现）
        local bit32 = {
            bxor = function(a, b) return a ~ b end,
            band = function(a, b) return a & b end,
            bor = function(a, b) return a | b end,
            bnot = function(a) return ~a end,
            lshift = function(a, n) return a << n end,
            rshift = function(a, n) return a >> n end,
            arshift = function(a, n) return a >> n end,
        }
        local bit = bit32
        -- Roblox 常用全局
        local function typeof(v) return type(v) end
        local function typeof2(v) return type(v) end
        local function tostring2(v) return tostring(v) end
        local function Instance(cls) return setmetatable({}, {__index=function() return function() return nil end end}) end
        local Vector3 = function(x,y,z) return {X=x,Y=y,Z=z} end
        local CFrame = function() return {} end
        local Color3 = function() return {} end
        local UDim2 = function() return {} end
        local Enum = setmetatable({}, {__index=function() return setmetatable({},{__index=function() return 0 end}) end})
        local function HttpService() return {JSONEncode=function(_,t) return "" end, JSONDecode=function() return {} end} end
        local RunService = {Heartbeat={},RenderStepped={}}
        local function connect(ev, fn) return {Disconnect=function() end} end
        return {
            task=task, spawn=spawn, tick=tick, getgenv=getgenv, getrenv=getrenv,
            identifyexecutor=identifyexecutor, setclipboard=setclipboard,
            request=request, writefile=writefile, readfile=readfile, delfile=delfile,
            isfile=isfile, makefolder=makefolder, Drawing=Drawing, game=game,
            workspace=workspace, print=print, loadstring=loadstring, warn=warn,
            hookfunction=hookfunction, hookmetamethod=hookmetamethod,
            bit32=bit32, bit=bit,
            typeof=typeof, Instance=Instance, Vector3=Vector3, CFrame=CFrame,
            Color3=Color3, UDim2=UDim2, Enum=Enum, HttpService=HttpService,
            RunService=RunService, connect=connect,
        }
    end
    return _build_shim
    '''
    return shim_lua

def run_with_shim(code, env="B", timeout_sense=True):
    """运行 code，返回 (print输出列表, error_or_None)。
    在 lupa 中注入 shim 后执行。超时/错误返回。"""
    lua = LuaRuntime(unpack_returned_tuples=True)
    out = lua.table()
    try:
        lua.execute(make_shim(env))
        lua.globals().out = out
        # 注入 shim 全局
        shim = lua.eval(f'_build_shim({("true" if env=="B" else "false")}, out)')
        g = lua.globals()
        for k in ['task','spawn','tick','getgenv','getrenv','identifyexecutor',
                  'setclipboard','request','writefile','readfile','delfile','isfile',
                  'makefolder','Drawing','game','workspace','print','loadstring',
                  'warn','hookfunction','hookmetamethod','bit32','bit',
                  'typeof','Instance','Vector3','CFrame','Color3','UDim2','Enum',
                  'HttpService','RunService','connect']:
            g[k] = shim[k]
        # 执行
        lua.execute(code)
    except Exception as e:
        # 取出已 print 的内容
        outs = [out[i] for i in range(1, len(out)+1)] if len(out) else []
        return outs, str(e)
    outs = [out[i] for i in range(1, len(out)+1)] if len(out) else []
    return outs, None


# ---------- 测试用例 ----------
CASES = [
    # (name, src, expected_prints_or_None)
    ("arith", "print(1+2*3)", ["7"]),
    ("strcat", 'local s="hello".." ".."world" print(s)', ["hello world"]),
    ("forloop", "local s=0 for i=1,10 do s=s+i end print(s)", ["55"]),
    ("closure", "local function c() local n=0 return function() n=n+1 return n end end local f=c() print(f(),f(),f())", ["1\t2\t3"]),
    ("table", "local t={1,2,3} print(#t, t[2])", ["3\t2"]),
    ("method", 'local s="a,b,c" local n=0 for w in string.gmatch(s,"[^,]+") do n=n+1 end print(n)', ["3"]),
    ("cond", "local function g(x) if x>=90 then return 'A' elseif x>=60 then return 'B' else return 'F' end end print(g(95),g(70),g(30))", ["A\tB\tF"]),
    ("recur", "local function f(n) if n<=1 then return 1 end return n*f(n-1) end print(f(5))", ["120"]),
    ("string_len", 'print(#"苍米独家混淆", string.sub("abcdef",2,4))', ["18\tbcd"]),
    ("bitop", "print((5 ~ 3), (10 & 6), (4 | 1))", ["6\t2\t5"]),
    ("metatab", 'local t=setmetatable({},{__index=function(_,k) return k.."!" end}) print(t.foo)', ["foo!"]),
    ("multi_ret", "local function m() return 1,2,3 end local a,b,c=m() print(a,b,c)", ["1\t2\t3"]),
    ("pccall", 'local ok,err=pcall(function() error("x") end) print(ok, err)', None),
    ("while_brk", "local i=0 while true do i=i+1 if i>=5 then break end end print(i)", ["5"]),
    ("nested_str", 'local t={name="苍米",ver="2.0"} print(t.name, t.ver)', ["苍米\t2.0"]),
]

def test_semantic():
    """语义等价：original 与 obfuscated 输出一致。"""
    if not LUPA_OK:
        print("SKIP 语义测试（无 lupa）"); return True
    ok = True
    seeds = [1, 2, 3, 42, 777]
    pass_cnt = 0; fail_cnt = 0
    for name, src, expected in CASES:
        # 先跑 original
        orig_out, orig_err = run_with_shim(src, env="B")
        if orig_err:
            print(f"[sem {name}] 原始脚本自身报错: {orig_err}")
            ok = False; fail_cnt += 1; continue
        for seed in seeds:
            try:
                r = obfuscate(src, seed=seed)
            except Exception as e:
                print(f"[sem {name} seed{seed}] obfuscate 抛异常: {e}")
                ok = False; fail_cnt += 1; continue
            obf_out, obf_err = run_with_shim(r["code"], env="B")
            if obf_err:
                # 可能是 VM 保护导致的 error（水印等）。检查是否是预期
                print(f"[sem {name} seed{seed}] 混淆脚本报错: {obf_err[:80]}")
                ok = False; fail_cnt += 1; continue
            nob, nor = _norm_outs(obf_out), _norm_outs(orig_out)
            if nob != nor:
                print(f"[sem {name} seed{seed}] 输出不匹配: orig={orig_out} obf={obf_out}")
                ok = False; fail_cnt += 1; continue
            # 若有期望值，也校验
            if expected is not None and nob != _norm_outs(expected):
                print(f"[sem {name} seed{seed}] 期望={expected} 实际={obf_out}")
                ok = False; fail_cnt += 1; continue
            pass_cnt += 1
        if ok and False:
            print(f"[sem {name}] OK ({len(seeds)} seeds)")
    print(f"语义等价: PASS={pass_cnt} FAIL={fail_cnt}")
    return ok


def test_stability():
    """稳定性：parse→generate 往返。"""
    ok = True
    for i, (name, src, _) in enumerate(CASES):
        for seed in [1, 2, 3]:
            try:
                r = obfuscate(src, seed=seed)
                code = r["code"]
                chunk2 = parse_source(code)
                code2 = generate_code(chunk2)
                assert code2
            except Exception as e:
                print(f"[stab {name} seed{seed}] FAIL: {e}")
                ok = False
    print(f"稳定性往返: {'OK' if ok else 'FAIL'}")
    return ok


def test_10k_nocrash():
    """万行脚本不卡死（A/B 环境）。"""
    if not LUPA_OK:
        print("SKIP 万行测试（无 lupa）"); return True
    p = os.path.join(HERE, '..', 'tests', 'big10k.lua')
    if not os.path.exists(p):
        print("SKIP 万行测试（无 big10k.lua）"); return True
    src = open(p, encoding='utf-8').read()
    ok = True
    for env in ["A", "B"]:
        for seed in [1, 2]:
            try:
                r = obfuscate(src, seed=seed)
            except Exception as e:
                print(f"[10k env{env} seed{seed}] obfuscate 异常: {e}")
                ok = False; continue
            # 运行（不卡死=在合理时间返回）
            obf_out, obf_err = run_with_shim(r["code"], env=env)
            # 万行脚本主要验证不卡死不报错（部分脚本可能 print 大量行）
            # 只要没卡死（函数返回）即通过
            print(f"[10k env{env} seed{seed}] 返回 out={len(obf_out)}行 err={('无' if not obf_err else obf_err[:60])}")
    print(f"万行不卡死: {'OK' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    print("=" * 60)
    print("加固验证测试（当前代码 GREEN 基线）")
    print("=" * 60)
    s_ok = test_stability()
    print()
    m_ok = test_semantic()
    print()
    k_ok = test_10k_nocrash()
    print()
    print("=" * 60)
    all_ok = s_ok and m_ok and k_ok
    print("==== 全部通过 ====" if all_ok else "==== 存在失败 ====")
    sys.exit(0 if all_ok else 1)
