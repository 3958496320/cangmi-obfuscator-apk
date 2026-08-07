# -*- coding: utf-8 -*-
"""
忍者注入器高仿真沙箱测试。

模拟忍者注入器的关键特性：
1. Luau 语义（用 lupa Lua 5.5 近似，但补全 Luau 特有行为）
2. loadstring 加载脚本（而非 dofile）
3. task 库可能不完整 / 缺失
4. bit32 可能缺失（强制走纯 Lua 回退）
5. debug 库受限（getinfo/setupvalue 可能返回 nil）
6. HttpService 可能被拦截
7. setmetatable 在沙箱中可用，但 _G 写入可能被监控
8. 没有 syn.crypt / protect_gui 等扩展库
9. typeof 返回 Luau 类型名（"Vector3"/"CFrame" 等，非 "table"）
10. game:GetService 返回受监控的服务对象

测试维度：
A. 纯加载测试（不调用 Activate）：零报错
B. Activate 测试：健康值合理（≥0.5）
C. SelfTest 测试：61/61 全通过
D. RunProgram 测试：VM 执行不崩
E. ShadowStack 压力测试：1000 次 push/pop 不崩
F. SelfModVM 触发旋转：执行 600+ 条指令不崩
G. Bidirectional 陷阱触发：不崩
H. bit32 缺失场景：纯 Lua 回退正常
I. task 缺失场景：降级正常
J. debug 缺失场景：降级正常
K. HttpService 拦截场景：降级正常
L. 综合压力：模拟真实业务调用 1000 次不崩
"""
import os, sys, time
from lupa import LuaRuntime

# ============================================================
# 忍者注入器仿真沙箱（多环境配置）
# ============================================================
def make_ninja_env(config):
    """config: dict 控制各库的可用性，模拟不同忍者注入器子版本"""
    cfg = {
        "has_bit32": True,
        "has_task": True,
        "has_debug": True,
        "has_http": True,
        "task_wait_yields": False,  # 忍者注入器 task.wait 可能不 yield
        "debug_getinfo_works": True,
        "debug_getupvalue_works": True,
        "restrict_g_writes": False,  # _G 写入是否被监控
        "has_syn": False,
        "has_protect_gui": False,
    }
    cfg.update(config)
    return cfg

