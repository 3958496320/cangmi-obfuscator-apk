import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import obfuscate_code
from lupa import LuaRuntime

# Test ecall function step by step
test_cases = [
    ("local s = 'hello: world' print(s:find(': '))", None),
    ("local s = 'hello: world' print(s:find(': ') + 2)", None),
    ("local s = 'hello: world' print(s:sub(s:find(': ') + 2, #s))", "world"),
    ("""
function ecall(fn, ...)
  local ok, err = pcall(fn, ...)
  assert(not ok)
  return err:sub(err:find(": ") + 2, #err)
end
print(ecall(function() assert(false) end))
""", "assertion failed!"),
    ("""
function ecall(fn, ...)
  local ok, err = pcall(fn, ...)
  assert(not ok)
  return err:sub(err:find(": ") + 2, #err)
end
print(ecall(function() assert() end))
""", "missing argument"),
]

for src, expected in test_cases:
    code = obfuscate_code(src, ninja_mode=False)
    lua = LuaRuntime(unpack_returned_tuples=True)
    outputs = []
    lua.globals()["print"] = lambda *a: outputs.append(" ".join(str(x) for x in a))
    try:
        lua.execute(code)
        out_str = " ".join(outputs)
        ok = (expected is None) or (expected in out_str)
        status = "OK  " if ok else "FAIL"
        print(f"{status} {src.strip()[:60]!r} -> {outputs}")
    except Exception as e:
        print(f"FAIL {src.strip()[:60]!r} -> ERR: {str(e)[:120]}")
