# -*- coding: utf-8 -*-
"""运行打标 payload#2，找出哪个检查触发了 corrupt。"""
import sys
sys.path.insert(0, "/workspace/docs")
from _tmp_real_env_repro import LUA_SETUP, run_in_executor_env  # noqa
from lupa import LuaRuntime

code = open("/workspace/tests/_dump_payload_2_tagged.lua", encoding="utf-8").read()

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(LUA_SETUP)
G = lua.globals()
# 注入 _ENV_PRINT（tagged 代码引用它）
lines = []
G["_ENV_PRINT"] = lambda msg: (lines.append(str(msg)), print("[tag]", msg))[1]
ok, info, calls = G["_run_code"](code)
print("ok=", bool(ok), "info=", str(info)[:200])
prints = calls["prints"]
if prints is not None:
    i = 1
    while prints[i] is not None:
        print("print>", str(prints[i])[:120])
        i += 1
print("tags:", lines if lines else "(无标记触发)")
