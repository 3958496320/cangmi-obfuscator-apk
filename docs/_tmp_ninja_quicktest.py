# -*- coding: utf-8 -*-
"""
忍者注入器最小化仿真加载测试。
逐环境逐用例测试，立即输出结果（flush=True），定位崩溃点。
"""
import sys, time
from lupa import LuaRuntime


def build_shim_lua(cfg):
    bit32_lua = r'''
    local bit32 = {
        bxor = function(a, b) return a ~ b end,
        band = function(a, b) return a & b end,
        bor = function(a, b) return a | b end,
        bnot = function(a) return (4294967295 ~ a) end,
        lshift = function(a, n) return a << n end,
        rshift = function(a, n) return a >> n end,
        arshift = function(a, n) return a >> n end,
    }
    ''' if cfg["has_bit32"] else "local bit32 = nil"

    task_lua = r'''
    local task = {
        wait = function(n) return n or 0, n or 0 end,
        spawn = function(f, ...) local co = coroutine.create(f) end,
        delay = function(n, f) end,
        defer = function(f) end,
    }
    ''' if cfg["has_task"] else "local task = nil"

    debug_lua = r'''
    local debug = {
        getinfo = function(level, what) return nil end,
        getupvalue = function(fn, idx) return nil, nil end,
        setupvalue = function(fn, idx, val) return false end,
        getlocal = function(level, idx) return nil, nil end,
    }
    ''' if cfg["has_debug"] else "local debug = nil"

    http_lua = r'''
    local function http_get(url) return "" end
    ''' if cfg["has_http"] else "local function http_get(url) return nil end"

    cfg_lua = "{"
    for k, v in cfg.items():
        cfg_lua += "{}={},".format(k, "true" if v else "false")
    cfg_lua += "}"

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
    -- Universal 链式伪对象：任何方法调用/字段访问/算术都返回自身，支持无限链式
    -- 用于模拟 Roblox game/Instance/Drawing 等，使 Roblox 脚本在仿真环境不报错
    local _U_MT
    _U_MT = {
        __index = function(t, k) return t end,
        __call = function(t, ...) return t end,
        __newindex = function(t, k, v) end,
        __add = function(t, o) return t end,
        __sub = function(t, o) return t end,
        __mul = function(t, o) return t end,
        __div = function(t, o) return t end,
        __mod = function(t, o) return t end,
        __pow = function(t, o) return t end,
        __unm = function(t) return t end,
        __concat = function(t, o) return tostring(t) end,
        __len = function(t) return 0 end,
        __tostring = function(t) return "U" end,
    }
    local function _U() return setmetatable({}, _U_MT) end
    local Drawing = _U()
    local game = _U()
    local workspace = game
    local function warn() end
    local function hookfunction() end
    local function hookmetamethod() end
    local function typeof(v)
        local t = type(v)
        if t == "table" then
            if v.X and v.Y and v.Z then return "Vector3" end
            return "table"
        end
        return t
    end
    local function Instance() return _U() end
    local Vector3 = _U()
    local CFrame = _U()
    local Color3 = _U()
    local UDim2 = _U()
    local Enum = _U()
    local HttpService = _U()
    local RunService = _U()
    local function connect(ev, fn) return {Disconnect=function() end} end
    local function loadstring(s, n) return load(s, n) end
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
''' % (cfg_lua, bit32_lua, task_lua, debug_lua, http_lua)
    return shim


def run_one(env_name, cfg, step_name, step_lua):
    """跑单步：加载 OmniShield → 执行 step_lua → 报告"""
    sys.stdout.write("[{:>10}] {:<25} ... ".format(env_name, step_name))
    sys.stdout.flush()
    t0 = time.time()
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
        g["print"] = lambda *a: None
        g["__OMNISHIELD_LOADED"] = None
        code = open("/workspace/OmniShield.lua", encoding="utf-8").read()
        lua.execute(code)
        if step_lua:
            lua.execute(step_lua)
        elapsed = time.time() - t0
        sys.stdout.write("PASS ({:.2f}s)\n".format(elapsed))
        sys.stdout.flush()
        return True
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e).replace("\n", " ")[:120]
        sys.stdout.write("FAIL ({:.2f}s) {}\n".format(elapsed, msg))
        sys.stdout.flush()
        return False


def make_envs():
    base = {
        "has_bit32": True, "has_task": True, "has_debug": True, "has_http": True,
        "task_wait_yields": False, "debug_getinfo_works": True,
        "debug_getupvalue_works": True, "restrict_g_writes": False,
        "has_syn": False, "has_protect_gui": False,
    }
    return [
        ("完整环境", dict(base)),
        ("无bit32", dict(base, has_bit32=False)),
        ("无task", dict(base, has_task=False)),
        ("无debug", dict(base, has_debug=False)),
        ("无http", dict(base, has_http=False)),
        ("全缺失", dict(base, has_bit32=False, has_task=False, has_debug=False, has_http=False)),
    ]


STEPS = [
    ("1_仅加载", None),
    ("2_Activate", r'''
        local h = _G.__OMNISHIELD_LOADED.Activate()
        _G.__h = h
    '''),
    ("3_SelfTest", r'''
        local r = _G.__OMNISHIELD_LOADED.SelfTest()
        _G.__st_total = r.total
        _G.__st_passed = r.passed
        _G.__st_failed = r.failed
    '''),
    ("4_RunProgram", r'''
        local OS = _G.__OMNISHIELD_LOADED
        local s = OS.EncodeProgram({{op=1,operand=42},{op=14,operand=0},{op=15,operand=0}})
        OS.RunProgram(s)
    '''),
    ("5_ShadowStack压测", r'''
        local OS = _G.__OMNISHIELD_LOADED
        local ss = OS._shadowstack
        ss.Init()
        for i = 1, 1000 do
            ss.push(i)
            local v = ss.pop()
            if v ~= i then error("shadowstack mismatch at "..i) end
        end
    '''),
    ("6_SelfModVM旋转", r'''
        local OS = _G.__OMNISHIELD_LOADED
        local prog = {}
        for i = 1, 700 do prog[i] = {op=(i % 4), operand=0} end
        OS._vm2_counter = 0
        OS._selfmodvm.Init()
        local ok, err = pcall(function() OS._vm2.execute(prog) end)
        if not ok then error("vm2 err: "..tostring(err)) end
    '''),
    ("7_Bidirectional陷阱", r'''
        local OS = _G.__OMNISHIELD_LOADED
        local bv = OS._bidirectional
        bv.Init()
        bv.Protect("test_fn", function() return 42 end)
        local pt = bv.GetProtectedTable()
        local _ = pt.test_fn
        pt.something = 123
        if not bv.IsTrapped() then error("trap not triggered") end
        if bv.Get("test_fn")() ~= 42 then error("real fn broken") end
    '''),
    ("8_综合压测1000", r'''
        local OS = _G.__OMNISHIELD_LOADED
        local ss = OS._shadowstack
        ss.Init()
        for i = 1, 1000 do
            ss.push(i * 1.5)
            ss.push(i * 2.5)
            ss.push(i * 0.5)
            local off = ss.pop()
            local y = ss.pop()
            local x = ss.pop()
            local s = OS.EncodeProgram({
                {op=1, operand=math.floor(x)},
                {op=2, operand=math.floor(y)},
                {op=15, operand=0}
            })
            OS.RunProgram(s)
        end
    '''),
]


if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("忍者注入器高仿真沙箱测试（8 步 × 6 环境 = 48 用例）", flush=True)
    print("=" * 70, flush=True)

    total = passed = 0
    failed = []
    for env_name, cfg in make_envs():
        for step_name, step_lua in STEPS:
            total += 1
            ok = run_one(env_name, cfg, step_name, step_lua)
            if ok:
                passed += 1
            else:
                failed.append("{} / {}".format(env_name, step_name))

    print("=" * 70, flush=True)
    print("总计: {}  通过: {}  失败: {}".format(total, passed, total - passed), flush=True)
    if failed:
        print("失败列表:", flush=True)
        for f in failed:
            print("  - {}".format(f), flush=True)
    print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====", flush=True)
    sys.exit(0 if passed == total else 1)
