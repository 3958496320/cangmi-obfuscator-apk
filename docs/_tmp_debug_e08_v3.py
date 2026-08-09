# -*- coding: utf-8 -*-
"""逐步测试 E08 的各个部分。"""
import sys
sys.path.insert(0, "/workspace/src")

from obfuscator_core import obfuscate_code
from lupa import LuaRuntime

def run(src, label):
    print(f"\n=== {label} ===")
    print(src.strip())
    try:
        code = obfuscate_code(src, ninja_mode=False)
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        out = []
        g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
        lua.execute(code)
        print(f"输出: {out}")
    except Exception as e:
        print(f"错误: {e}")

# 1. 简单表方法定义
run('''
local t = {}
function t.foo() return 42 end
print(t.foo())
''', "T1: 表方法定义 t.foo()")

# 2. 表方法 + self
run('''
local t = {}
function t:say() return "hi" end
print(t:say())
''', "T2: 表方法定义 t:say()")

# 3. setmetatable 基础
run('''
local mt = {__index = {hello = function() return "world" end}}
local t = setmetatable({}, mt)
print(t.hello())
''', "T3: setmetatable 基础")

# 4. setmetatable 返回值
run('''
local mt = {}
function mt.__index(self, k) return "default" end
local t = setmetatable({}, mt)
print(t.missing)
''', "T4: setmetatable __index 函数")

# 5. 类似 E08 但更简单
run('''
local Animal = {}
Animal.__index = Animal
function Animal.new()
    return setmetatable({}, Animal)
end
local a = Animal.new()
print(type(a))
''', "T5: 简化 E08 (无 speak)")

# 6. 加 speak
run('''
local Animal = {}
Animal.__index = Animal
function Animal.new()
    return setmetatable({}, Animal)
end
function Animal:speak()
    return "I am animal"
end
local a = Animal.new()
print(a:speak())
''', "T6: 加 speak 方法")
