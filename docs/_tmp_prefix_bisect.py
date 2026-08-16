# -*- coding: utf-8 -*-
"""逐语句二分：完整脚本逐段累加，找到触发崩溃的最小前缀。"""
import sys
sys.path.insert(0, "/workspace/src")
sys.path.insert(0, "/workspace/docs")
from lupa import LuaRuntime
from _tmp_real_env_repro import LUA_SETUP
from obfuscator_core import obfuscate

STMTS = [
    'loadstring(game:HttpGet("https://example.com/ui.lua"))()',
    'local Players = game:GetService("Players")',
    'local player = Players.LocalPlayer',
    'local function notify(msg) print("[PI] " .. tostring(msg)) end',
    'notify("脚本已加载")',
    'for _, p in ipairs(Players:GetPlayers()) do\n    if p ~= player then\n        notify("发现其他玩家: " .. p.Name)\n    end\nend',
    'local conn',
    'conn = game:GetService("RunService").Heartbeat:Connect(function()\n    if player.Character and player.Character:FindFirstChild("Humanoid") then\n        local hum = player.Character.Humanoid\n        if hum.Health < hum.MaxHealth then\n            notify("血量不足")\n        end\n    end\n    conn:Disconnect()\nend)',
]


def run_vm(src):
    obf = obfuscate(src, seed=42)["code"]
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(LUA_SETUP)
    G = lua.globals()
    try:
        ok, info, calls = G["_run_code"](obf)
    except Exception as e:
        return False, f"PY:{str(e)[:100]}", []
    prints = []
    if calls is not None:
        p = calls["prints"]
        if p is not None:
            i = 1
            while p[i] is not None:
                prints.append(str(p[i]))
                i += 1
    return bool(ok), str(info)[:120], prints


if __name__ == "__main__":
    # 累加前缀测试
    for k in range(1, len(STMTS) + 1):
        src = "\n".join(STMTS[:k])
        ok, info, prints = run_vm(src)
        mark = "PASS" if ok else "FAIL"
        last = prints[-1][:50] if prints else "-"
        print(f"prefix[1..{k}] {mark} last_print={last} {'' if ok else info}")
