# -*- coding: utf-8 -*-
"""快速诊断哪个测试卡死。"""
import os, sys, time, signal
from lupa import LuaRuntime

sys.path.insert(0, "/workspace/docs")
from _tmp_ninja_sim_test import make_ninja_env, build_shim_lua, test_a_load_only, test_b_activate, test_c_selftest, test_d_runprogram, test_e_shadowstack_stress, test_f_selfmodvm_rotate, test_g_bidirectional_trap, test_l_stress_combined

cfg = make_ninja_env({})  # 完整环境
tests = [
    ("A", test_a_load_only),
    ("B", test_b_activate),
    ("C", test_c_selftest),
    ("D", test_d_runprogram),
    ("E", test_e_shadowstack_stress),
    ("F", test_f_selfmodvm_rotate),
    ("G", test_g_bidirectional_trap),
    ("L", test_l_stress_combined),
]

for name, fn in tests:
    print(">>> testing {} ...".format(name), flush=True)
    t0 = time.time()
    try:
        # 用线程+超时
        import threading
        result = [None]
        def runner():
            result[0] = (name, cfg, fn.__doc__ or "", "running")
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
                g["print"] = lambda *a: None
                g["__OMNISHIELD_LOADED"] = None
                code = open("/workspace/OmniShield.lua", encoding="utf-8").read()
                lua.execute(code)
                passed, detail = fn(lua, g)
                result[0] = (name, cfg, passed, detail)
            except Exception as e:
                result[0] = (name, cfg, False, "EXC: " + str(e)[:200])
        t = threading.Thread(target=runner, daemon=True)
        t.start()
        t.join(timeout=15)  # 每个测试 15 秒超时
        elapsed = time.time() - t0
        if t.is_alive():
            print("    [TIMEOUT] {} 卡死 (>{}s)".format(name, 15), flush=True)
            # 无法 kill 线程，直接退出
            os._exit(1)
        else:
            _, _, ok, detail = result[0]
            status = "PASS" if ok else "FAIL"
            print("    [{}] {} ({:.2f}s) {}".format(status, name, elapsed, detail[:60]), flush=True)
    except Exception as e:
        print("    [ERR] {} {}".format(name, str(e)[:100]), flush=True)

print("=== DONE ===", flush=True)
