# -*- coding: utf-8 -*-
"""精确验证：bit32 fallback 是否触发 readonly 错误。"""
import subprocess, tempfile, os

LUAU = "/tmp/luau-bin/luau"

def run(code, timeout=10):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".luau", delete=False) as f:
        f.write(code); path = f.name
    try:
        r = subprocess.run([LUAU, path], capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    finally:
        os.unlink(path)

# 测试1: luau 下 bit32 状态
code1 = r'''
print("bit32存在:", type(bit32))
if bit32 then
    print("bxor:", type(bit32.bxor))
    print("band:", type(bit32.band))
    print("bor:", type(bit32.bor))
    print("bnot:", type(bit32.bnot))
    print("lshift:", type(bit32.lshift))
    print("rshift:", type(bit32.rshift))
end
print("bit存在:", type(bit))
'''
out, err, rc = run(code1)
print("=== 测试1: bit32 状态 ===")
print("rc:", rc)
print("stdout:", out)
if err: print("stderr:", err)

# 测试2: 直接运行 fallback 代码，看是否报错
import sys
sys.path.insert(0, "/workspace/docs")
from obfuscator_all import _BIT32_FALLBACK
code2 = _BIT32_FALLBACK + '\nprint("[FALLBACK_OK]")\n'
out2, err2, rc2 = run(code2)
print("\n=== 测试2: 单独运行 bit32 fallback ===")
print("rc:", rc2)
print("stdout:", out2)
if err2: print("stderr:", err2)

# 测试3: 检查 fallback 代码里 7137 行的判断在 luau 下是否进入
code3 = r'''
do
  local _bxor = (bit32 and bit32.bxor) or (bit and bit.bxor)
  local _band = (bit32 and bit32.band) or (bit and bit.band)
  local _bor  = (bit32 and bit32.bor)  or (bit and bit.bor)
  local _bnot = (bit32 and bit32.bnot) or (bit and bit.bnot)
  local _lsh  = (bit32 and bit32.lshift) or (bit and bit.lshift)
  local _rsh  = (bit32 and bit32.rshift) or (bit and bit.rshift)
  print("进入fallback块?", not (_bxor and _band and _bor and _bnot and _lsh and _rsh))
  print("_bxor=", _bxor, "_band=", _band, "_bor=", _bor)
end
print("[CHECK_OK]")
'''
out3, err3, rc3 = run(code3)
print("\n=== 测试3: fallback 判断条件 ===")
print("rc:", rc3)
print("stdout:", out3)
if err3: print("stderr:", err3)
