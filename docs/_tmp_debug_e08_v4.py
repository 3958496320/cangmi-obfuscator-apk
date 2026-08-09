# -*- coding: utf-8 -*-
"""更细粒度隔离 E08 bug。"""
import sys
sys.path.insert(0, "/workspace/src")

from obfuscator_core import obfuscate_code
from lupa import LuaRuntime

def run(src, label):
    print(f"\n=== {label} ===")
    try:
        code = obfuscate_code(src, ninja_mode=False)
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        out = []
        g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
        lua.execute(code)
        print(f"输出: {out}")
    except Exception as e:
        print(f"错误: {str(e)[:150]}")

# A. 闭包引用外部 local（无表）
run('''
local x = 10
local function getx() return x end
print(getx())
''', "A: 闭包引用 local x")

# B. 闭包引用外部 local 表
run('''
local t = {val = 42}
local function gett() return t.val end
print(gett())
''', "B: 闭包引用 local 表 t")

# C. 闭包引用外部 local 表 + 修改
run('''
local t = {}
local function setfield() t.field = "hello" end
setfield()
print(t.field)
''', "C: 闭包给 local 表设字段")

# D. setmetatable 在函数内引用 local 表
run('''
local mt = {}
local function make() return setmetatable({}, mt) end
local a = make()
print(type(a))
''', "D: setmetatable 在函数内引用 local mt")

# E. mt.__index = mt 然后 setmetatable
run('''
local mt = {}
mt.__index = mt
local function make() return setmetatable({}, mt) end
local a = make()
print(type(a))
''', "E: mt.__index = mt + 函数内引用")

# F. function mt.new()
run('''
local mt = {}
mt.__index = mt
function mt.new() return setmetatable({}, mt) end
local a = mt.new()
print(type(a))
''', "F: function mt.new() + 函数内引用 mt")
