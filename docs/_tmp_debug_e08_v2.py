# -*- coding: utf-8 -*-
"""直接测试 vm_pro_compile，跳过外层 Dual-VM 包装。"""
import sys
sys.path.insert(0, "/workspace/src")

from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile, ProVMCompiler
import random

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

# 解析 AST
chunk = parse_source(SRC)
print("AST body 语句数:", len(chunk.get("body") or []))

# 直接编译 vm_pro
rng = random.Random(42)
gen = NameGenerator(rng=rng)
vmc = ProVMCompiler(rng, gen)
# 先做捕获变量预扫描（compile_chunk 内部也会做，这里打印用）
vmc._pre_scan_captured(chunk)
print("捕获变量:", vmc._captured_vars)

# 编译 chunk（包含预扫描+编译+回填+生成解释器）
final = vmc.compile_chunk(chunk)
print("最终代码长度:", len(final) if final else 0)
if final is None:
    print("编译失败！")
    sys.exit(1)

# 执行
from lupa import LuaRuntime
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
out = []
g["print"] = lambda *a: out.append("\t".join(str(x) for x in a))
try:
    lua.execute(final)
    print("输出:", out)
except Exception as e:
    print("错误:", e)
    # 打印出错位置附近的代码
    lines = final.split("\n")
    print(f"总行数: {len(lines)}")
    # 找到出错行
    import re
    m = re.search(r":(\d+):", str(e))
    if m:
        lineno = int(m.group(1))
        for i in range(max(1, lineno-3), min(len(lines)+1, lineno+3)):
            print(f"{i:4d}| {lines[i-1][:140]}")
