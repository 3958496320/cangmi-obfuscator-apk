# -*- coding: utf-8 -*-
"""
真实注入器高保真仿真：复现"混淆后无反应"。
  - 提供执行器专属全局（hookfunction/getgenv/identifyexecutor 等，真实注入器都有）
  - game:HttpGet 返回真实可执行 chunk
  - Connect 回调真实触发
  - 检查"静默失败"：不抛错但什么都没发生 == 用户看到的"无反应"
"""
import sys
sys.path.insert(0, "/workspace/src")
from lupa import LuaRuntime

LUA_SETUP = r'''
function _loadstring_or_load(code, name)
    local ls = rawget(_G, "loadstring")
    if ls then return ls(code, name) end
    return load(code, name)
end

-- 真实 Luau 执行器均有 loadstring；补齐以贴近真实环境
-- 同时转储运行时传给 loadstring/load 的所有载荷用于分析
_DUMPS = {}
_G.loadstring = function(code, name)
    _DUMPS[#_DUMPS+1] = tostring(code)
    return load(code, name)
end

-- 构建仿真执行器环境到真实 _G，返回记录表
function _build_env()
    local calls = { http = {}, connects = 0, prints = {} }

    _G.getgenv = function() return _G end
    _G.getrenv = function() return _G end
    _G.identifyexecutor = function() return "NinjaInjector" end
    _G.hookfunction = function() return function() end end
    _G.hookmetamethod = function() return function() end end
    _G.checkcaller = function() return true end
    _G.setclipboard = function(_) end
    _G.request = function(_) return {StatusCode=200, Body=""} end
    _G.isfile = function(_) return false end
    _G.writefile = function(_,__) end
    _G.readfile = function(_) return "" end
    _G.makefolder = function(_) end
    _G.queue_on_teleport = function(_) end

    _G.task = { wait = function(_) return 0 end, spawn = function(f) f() end,
                delay = function(_, f) f() end, defer = function(f) f() end }
    _G.wait = function(_) return 0 end
    _G.spawn = function(f) f() end
    _G.delay = function(_, f) f() end
    _G.tick = function() return os.clock() end
    _G.time = function() return os.clock() end
    _G.elapsedTime = function() return os.clock() end

    local gameobj = {}
    local runsvc = {}
    local players = {}
    gameobj.HttpGet = function(self, url)
        table.insert(calls.http, url)
        return 'PiUILoaded = true print("[UI] loaded")'
    end
    local services = { Players = players, RunService = runsvc,
                       HttpService = { RequestInternal = function() end } }
    gameobj.GetService = function(self, name) return services[name] or {} end
    gameobj.Players = players
    gameobj.Workspace = {}
    gameobj.Loaded = true

    players.LocalPlayer = { Name = "Me", UserId = 1,
        Character = { FindFirstChild = function(_, n)
            if n == "Humanoid" then return { Health = 50, MaxHealth = 100 } end
            return nil
        end } }
    players.GetPlayers = function(_)
        return { players.LocalPlayer,
                 { Name = "Other1", Character = nil },
                 { Name = "Other2", Character = nil } }
    end

    local function mkconn()
        local c = {}
        function c:Disconnect() end
        return c
    end
    runsvc.Heartbeat = { Connect = function(_, fn)
        calls.connects = calls.connects + 1
        local ok, err = pcall(fn)
        if not ok then calls.prints[#calls.prints+1] = "CB_ERR:" .. tostring(err) end
        return mkconn()
    end }

    _G.game = gameobj
    _G.workspace = gameobj.Workspace
    _G.print = function(...)
        local parts = {}
        for i = 1, select("#", ...) do parts[#parts+1] = tostring(select(i, ...)) end
        calls.prints[#calls.prints+1] = table.concat(parts, "\t")
    end
    _G.warn = _G.print
    return calls
end

-- 在仿真环境执行 code，返回 (执行OK, 信息, calls)
function _run_code(code)
    local calls = _build_env()
    local fn, err = _loadstring_or_load(code, "obf")
    if not fn then
        return false, "LOAD_ERR:" .. tostring(err), calls
    end
    local ok, e = pcall(fn)
    if not ok then
        return false, "RUN_ERR:" .. tostring(e), calls
    end
    return true, "OK", calls
end
'''


def run_in_executor_env(code, label):
    diag = {"label": label, "ok": False, "info": "", "http_called": 0,
            "prints": [], "connects": 0, "exception": None}
    try:
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_SETUP)
        G = lua.globals()
        ok, info, calls = G["_run_code"](code)
        diag["ok"] = bool(ok)
        diag["info"] = str(info)
        diag["connects"] = int(calls["connects"] or 0)
        http = calls["http"]
        if http is not None:
            i = 1
            while http[i] is not None:
                diag["http_called"] += 1
                i += 1
        prints = calls["prints"]
        if prints is not None:
            i = 1
            while prints[i] is not None:
                diag["prints"].append(str(prints[i]))
                i += 1
    except Exception as e:
        diag["exception"] = str(e).replace("\n", " ")[:300]
    return diag


def report(diag):
    print(f"--- {diag['label']} ---")
    if diag["exception"]:
        print(f"  PYTHON异常: {diag['exception']}")
        return
    print(f"  执行: ok={diag['ok']} info={diag['info'][:150]}")
    print(f"  HttpGet调用: {diag['http_called']}  Connect: {diag['connects']}")
    shown = 0
    for p in diag["prints"]:
        if p.startswith("RUN_ERR") or p.startswith("CB_ERR"):
            print(f"  !! {p[:180]}")
        elif shown < 8:
            print(f"  print> {p[:120]}")
            shown += 1
    if not diag["prints"]:
        print("  print> (无任何输出)")


if __name__ == "__main__":
    src = open("/workspace/tests/pi_loadstring_input.lua", encoding="utf-8").read()
    report(run_in_executor_env(src, "原始脚本(基线)"))
    from obfuscator_core import obfuscate
    obf = obfuscate(src, seed=42)["code"]
    open("/workspace/tests/pi_obf_vmpro.lua", "w", encoding="utf-8").write(obf)
    report(run_in_executor_env(obf, "混淆脚本(vm_pro默认)"))
    # 转储运行时 loadstring 载荷
    import json
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(LUA_SETUP)
    G = lua.globals()
    ok, info, calls = G["_run_code"](obf)
    dumps = G["_DUMPS"]
    if dumps is not None:
        i = 1
        while dumps[i] is not None:
            payload = str(dumps[i])
            path = f"/workspace/tests/_dump_payload_{i}.lua"
            open(path, "w", encoding="utf-8").write(payload)
            print(f"[dump] payload#{i} -> {path} ({len(payload)} chars, head={payload[:60]!r})")
            i += 1
