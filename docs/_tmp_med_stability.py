# -*- coding: utf-8 -*-
"""
中等脚本 + 多种子测试：覆盖真实逻辑（函数/循环/表/闭包/字符串）但执行时间可控。
混淆产物在仿真忍者注入器环境下加载执行不报错。
"""
import os
import sys
import time

sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import obfuscate
from _tmp_ninja_quicktest import build_shim_lua, make_envs


# 中等复杂度脚本：模拟真实 Roblox 脚本核心逻辑（无 Roblox API 依赖部分）
MED_SRC = r'''
local Config = {Speed = 50, Jump = 100, ESP = true}
local Players = {}
local function addPlayer(name, team)
    table.insert(Players, {Name = name, Team = team, Kills = 0})
end

addPlayer("Alice", "Red")
addPlayer("Bob", "Blue")
addPlayer("Carol", "Red")

local function getPlayer(name)
    for _, p in ipairs(Players) do
        if p.Name == name then return p end
    end
    return nil
end

local function countTeam(teamName)
    local count = 0
    for _, p in ipairs(Players) do
        if p.Team == teamName then count = count + 1 end
    end
    return count
end

-- 闭包计数器
local function makeCounter(start)
    local n = start
    return function()
        n = n + 1
        return n
    end
end

local counter = makeCounter(10)
local results = {}
for i = 1, 5 do
    table.insert(results, counter())
end

-- 字符串处理
local function buildMsg(prefix, name, val)
    return prefix .. ":" .. name .. "=" .. tostring(val)
end

local msgs = {}
for _, p in ipairs(Players) do
    msgs[p.Name] = buildMsg("INFO", p.Name, p.Kills)
end

-- 算术 + 条件
local function calc(a, b, op)
    if op == "add" then return a + b
    elseif op == "sub" then return a - b
    elseif op == "mul" then return a * b
    elseif op == "div" then
        if b == 0 then return 0 end
        return a / b
    end
    return 0
end

local sum = 0
for i = 1, 100 do
    sum = sum + calc(i, i - 1, "add")
end

-- 元表
local Vec = {}
Vec.__index = Vec
function Vec.new(x, y, z)
    return setmetatable({x = x, y = y, z = z}, Vec)
end
function Vec:len()
    return math.sqrt(self.x^2 + self.y^2 + self.z^2)
end

local v = Vec.new(3, 4, 0)

-- 输出最终结果
print("COUNT_RED:" .. countTeam("Red"))
print("COUNT_BLUE:" .. countTeam("Blue"))
print("COUNTER:" .. table.concat(results, ","))
print("SUM:" .. sum)
print("VEC_LEN:" .. v:len())
print("MSG_ALICE:" .. msgs["Alice"])
print("GET_BOB_TEAM:" .. getPlayer("Bob").Team)
'''


def run_medium(seed, env_idx=0, timeout_s=60):
    t0 = time.time()
    try:
        result = obfuscate(MED_SRC, seed=seed)
        code = result["code"]
        profile = result.get("profile", {}).get("name", "?")
        if not code or len(code) < 100:
            return False, f"obf empty/short (len={len(code)})", 0

        env_name, cfg = make_envs()[env_idx]
        outputs = []
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        lua.execute(build_shim_lua(cfg))
        env = lua.eval("_G._build_ninja_shim()")
        for k in ["bit32", "bit", "task", "tick", "getgenv", "getrenv",
                  "identifyexecutor", "setclipboard", "request", "writefile",
                  "readfile", "delfile", "isfile", "makefolder", "Drawing",
                  "game", "workspace", "warn", "hookfunction", "hookmetamethod",
                  "typeof", "Instance", "Vector3", "CFrame", "Color3", "UDim2",
                  "Enum", "HttpService", "RunService", "connect", "spawn",
                  "delay", "wait", "loadstring", "debug", "syn", "protect_gui",
                  "http_get"]:
            if env[k] is not None or k in ["bit32", "bit", "task", "debug", "syn", "protect_gui"]:
                g[k] = env[k]

        def _cap_print(*args):
            outputs.append("\t".join(str(a) for a in args))
        g["print"] = _cap_print
        g["__OMNISHIELD_LOADED"] = None

        lua.execute(code)
        elapsed = time.time() - t0

        out_str = "\n".join(outputs)
        expected = [
            "COUNT_RED:2",
            "COUNT_BLUE:1",
            "SUM:",
            "VEC_LEN:5",
            "MSG_ALICE:INFO:Alice=0",
            "GET_BOB_TEAM:Blue",
        ]
        missing = [e for e in expected if e not in out_str]
        if missing:
            return False, f"missing outputs {missing[:2]} got '{out_str[:200]}'", elapsed
        return True, f"profile={profile} out={len(code)}B {elapsed:.1f}s", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e).replace("\n", " ")[:200]
        return False, msg, elapsed


def main():
    print("=" * 70, flush=True)
    print("中等脚本多种子测试 (覆盖真实逻辑)", flush=True)
    print("=" * 70, flush=True)

    total = passed = 0
    failed = []
    seeds = [12345, 99999, 42, 7, 2024, 31337, 555, 8888]

    for seed in seeds:
        total += 1
        sys.stdout.write(f"[med seed={seed:<6}] ... ")
        sys.stdout.flush()
        ok, info, elapsed = run_medium(seed, env_idx=0)
        if ok:
            passed += 1
            sys.stdout.write(f"PASS ({elapsed:.1f}s) {info}\n")
        else:
            failed.append(f"seed={seed}: {info}")
            sys.stdout.write(f"FAIL ({elapsed:.1f}s) {info}\n")
        sys.stdout.flush()

    # 全缺失环境
    for seed in [12345, 99999]:
        total += 1
        sys.stdout.write(f"[med_missing seed={seed:<6}] ... ")
        sys.stdout.flush()
        ok, info, elapsed = run_medium(seed, env_idx=5)
        if ok:
            passed += 1
            sys.stdout.write(f"PASS ({elapsed:.1f}s) {info}\n")
        else:
            failed.append(f"missing seed={seed}: {info}")
            sys.stdout.write(f"FAIL ({elapsed:.1f}s) {info}\n")
        sys.stdout.flush()

    print("=" * 70, flush=True)
    print(f"总计: {total}  通过: {passed}  失败: {total - passed}", flush=True)
    if failed:
        print("失败列表:", flush=True)
        for f in failed:
            print(f"  - {f}", flush=True)
    print("==== ALL PASS ====" if passed == total else "==== HAS FAIL ====", flush=True)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
