import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import obfuscate_code
from lupa import LuaRuntime

with open('/tmp/luau_tables.luau') as f:
    src = f.read()
try:
    code = obfuscate_code(src, ninja_mode=False)
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(code)
    print('PASS: luau_tables.luau 执行成功')
except Exception as e:
    print(f'ERR: {str(e)[:200]}')
