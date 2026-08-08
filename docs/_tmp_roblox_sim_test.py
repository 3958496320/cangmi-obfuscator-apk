# -*- coding: utf-8 -*-
"""模拟忍者注入器（Roblox）环境，运行混淆产物，定位崩溃点。"""
import sys, os, subprocess, tempfile
sys.path.insert(0, "/workspace/docs")
from obfuscator_all import obfuscate_code

LUAU = "/tmp/luau-bin/luau"

STUB = r'''
local _inst_meta = {__index = function() return _inst end, __tostring = function() return "Instance" end}
local _inst = setmetatable({}, _inst_meta)
game = _inst; workspace = _inst; Game = _inst; Workspace = _inst
task = setmetatable({}, {__index = function(t, k)
    if k == "wait" or k == "delay" or k == "defer" then return function() end end
    return function() end
end})
spawn = function(fn) pcall(fn) end
tick = function() return 1000000.001 end
getloadedmodules = function() return {} end
getrenv = function() return _G end
getrawmetatable = function(t) return getmetatable(t) end
hookmetamethod = function() end
getgc = function() return {} end
getconnections = function() return {} end
getupvalue = function() return nil end
setupvalue = function() end
getregistry = function() return {} end
checkcaller = function() return false end
isluau = function() return true end
isexecutor = function() return false end
identifyexecutor = function() end
getrunningscripts = function() return {} end
getcallingscript = function() return nil end
print("[STUB] ok")
'''

def run_luau(code, timeout=10):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
        f.write(code); path = f.name
    try:
        r = subprocess.run([LUAU, path], capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    finally:
        os.unlink(path)

def main():
    src = 'local x=5 print(x*2)'
    print("=== 当前 v8 ===")
    obf = obfuscate_code(src, ninja_mode=False)
    print(f"产物: {len(obf)} 字符")
    full = STUB + "\n" + obf + "\nprint('[DONE]')\n"
    out, err, rc = run_luau(full, timeout=15)
    print(f"rc={rc} stdout末尾={out[-400:]!r}")
    if err: print(f"stderr={err[-300:]!r}")
    print("崩溃" if (rc != 0 or "DONE" not in out) else "成功")

    print("\n=== 5f8c350(能启动) ===")
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', '/tmp/obf_5f8c350.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    obf2 = mod.obfuscate_code(src, ninja_mode=False)
    print(f"产物: {len(obf2)} 字符")
    full2 = STUB + "\n" + obf2 + "\nprint('[DONE]')\n"
    out2, err2, rc2 = run_luau(full2, timeout=15)
    print(f"rc={rc2} stdout末尾={out2[-400:]!r}")
    if err2: print(f"stderr={err2[-300:]!r}")
    print("崩溃" if (rc2 != 0 or "DONE" not in out2) else "成功")

if __name__ == "__main__":
    main()
