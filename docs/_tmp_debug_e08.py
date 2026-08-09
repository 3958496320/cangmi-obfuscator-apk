# -*- coding: utf-8 -*-
"""调试 E08 Animal OOP 元表测试。"""
import sys
sys.path.insert(0, "/workspace/src")

from obfuscator_core import obfuscate_code
from vm_pro import vm_pro_compile, ProVMCompiler

SRC = '''
local Animal = {}
Animal.__index = Animal
function Animal.new(name)
    return setmetatable({name = name}, Animal)
end
function Animal:speak()
    return "I am " .. self.name
end
local a = Animal.new("Cat")
print(a:speak())
'''

# 混淆
code = obfuscate_code(SRC, ninja_mode=False)
print("=== 混淆产物前 80 行 ===")
for i, line in enumerate(code.split("\n")[:80], 1):
    print(f"{i:3d}| {line[:120]}")

# 执行
print("\n=== 执行 ===")
from lupa import LuaRuntime
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
out = []
g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
try:
    lua.execute(code)
    print("输出:", out)
except Exception as e:
    print("错误:", e)