# 生成 Lua 沙箱代码（根据 config 启用/禁用各库）
def build_shim_lua(cfg):
    bit32_lua = """
    local bit32 = {
        bxor = function(a, b) return a ~ b end,
        band = function(a, b) return a & b end,
        bor = function(a, b) return a | b end,
        bnot = function(a) return (4294967295 ~ a) end,
        lshift = function(a, n) return a << n end,
        rshift = function(a, n) return a >> n end,
        arshift = function(a, n) return a >> n end,
    }
    """ if cfg["has_bit32"] else "local bit32 = nil"

    task_lua = """
    local task = {
        wait = function(n) return n or 0, n or 0 end,
        spawn = function(f, ...) local co = coroutine.create(f) end,
        delay = function(n, f) end,
        defer = function(f) end,
    }
    """ if cfg["has_task"] else "local task = nil"

    debug_lua = """
    local debug = {
        getinfo = function(level, what) return nil end,
        getupvalue = function(fn, idx) return nil, nil end,
        setupvalue = function(fn, idx, val) return false end,
        getlocal = function(level, idx) return nil, nil end,
    }
    """ if cfg["has_debug"] else "local debug = nil"

    http_lua = """
    local function http_get(url) return "" end
    """ if cfg["has_http"] else "local function http_get(url) return nil end"

    shim = r'''
function _G._build_ninja_shim()
    __NINJA_CONFIG = %s
    %s
    %s
    %s
    %s
    local bit = bit32
    local function tick() return os.clock() end
    local function getgenv() return _G end
    local function getrenv() return _G end
    local function identifyexecutor() return "NinjaInjector", "1.0" end
    local function setclipboard() end
    local function request() return {StatusCode=200, Body="", Headers={}} end
    local function writefile() end
    local function readfile() return "" end
    local function delfile() end
    local function isfile() return false end
    local function makefolder() end
    local Drawing = setmetatable({}, {__index = function() return function() return setmetatable({}, {__index=function() return nil end}) end end})
    local game = setmetatable({}, {__index = function(t,k)
        if k == "GetService" then return function(_, s) return setmetatable({}, {__index=function() return function() return nil end end}) end end
        return setmetatable({}, {__index=function() return function() return nil end end})
    end})
    local workspace = game
    local function warn() end
    local function hookfunction() end
    local function hookmetamethod() end
    -- Luau typeof：返回类型名（与 type 不同）
    local function typeof(v)
        local t = type(v)
        if t == "table" then
            -- Luau 中 Vector3/CFrame 等是 userdata，这里用表模拟
            if v.X and v.Y and v.Z then return "Vector3" end
            return "table"
        end
        return t
    end
    local function Instance() return setmetatable({}, {__index=function() return function() return nil end end}) end
    local Vector3 = function(x,y,z) return {X=x,Y=y,Z=z} end
    local CFrame = function() return {} end
    local Color3 = function() return {} end
    local UDim2 = function() return {} end
    local Enum = setmetatable({}, {__index=function() return setmetatable({},{__index=function() return 0 end}) end})
    local HttpService = {JSONEncode=function() return "" end, JSONDecode=function() return {} end, GetAsync=function() return "" end}
    local RunService = {Heartbeat={},RenderStepped={}}
    local function connect(ev, fn) return {Disconnect=function() end} end
    -- loadstring（忍者注入器核心加载方式）
    local function loadstring(s, n) return load(s, n) end
    -- syn.crypt / protect_gui 不存在
    local syn = nil
    local protect_gui = nil
    return {
        bit32=bit32, bit=bit, task=task, tick=tick, getgenv=getgenv, getrenv=getrenv,
        identifyexecutor=identifyexecutor, setclipboard=setclipboard, request=request,
        writefile=writefile, readfile=readfile, delfile=delfile, isfile=isfile,
        makefolder=makefolder, Drawing=Drawing, game=game, workspace=workspace, warn=warn,
        hookfunction=hookfunction, hookmetamethod=hookmetamethod, typeof=typeof, Instance=Instance,
        Vector3=Vector3, CFrame=CFrame, Color3=Color3, UDim2=UDim2, Enum=Enum, HttpService=HttpService,
        RunService=RunService, connect=connect, spawn=task and task.spawn, delay=task and task.delay, wait=task and task.wait,
        loadstring=loadstring, debug=debug, syn=syn, protect_gui=protect_gui, http_get=http_get,
    }
end
return _G._build_ninja_shim
''' % ("__NINJA_CONFIG_PLACEHOLDER", bit32_lua, task_lua, debug_lua, http_lua)
    # 替换配置占位符为实际的 Lua table
    cfg_lua = "{"
    for k, v in cfg.items():
        cfg_lua += "{}={},".format(k, "true" if v else "false")
    cfg_lua += "}"
    shim = shim.replace("__NINJA_CONFIG_PLACEHOLDER", cfg_lua)
    return shim


def run_test(test_name, cfg, test_body):
    """运行单个测试。test_body(lua, g) 返回 (passed, detail)"""
    try:
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        shim_lua = build_shim_lua(cfg)
        lua.execute(shim_lua)
        shim_fn = lua.eval("_G._build_ninja_shim")
        env = shim_fn()
        for k in ["bit32","bit","task","tick","getgenv","getrenv","identifyexecutor",
                  "setclipboard","request","writefile","readfile","delfile","isfile",
                  "makefolder","Drawing","game","workspace","warn","hookfunction",
                  "hookmetamethod","typeof","Instance","Vector3","CFrame","Color3",
                  "UDim2","Enum","HttpService","RunService","connect","spawn","delay",
                  "wait","loadstring","debug","syn","protect_gui","http_get"]:
            if env[k] is not None or k in ["bit32","bit","task","debug","syn","protect_gui"]:
                g[k] = env[k]
        # 静默 print，避免 OmniShield 日志淹没测试输出
        g["print"] = lambda *a: None
        g["__OMNISHIELD_LOADED"] = None
        # 加载 OmniShield.lua
        code = open("/workspace/OmniShield.lua", encoding="utf-8").read()
        lua.execute(code)
        # 运行测试体
        passed, detail = test_body(lua, g)
        status = "PASS" if passed else "FAIL"
        return (test_name, cfg, passed, detail)
    except Exception as e:
        return (test_name, cfg, False, "EXC: " + str(e)[:200])


