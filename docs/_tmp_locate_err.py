# -*- coding: utf-8 -*-
"""精确定位 readonly 错误的产物行。"""
import sys, os, subprocess, tempfile
sys.path.insert(0, "/workspace/docs")
from obfuscator_all import obfuscate_code

LUAU = "/tmp/luau-bin/luau"
SRC = open("/workspace/docs/radar_input.lua").read()

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

obf = obfuscate_code(SRC, ninja_mode=True)
stub_lines = STUB.count("\n") + 1
full = STUB + "\n" + obf + "\nprint('[DONE]')\n"

with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
    f.write(full); path = f.name
r = subprocess.run([LUAU, path], capture_output=True, text=True, timeout=20)
os.unlink(path)
print("rc:", r.returncode)
print("stdout末尾:", r.stdout[-200:])
print("stderr:", r.stderr)

# 解析错误行号
import re
m = re.search(r'\.luau:(\d+):', r.stderr)
if m:
    luau_line = int(m.group(1))
    obf_line = luau_line - stub_lines
    print(f"\nluau报错行: {luau_line}, stub行数: {stub_lines}, 产物内行: {obf_line}")
    obf_lines = obf.split("\n")
    if 1 <= obf_line <= len(obf_lines):
        print(f"\n=== 产物第 {obf_line} 行附近（出错行）===")
        for i in range(max(0, obf_line-8), min(len(obf_lines), obf_line+5)):
            mark = " >>>" if i == obf_line-1 else "    "
            print(f"{mark}{i+1}: {obf_lines[i][:200]}")
