# -*- coding: utf-8 -*-
"""
大脚本 + 多种子稳定性测试。
混淆 tests/big10k.lua (~12k 行) 在 5 个种子下：
  - 混淆不报错
  - 产物能在仿真忍者注入器环境加载执行不报错
"""
import os
import sys
import time

sys.path.insert(0, "/workspace/docs")
sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import obfuscate
from _tmp_ninja_quicktest import build_shim_lua, make_envs


def run_big(seed, env_idx=0):
    t0 = time.time()
    src = open("/workspace/tests/big10k.lua", encoding="utf-8").read()
    src_len = len(src)
    try:
        result = obfuscate(src, seed=seed)
        code = result["code"]
        profile = result.get("profile", {}).get("name", "?")
        if not code or len(code) < 100:
            return False, f"obf empty/short (len={len(code)})", 0, src_len, 0

        # 仿真运行
        env_name, cfg = make_envs()[env_idx]
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
        g["print"] = lambda *a: None
        g["warn"] = lambda *a: None
        g["__OMNISHIELD_LOADED"] = None

        lua.execute(code)
        elapsed = time.time() - t0
        return True, f"profile={profile} out={len(code)}B ratio={len(code)/src_len:.1f}x", elapsed, src_len, len(code)
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e).replace("\n", " ")[:200]
        return False, msg, elapsed, src_len, 0


def main():
    print("=" * 70, flush=True)
    print("大脚本稳定性测试 (tests/big10k.lua ~12k 行)", flush=True)
    print("=" * 70, flush=True)

    total = passed = 0
    failed = []
    seeds = [12345, 99999, 42, 7, 2024]

    for seed in seeds:
        total += 1
        sys.stdout.write(f"[big seed={seed:<6}] ... ")
        sys.stdout.flush()
        ok, info, elapsed, src_len, out_len = run_big(seed, env_idx=0)
        if ok:
            passed += 1
            sys.stdout.write(f"PASS ({elapsed:.1f}s) {info}\n")
        else:
            failed.append(f"seed={seed}: {info}")
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
