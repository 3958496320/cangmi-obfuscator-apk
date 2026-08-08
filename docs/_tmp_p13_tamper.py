# -*- coding: utf-8 -*-
"""P1-3 验证：CRC32 分段校验是否真的能检测字节码篡改。"""
import random
import re
import sys

sys.path.insert(0, "/workspace/src")

from lupa import LuaRuntime
from obfuscator_core import parse_source, NameGenerator
from vm_pro import vm_pro_compile

# 一个足够长的脚本，确保能跑到 ad_period 检查点触发 CRC 校验
SRC = """
local s = 0
for i = 1, 500 do
    s = s + i
end
print(s)
"""
EXPECTED = str(sum(range(1, 501)))  # 125250


def run_code(code, label):
    outputs = []
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    g["print"] = lambda *a: outputs.append("\t".join(str(x) for x in a))
    try:
        lua.execute(code)
    except Exception as e:
        return f"EXC: {str(e)[:60]}"
    return "\n".join(outputs).strip()


def tamper_bytecode(code):
    """在 bc 表里篡改一个数字元素（不影响表结构）。
    找到第一个形如 <数字> 的独立 token（在表内），把它改成另一个值。
    返回篡改后的 code。"""
    # 找到形如 ",12345," 的数字（表元素），改最后一位
    # 选一个足够靠后的数字（避开前几个结构元素），翻转最低位
    matches = list(re.finditer(r'(\d{5,})', code))
    if not matches:
        return code
    # 选第 20 个左右的数字篡改，避免破坏表结构
    target = matches[min(20, len(matches) - 1)]
    old = target.group(1)
    new = str(int(old) ^ 0x1)  # 翻转最低位
    return code[:target.start()] + new + code[target.end():]


def main():
    print("=" * 60, flush=True)
    print("P1-3 字节码防篡改校验测试", flush=True)
    print("=" * 60, flush=True)
    ok = True
    for seed in [1, 2, 3, 7, 42]:
        rng = random.Random(seed)
        gen = NameGenerator(rng)
        ast = parse_source(SRC)
        code = vm_pro_compile(ast, rng, gen)
        if not code:
            print(f"[seed{seed}] FAIL  vm_pro_compile returned None", flush=True)
            ok = False
            continue
        # 1) 未篡改：应输出正确结果
        out_clean = run_code(code, f"seed{seed}-clean")
        # 2) 篡改：CRC 应检测到，输出错乱或异常
        tampered = tamper_bytecode(code)
        out_tamper = run_code(tampered, f"seed{seed}-tamper")
        clean_ok = out_clean == EXPECTED
        tamper_detected = out_tamper != EXPECTED
        status = "PASS" if (clean_ok and tamper_detected) else "FAIL"
        if not (clean_ok and tamper_detected):
            ok = False
        print(f"[seed{seed}] {status}  clean={out_clean!r} tamper={out_tamper[:50]!r}", flush=True)
    print("=" * 60, flush=True)
    print("==== P1-3 ALL PASS ====" if ok else "==== P1-3 HAS FAIL ====", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
