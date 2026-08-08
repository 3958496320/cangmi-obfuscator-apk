# -*- coding: utf-8 -*-
"""决定性对比测试：用真实雷达脚本，对比当前版本与4个历史版本，
确认哪个版本产物能在官方 Luau CLI 下成功运行到结尾。"""
import sys, os, subprocess, tempfile, importlib.util
sys.path.insert(0, "/workspace/docs")

LUAU = "/tmp/luau-bin/luau"
SRC = open("/workspace/docs/radar_input.lua").read()

# Roblox 环境 stub（模拟忍者注入器运行时）
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
getgenv = function() return _G end
CFrame = {new = function(...) return setmetatable({}, {__index = function() return 0 end}) end}
'''

VERSIONS = [
    ("当前(我的优化版)", "/workspace/docs/obfuscator_all.py"),
    ("ca75b7e", "/tmp/obf_ca75b7e.py"),
    ("5f8c350(疑似能启动)", "/tmp/obf_5f8c350.py"),
    ("7664950", "/tmp/obf_7664950.py"),
    ("ba01255", "/tmp/obf_ba01255.py"),
]

def run_luau(code, timeout=20):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
        f.write(code); path = f.name
    try:
        r = subprocess.run([LUAU, path], capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    finally:
        os.unlink(path)

def load_mod(path):
    spec = importlib.util.spec_from_file_location('m_' + os.path.basename(path).replace('.','_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    print("=" * 70)
    print("决定性对比：真实雷达脚本 × 5 个版本 × 官方 Luau CLI")
    print("=" * 70)
    for label, path in VERSIONS:
        print(f"\n>>> {label}  ({path})")
        try:
            mod = load_mod(path)
        except Exception as e:
            print(f"  加载失败: {e}")
            continue
        # 生成产物（ninja_mode=True，模拟用户实际使用）
        try:
            obf = mod.obfuscate_code(SRC, ninja_mode=True)
        except Exception as e:
            print(f"  混淆失败: {e}")
            continue
        print(f"  产物大小: {len(obf)} 字符 ({len(obf.encode())/1024:.1f} KB)")
        full = STUB + "\n" + obf + "\nprint('[DONE]')\n"
        out, err, rc = run_luau(full, timeout=20)
        ok = (rc == 0 and "[DONE]" in out)
        print(f"  运行结果: {'✓ 成功启动' if ok else '✗ 启动失败'}  (rc={rc})")
        if err:
            # 只打印错误最后 500 字符
            print(f"  stderr(末尾500): {err[-500:]!r}")
        if out:
            print(f"  stdout(末尾200): {out[-200:]!r}")

if __name__ == "__main__":
    main()
