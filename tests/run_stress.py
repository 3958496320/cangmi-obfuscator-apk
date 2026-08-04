# -*- coding: utf-8 -*-
"""
压力测试回归：对 stress_input.lua 用多组 seed 混淆，再用 lua5.3 执行，
校验输出与原始脚本完全一致。

用法：
    python3 tests/run_stress.py [--lua lua5.3] [--seeds 50] [--seed N]
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..", "src")
sys.path.insert(0, _SRC)

from obfuscator_core import obfuscate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lua", default="lua")
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0,
                    help="only run this seed (1-based); 0 = all")
    ap.add_argument("--keep", action="store_true",
                    help="keep obfuscated output files for inspection")
    args = ap.parse_args()

    sample = os.path.join(_HERE, "stress_input.lua")
    with open(sample, "r", encoding="utf-8") as f:
        src = f.read()

    # 原始脚本基线
    base = subprocess.run([args.lua, sample], capture_output=True, text=True)
    if base.returncode != 0:
        print(f"[fatal] 原始脚本执行失败: {base.stderr}")
        return 99
    baseline = base.stdout
    print(f"[baseline] {repr(baseline)}")

    seeds = [args.seed] if args.seed > 0 else range(1, args.seeds + 1)

    npass = 0
    fails = []
    for seed in seeds:
        try:
            res = obfuscate(src=src, seed=seed)
        except Exception as e:
            fails.append((seed, "OBFUSCATE-EXC", repr(e)))
            continue
        code = res["code"]
        prof = res["profile"].get("name")
        tmp = f"/tmp/_stress_{seed}.lua"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            run = subprocess.run([args.lua, tmp], capture_output=True,
                                 text=True, timeout=30)
        except subprocess.TimeoutExpired:
            fails.append((seed, f"TIMEOUT prof={prof}", ">30s"))
            if not args.keep:
                os.remove(tmp)
            continue
        if run.returncode != 0:
            err = run.stderr.strip().splitlines()
            msg = err[-1] if err else "(no stderr)"
            fails.append((seed, f"RUN-ERR rc={run.returncode} prof={prof}",
                          msg))
            if not args.keep:
                os.remove(tmp)
            continue
        if run.stdout == baseline:
            npass += 1
            if not args.keep:
                os.remove(tmp)
        else:
            fails.append((seed, f"OUTPUT-MISMATCH prof={prof}",
                          f"got={run.stdout!r}"))
            if not args.keep:
                os.remove(tmp)

    total = len(seeds)
    print(f"\n=== {npass}/{total} PASS ===")
    for seed, kind, detail in fails:
        print(f"  [seed={seed}] {kind}")
        print(f"      {detail}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
