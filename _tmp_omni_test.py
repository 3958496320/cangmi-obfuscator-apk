import lupa
from lupa import LuaRuntime

lua = LuaRuntime(unpack_returned_tuples=True)

# Inject Roblox-like shim globals BEFORE loading the module
g = lua.globals()

# game service stub
setup_shim = r"""
-- Roblox-like shim for testing (NOT part of OmniShield)
_G.game = setmetatable({}, {
    __index = function(t, k)
        if k == "GetService" then
            return function(name)
                return setmetatable({}, {
                    __index = function(_, key)
                        if key == "GetMouseLocation" then
                            return function() return {X = 100, Y = 200} end
                        end
                        if key == "GetRealPhysicsFPS" then
                            return function() return 60 end
                        end
                        if key == "GetAsync" then
                            return function() return "" end
                        end
                        return nil
                    end
                })
            end
        end
        return nil
    end
})
_G.HttpService = setmetatable({}, {
    __index = function(_, k)
        if k == "GetAsync" then return function() return "" end end
        return nil
    end
})
_G.tick = function() return os.clock() end
_G.wait = function(n)
    -- yield only when inside a coroutine; in main thread just return (simulates non-blocking)
    if coroutine.isyieldable() then coroutine.yield(n or 0) end
    return n or 0, n or 0
end
_G.spawn = function(fn, ...)
    local co = coroutine.create(fn)
    local ok, err = coroutine.resume(co, ...)
    if not ok then _G.warn("[shim] spawn err:", tostring(err)) end
    return co
end
_G.delay = function(n, fn, ...)
    local co = coroutine.create(fn)
    coroutine.resume(co, ...)
    return co
end
_G.checkcaller = function() return false end
-- do NOT define bit32 / task / request / httpget to exercise fallback paths
_G.warn = function(...) end
_G.print = function(...) end
_G.typeof = function(v) return type(v) end
return true
"""
lua.execute(setup_shim)

with open('OmniShield.lua', 'r', encoding='utf-8') as f:
    src = f.read()

# 1) Load the module (this exercises top-level code = "startup")
print("=== Loading module (startup) ===")
load_fn = lua.eval('function(s) return load(s, "OmniShield") end')
chunk = load_fn(src)
if chunk is None:
    print("LOAD FAILED")
    raise SystemExit(1)
print("load() returned a function: OK")

# Run the chunk to execute module top-level
try:
    OmniShield = chunk()
    print("Module top-level executed: OK, returned:", type(OmniShield))
except lupa.LuaError as e:
    print("STARTUP ERROR:", e)
    raise SystemExit(1)

# 2) Call Activate()
print("\n=== Activate() ===")
try:
    health = OmniShield.Activate()
    print("Activate returned health =", health)
except lupa.LuaError as e:
    print("ACTIVATE ERROR:", e)
    raise SystemExit(1)

# 3) Run SelfTest()
print("\n=== SelfTest() ===")
try:
    res = OmniShield.SelfTest(OmniShield)
    print("SelfTest total:", res.total, "passed:", res.passed, "failed:", res.failed)
    # print failures
    results = res.results
    for i in range(len(results)):
        r = results[i]
        if str(r.status) == "FAIL":
            print("  FAIL:", r.name, "|", r.err)
except lupa.LuaError as e:
    print("SELFTEST ERROR:", e)
    raise SystemExit(1)

print("\n=== DONE ===")