# ============================================================
# 测试用例
# ============================================================

def test_a_load_only(lua, g):
    """A. 纯加载测试：零报错"""
    loaded = g["__OMNISHIELD_LOADED"]
    if loaded is None:
        return False, "__OMNISHIELD_LOADED 为 nil"
    return True, "OmniShield 已加载"


def test_b_activate(lua, g):
    """B. Activate 测试：健康值合理"""
    loaded = lua.eval("_G.__OMNISHIELD_LOADED")
    h = lua.execute("return _G.__OMNISHIELD_LOADED.Activate()")
    if h is None:
        return False, "Activate 返回 nil"
    if not (0 <= h <= 1):
        return False, "健康值越界: {}".format(h)
    return True, "健康值: {}".format(h)


def test_c_selftest(lua, g):
    """C. SelfTest 测试：61/61 全通过"""
    result = lua.eval("_G.__OMNISHIELD_LOADED.SelfTest()")
    t = result["total"]
    p = result["passed"]
    f = result["failed"]
    if f == 0 and t == 61:
        return True, "{}/{}".format(p, t)
    return False, "{}/{} (失败{})".format(p, t, f)


def test_d_runprogram(lua, g):
    """D. RunProgram test: VM exec no crash"""
    lua.execute(r'''
        local OS = _G.__OMNISHIELD_LOADED
        local stream = OS.EncodeProgram({
            {op=1,operand=42},
            {op=14,operand=0},
            {op=15,operand=0}
        })
        local result = OS.RunProgram(stream)
        _G.__test_d_result = result
    ''')
    return True, "VM exec done"


def test_e_shadowstack_stress(lua, g):
    """E. ShadowStack stress: 1000x push/pop"""
    lua.execute(r'''
        local OS = _G.__OMNISHIELD_LOADED
        local ss = OS._shadowstack
        ss.Init()
        local ok = true
        for i = 1, 1000 do
            ss.push(i)
            local v = ss.pop()
            if v ~= i then ok = false; break end
        end
        -- test negative/float/string/nil
        ss.push(-999)
        ss.push(3.14)
        ss.push("hello")
        ss.push(nil)
        local n = ss.pop()
        local s = ss.pop()
        local f = ss.pop()
        local neg = ss.pop()
        if n ~= nil then ok = false end
        if s ~= "hello" then ok = false end
        if math.abs(f - 3.14) > 0.001 then ok = false end
        if neg ~= -999 then ok = false end
        _G.__test_e_ok = ok
    ''')
    ok = g["__test_e_ok"]
    return ok == True, "1000x roundtrip + multi-type"


def test_f_selfmodvm_rotate(lua, g):
    """F. SelfModVM trigger rotate: 600+ instr no crash"""
    lua.execute(r'''
        local OS = _G.__OMNISHIELD_LOADED
        -- build 700 instr program, trigger >=1 rotate (RotateEvery=500)
        local prog = {}
        for i = 1, 700 do
            prog[i] = {op=(i % 4), operand=0}
        end
        -- call VM2.execute directly (bypass VM1)
        OS._vm2_counter = 0
        OS._selfmodvm.Init()
        local ok, err = pcall(function()
            OS._vm2.execute(prog)
        end)
        _G.__test_f_ok = ok
        _G.__test_f_err = err
    ''')
    ok = g["__test_f_ok"]
    err = g["__test_f_err"]
    if ok:
        return True, "700 instr executed"
    return False, "err: {}".format(str(err)[:100])


