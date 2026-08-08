# -*- coding: utf-8 -*-
"""决定性对比 v2：修复 getgenv 返回可写表，加语法编译检查。"""
import sys, os, subprocess, tempfile, importlib.util
sys.path.insert(0, "/workspace/docs")

LUAU = "/tmp/luau-bin/luau"
SRC = open("/workspace/docs/radar_input.lua").read()

# 修复：getgenv 返回可写表（代理 _G 读取，写入到自身）
STUB = r'''
local _genv = setmetatable({}, {__index = function(_, k) return rawget(_G, k) end})
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
getrenv = function() return _genv end
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
getgenv = function() return _genv end
CFrame = {new = function(...) return setmetatable({}, {__index = function() return 0 end}) end}
'''

VERSIONS = [
    ("当前(我的优化版)", "/workspace/docs/obfuscator_all.py"),
    ("5f8c350(疑似能启动)", "/tmp/obf_5f8c350.py"),
    ("7664950", "/tmp/obf_7664950.py"),
    ("ba01255", "/tmp/obf_ba01255.py"),
    ("ca75b7e", "/tmp/obf_ca75b7e.py"),
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

def compile_check(code, timeout=15):
    """用 luau --compile 检查语法（不运行）。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
        f.write(code); path = f.name
    try:
        r = subprocess.run([LUAU, "--compile", path], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    finally:
        os.unlink(path)

def load_mod(path):
    spec = importlib.util.spec_from_file_location('m_' + os.path.basename(path).replace('.','_').replace('/','_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    print("=" * 70)
    print("决定性对比 v2：修复 getgenv + 语法检查 + 运行测试")
    print("=" * 70)
    for label, path in VERSIONS:
        print(f"\n>>> {label}")
        try:
            mod = load_mod(path)
        except Exception as e:
            print(f"  加载失败: {e}")
            continue
        try:
            # 兼容新旧接口
            if 'ninja_mode' in mod.obfuscate_code.__code__.co_varnames:
                obf = mod.obfuscate_code(SRC, ninja_mode=True)
            else:
                obf = mod.obfuscate_code(SRC)
        except Exception as e:
            print(f"  混淆失败: {type(e).__name__}: {e}")
            continue
        print(f"  产物: {len(obf)} 字符 ({len(obf.encode())/1024:.1f} KB)")
        # 运行测试（语法错误会在运行时暴露）
        full = STUB + "\n" + obf + "\nprint('[DONE]')\n"
        out, err, rc = run_luau(full, timeout=20)
        ok = (rc == 0 and "[DONE]" in out)
        print(f"  运行结果: {'✓ 成功启动' if ok else '✗ 启动失败'}  (rc={rc})")
        if err:
            print(f"  stderr(末尾400): {err[-400:]!r}")
        if out and not ok:
            print(f"  stdout(末尾200): {out[-200:]!r}")

if __name__ == "__main__":
    main()
