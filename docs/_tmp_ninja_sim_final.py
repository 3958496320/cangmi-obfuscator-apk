# -*- coding: utf-8 -*-
"""
忍者注入器高仿真测试：混淆产物在 LuaJIT (lupa) 下运行，验证不报错 + 输出正确。
模拟 6 种 Ninja Injector 环境配置（bit32/task/debug/http 有无）。
"""
import os
import sys
import time

sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import obfuscate
from _tmp_ninja_quicktest import build_shim_lua, make_envs


# (源码, 期望输出包含的子串)
SAMPLES = [
    ('print("HELLO_NINJA")', "HELLO_NINJA"),
    ('print(1 + 2 * 3)', "7"),
    ('print("a" .. "b" .. "c")', "abc"),
    ('local function f(x) return x * x end print(f(9))', "81"),
    ('local t = {10, 20, 30} local s = 0 for _, v in ipairs(t) do s = s + v end print(s)', "60"),
    ('local function c() local n = 0 return function() n = n + 1 return n end end local f = c() print(f(), f(), f())', "1\t2\t3"),
    ('local function fact(n) if n <= 1 then return 1 end return n * fact(n-1) end print(fact(5))', "120"),
    ('local i = 1 local s = 0 while i <= 10 do s = s + i i = i + 1 end print(s)', "55"),
    ('print(string.upper("hello"))', "HELLO"),
    ('print(math.floor(3.7))', "3"),
    ('local function m() return 1, 2, 3 end local a, b, c = m() print(a + b + c)', "6"),
    ('local function g(x) if x > 0 then return "POS" elseif x < 0 then return "NEG" else return "ZERO" end end print(g(5), g(-1), g(0))', "POS\tNEG\tZERO"),
    ('local t = setmetatable({}, {__index = function(_, k) return "KEY_" .. k end}) print(t.foo)', "KEY_foo"),
    ('local t = {} table.insert(t, "a") table.insert(t, "b") print(#t, t[1] .. t[2])', "2\tab"),
    ('print((2 + 3) * 4 - 10 / 2)', "15"),
]


def run_one(env_name, cfg, src, expected, seed):
    """混淆 + 在仿真环境运行，捕获 print 输出"""
    t0 = time.time()
    try:
        # 1. 混淆
        result = obfuscate(src, seed=seed)
        code = result["code"]
        if not code or len(code) < 10:
            return False, "obf empty", 0

        # 2. 仿真运行
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
        # 捕获 print
        def _cap_print(*args):
            outputs.append("\t".join(str(a) for a in args))
        g["print"] = _cap_print
        g["__OMNISHIELD_LOADED"] = None

        # 3. 执行混淆产物
        lua.execute(code)
        elapsed = time.time() - t0

        out_str = "\n".join(outputs)
        if expected in out_str:
            return True, out_str[:80], elapsed
        else:
            return False, f"expected '{expected}' got '{out_str[:60]}'", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e).replace("\n", " ")[:150]
        return False, msg, elapsed


def main():
    print("=" * 70, flush=True)
    print("忍者注入器高仿真测试：混淆产物执行验证", flush=True)
    print("=" * 70, flush=True)

    total = passed = 0
    failed = []
    envs = make_envs()

    # 对每个样本在「完整环境」下跑 3 个种子
    seeds = [12345, 99999, 42]
    for idx, (src, expected) in enumerate(SAMPLES):
        for seed in seeds:
            env_name, cfg = envs[0]  # 完整环境
            total += 1
            label = f"S{idx+1:02d}_seed{seed}"
            sys.stdout.write(f"[{label:>20}] ... ")
            sys.stdout.flush()
            ok, info, elapsed = run_one(env_name, cfg, src, expected, seed)
            if ok:
                passed += 1
                sys.stdout.write(f"PASS ({elapsed:.2f}s)\n")
            else:
                failed.append(f"{label}: {info}")
                sys.stdout.write(f"FAIL ({elapsed:.2f}s) {info}\n")
            sys.stdout.flush()

    # 完整样本在「全缺失环境」下跑 1 个种子
    for idx, (src, expected) in enumerate(SAMPLES):
        env_name, cfg = envs[5]  # 全缺失环境
        seed = 12345
        total += 1
        label = f"S{idx+1:02d}_missing_seed{seed}"
        sys.stdout.write(f"[{label:>24}] ... ")
        sys.stdout.flush()
        ok, info, elapsed = run_one(env_name, cfg, src, expected, seed)
        if ok:
            passed += 1
            sys.stdout.write(f"PASS ({elapsed:.2f}s)\n")
        else:
            failed.append(f"{label}: {info}")
            sys.stdout.write(f"FAIL ({elapsed:.2f}s) {info}\n")
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