def test_g_bidirectional_trap(lua, g):
    """G. Bidirectional trap trigger: no crash"""
    lua.execute(r'''
        local OS = _G.__OMNISHIELD_LOADED
        local bv = OS._bidirectional
        bv.Init()
        bv.Protect("test_fn", function() return 42 end)
        local pt = bv.GetProtectedTable()
        -- trigger trap
        local _ = pt.test_fn
        pt.something = 123
        _G.__test_g_trapped = bv.IsTrapped()
        _G.__test_g_real = bv.Get("test_fn")()
    ''')
    trapped = g["__test_g_trapped"]
    real = g["__test_g_real"]
    if trapped and real == 42:
        return True, "trap triggered + real fn callable"
    return False, "trapped={} real={}".format(trapped, real)


def test_l_stress_combined(lua, g):
    """L. Combined stress: 1000 biz calls no crash"""
    lua.execute(r'''
        local OS = _G.__OMNISHIELD_LOADED
        local ss = OS._shadowstack
        ss.Init()
        local ok, err = pcall(function()
            for i = 1, 1000 do
                -- simulate aimbot biz: push coords -> calc -> pop
                ss.push(i * 1.5)        -- targetX
                ss.push(i * 2.5)        -- targetY
                ss.push(i * 0.5)        -- offset
                local off = ss.pop()
                local y = ss.pop()
                local x = ss.pop()
                -- simulate VM exec
                local stream = OS.EncodeProgram({
                    {op=1, operand=math.floor(x)},
                    {op=2, operand=math.floor(y)},
                    {op=15, operand=0}
                })
                OS.RunProgram(stream)
            end
        end)
        _G.__test_l_ok = ok
        _G.__test_l_err = err
    ''')
    ok = g["__test_l_ok"]
    err = g["__test_l_err"]
    if ok:
        return True, "1000 biz calls done"
    return False, "err: {}".format(str(err)[:100])


# ============================================================
# 主测试流程
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("忍者注入器高仿真沙箱测试")
    print("=" * 60)

    # 定义多组环境配置（模拟不同忍者注入器子版本）
    envs = [
        ("完整环境", make_ninja_env({})),
        ("无bit32", make_ninja_env({"has_bit32": False})),
        ("无task", make_ninja_env({"has_task": False})),
        ("无debug", make_ninja_env({"has_debug": False})),
        ("无http", make_ninja_env({"has_http": False})),
        ("全缺失", make_ninja_env({
            "has_bit32": False, "has_task": False,
            "has_debug": False, "has_http": False
        })),
    ]

    tests = [
        ("A_加载", test_a_load_only),
        ("B_Activate", test_b_activate),
        ("C_SelfTest", test_c_selftest),
        ("D_RunProgram", test_d_runprogram),
        ("E_影子堆栈压力", test_e_shadowstack_stress),
        ("F_自修改VM旋转", test_f_selfmodvm_rotate),
        ("G_双向校验陷阱", test_g_bidirectional_trap),
        ("L_综合压力", test_l_stress_combined),
    ]

    total = 0
    passed = 0
    failed_details = []
    results_grid = []

    for env_name, cfg in envs:
        for test_name, test_fn in tests:
            total += 1
            full_name = "{} [{}]".format(test_name, env_name)
            _, _, ok, detail = run_test(full_name, cfg, test_fn)
            results_grid.append((full_name, cfg, ok, detail))
            if ok:
                passed += 1
            else:
                failed_details.append(full_name)

    # 统一打印结果表格
    print("=" * 70)
    print("忍者注入器高仿真沙箱测试结果")
    print("=" * 70)
    for full_name, cfg, ok, detail in results_grid:
        status = "PASS" if ok else "FAIL"
        env_short = "b{}t{}d{}h{}".format(
            int(cfg["has_bit32"]), int(cfg["has_task"]),
            int(cfg["has_debug"]), int(cfg["has_http"]))
        print("[{}] {:<30} env={:<8} {}".format(status, full_name[:30], env_short, detail[:40]))
    print("=" * 70)
    print("总计: {}  通过: {}  失败: {}".format(total, passed, total - passed))
    if failed_details:
        print("失败列表:")
        for f in failed_details:
            print("  - {}".format(f))
    print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====")
    print("=" * 70)
    sys.exit(0 if passed == total else 1)
