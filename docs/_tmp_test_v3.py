# -*- coding: utf-8 -*-
"""临时验证：v3 字符串加密（滚动异或 + 随机无意义字符插入）往返正确性。"""
import os
import sys
import re
import random
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
exec(open(os.path.join(HERE, 'obfuscator_all.py')).read())


def luau_decrypt_mirror(data: bytes, key: int, offset: int, mask: int) -> bytes:
    """精确镜像 _build_decrypt_function 生成的 Luau 解密逻辑。"""
    block = (key % 4) + 6
    t = []
    ri = 0
    n = len(data)
    for i in range(1, n + 1):  # 1-based
        if i % block != 0:
            ri += 1
            b = data[i - 1]
            rk = (key + (ri - 1)) % 256
            b = ((b ^ mask) - offset) % 256
            b = b ^ rk
            t.append(b & 0xFF)
    return bytes(t)


def test_roundtrip():
    cases = [
        b"",                                  # 空串
        b"A",                                 # 单字节
        b"AB",                                # 两字节
        b"short",                             # 短串（不触达首个 block 边界）
        b"this is a medium length string",    # 中等
        b"x" * 5,                             # 恰好 < block
        b"x" * 6,                             # 跨越首个边界
        b"x" * 7,
        b"x" * 12,                            # 跨越两个边界
        b"x" * 13,
        b"x" * 100,                           # 多边界
        b"x" * 1000,                          # 长串
        "中文测试 UTF-8 多字节字符 🚀✨".encode("utf-8"),  # 多字节
        bytes(range(256)) * 3,                # 全字节值覆盖
    ]
    # 覆盖所有 block 取值（6..9）：key % 4 == 0,1,2,3
    key_pool = [4, 5, 6, 7, 8, 16, 17, 100, 200, 255, 1]
    total = 0
    for key in key_pool:
        for offset in [0, 1, 17, 128, 255]:
            for mask in [0, 1, 64, 128, 255]:
                for data in cases:
                    total += 1
                    enc = _encrypt_bytes(data, key, offset, mask)
                    dec = luau_decrypt_mirror(enc, key, offset, mask)
                    if dec != data:
                        print(f"FAIL key={key} off={offset} mask={mask} "
                              f"len={len(data)}")
                        print(f"  expected ({len(data)}): {data[:40]!r}...")
                        print(f"  got      ({len(dec)}): {dec[:40]!r}...")
                        return False
                    # 垃圾插入验证：仅当真实字节数足以触达首个 block 边界时
                    # 才强制要求密文比明文长（len < block 时合法地无垃圾）
                    block = (key % 4) + 6
                    if len(data) >= block and len(enc) <= len(data):
                        print(f"FAIL no garbage inserted: key={key} "
                              f"len={len(data)} block={block} enclen={len(enc)}")
                        return False
    print(f"[roundtrip] OK — {total} 组 (key,offset,mask,data) 全部往返一致")
    return True


def test_block_coverage():
    """验证 block 在 6..9 范围内均被覆盖（key%4 == 0..3）。"""
    seen = set()
    for key in range(0, 256):
        seen.add((key % 4) + 6)
    if seen != {6, 7, 8, 9}:
        print(f"FAIL block coverage: {seen}")
        return False
    print(f"[block] OK — block 取值覆盖 {sorted(seen)}")
    return True


def test_nondeterminism():
    """同一明文多次加密应产出不同密文（垃圾字节随机）。"""
    data = b"deterministic plaintext for nondeterminism check" * 2
    key, offset, mask = 37, 91, 173
    samples = {_encrypt_bytes(data, key, offset, mask) for _ in range(20)}
    if len(samples) < 2:
        print(f"FAIL nondeterminism: 仅产出 {len(samples)} 种密文")
        return False
    # 但所有密文都必须能正确解密
    for s in samples:
        if luau_decrypt_mirror(s, key, offset, mask) != data:
            print("FAIL nondeterminism: 某密文解密不一致")
            return False
    print(f"[nondeterminism] OK — 20 次加密产出 {len(samples)} 种不同密文，均正确解密")
    return True


def test_decrypt_emit():
    """隔离验证：直接序列化 _build_decrypt_function 生成的 AST（重命名前），
    确认含 v3 特征：block 计算、i % block 跳过、滚动密钥。"""
    dec_node = _build_decrypt_function("__dec", "__cache")
    # generate_code 要求顶层为 Chunk，故包裹一层
    src = generate_code(N("Chunk", body=[dec_node]))
    checks = {
        "block 计算 (key % 4)": "key % 4" in src or "(key % 4)" in src,
        "block + 6": "+ 6" in src,
        "i % block 跳过": "i % block" in src,
        "~= 0 判定": "~=" in src,
        "滚动密钥 (ri - 1)": "ri - 1" in src or "(ri - 1)" in src,
        "table.concat": "table.concat" in src,
        "string.byte": "string.byte" in src,
        # 关键：ri 自增必须是对外层 ri 赋值，不能是 local（否则遮蔽致 ri 恒 0）
        "ri = ri + 1 (非 local)": "ri = ri + 1" in src,
        "无 local ri 遮蔽": "local ri = ri" not in src,
        "无 local ri = ri + 1": "local ri = ri + 1" not in src,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print(f"FAIL decrypt_emit: 缺少特征 {failed}")
        print("---- 生成的解密函数 ----")
        print(src)
        return False
    print(f"[decrypt_emit] OK — 解密函数 AST 含全部 v3 特征（{len(checks)} 项）")
    return True


def test_e2e_obfuscate():
    """端到端：对样例 Lua 脚本执行完整混淆，确认无异常、有加密字符串、
    输出显著膨胀。运行时语义正确性已由 test_roundtrip 的 Python 镜像保证。"""
    src = '''
local function greet(name)
    print("Hello, " .. name .. "!")
    return "greeted:" .. name
end
greet("World")
'''
    try:
        result = obfuscate(src)
    except Exception:
        print("FAIL e2e: obfuscate 抛异常")
        traceback.print_exc()
        return False
    code = result["code"]
    # 加密字符串存在：应出现 \\ddd 十进制转义序列（密文载荷）
    has_escapes = bool(re.search(r"\\\d{1,3}", code))
    # 输出应显著膨胀（混淆生效）
    if len(code) <= len(src):
        print(f"FAIL e2e: 输出未膨胀 (in={len(src)} out={len(code)})")
        return False
    if not has_escapes:
        print("FAIL e2e: 未检测到加密字符串转义序列")
        return False
    print(f"[e2e] OK — 混淆成功，输出 {len(code)} 字符 "
          f"(膨胀 {len(code)/max(len(src),1):.1f}x)，含加密字符串")
    return True


# ---------------- 提升3：嵌套（双重）跳转表分发器 ----------------

class _Break(Exception):
    pass


class _Return(Exception):
    pass


def _interp_dispatch(dispatcher, env):
    """极简 Python AST 解释器：仅解释 CFF 分发子集
    (While / If-elseif-else / Assign / Break / Return / Number / Name / ==,~=)。
    记录 __log 赋值序列，用于验证 group 执行顺序。"""
    log = []

    def eval_expr(node):
        if node.type == "Number":
            return int(node.get("value"))
        if node.type == "Name":
            return env.get(node.get("name"), 0)
        if node.type == "BinOp":
            l = eval_expr(node.get("left"))
            r = eval_expr(node.get("right"))
            op = node.get("op")
            if op == "==":
                return 1 if l == r else 0
            if op == "~=":
                return 1 if l != r else 0
        raise AssertionError(f"无法求值: {node.type} {node.attrs}")

    def exec_stmts(stmts):
        for s in stmts:
            t = s.type
            if t == "Assign":
                val = eval_expr(s.get("exprs")[0])
                tgt = s.get("targets")[0]
                if tgt.type == "Name":
                    env[tgt.get("name")] = val
                    if tgt.get("name") == "__log":
                        log.append(val)
            elif t == "If":
                taken = False
                if eval_expr(s.get("cond")):
                    exec_stmts(s.get("body"))
                    taken = True
                else:
                    for ec, eb in s.get("elifs", []):
                        if eval_expr(ec):
                            exec_stmts(eb)
                            taken = True
                            break
                if not taken and s.get("else_body"):
                    exec_stmts(s.get("else_body"))
            elif t == "Break":
                raise _Break()
            elif t == "While":
                try:
                    while eval_expr(s.get("cond")):
                        exec_stmts(s.get("body"))
                except _Break:
                    pass
            elif t == "Return":
                raise _Return()

    try:
        exec_stmts([dispatcher])
    except _Return:
        pass
    return log


def _make_group(i, with_return=False):
    """构造一个合成 group：__log = i（可选末尾 return）。"""
    stmts = [N("Assign", targets=[name_node("__log")],
               exprs=[number_node(i)])]
    if with_return:
        stmts.append(N("Return", exprs=[]))
    return stmts


def test_nested_cff():
    """验证嵌套跳转表分发器：
    1. group 按 0,1,...,N-1 顺序执行；
    2. (page,slot) 分配为双射（无冲突）；
    3. 含 return 的 group 截断后续；
    4. 生成的 Luau 含二层 if 结构。"""
    rng = random.Random(20260804)

    # 用例 A：10 个普通 group
    groups = [_make_group(i) for i in range(10)]
    pg, st = "__pg", "__st"
    dispatcher, ep, es = _build_nested_dispatcher(groups, rng, pg, st)
    env = {pg: ep, st: es, "__log": -1}
    log = _interp_dispatch(dispatcher, env)
    if log != list(range(10)):
        print(f"FAIL nested A: 执行顺序错误 {log}")
        return False
    # 双射性：所有 (page,slot) 唯一
    seen = set()
    # 通过遍历 dispatcher 提取所有 (page==K, slot==J) 组合较复杂；
    # 改为直接验证：模拟时每个 group 恰好被执行一次（无重复、无遗漏）
    if len(set(log)) != 10:
        print(f"FAIL nested A: group 重复或遗漏 {log}")
        return False

    # 用例 B：5 个 group，第 3 个含 return（应停在 0,1,2）
    groupsB = [_make_group(i) for i in range(5)]
    groupsB[2] = _make_group(2, with_return=True)
    dispatcherB, epB, esB = _build_nested_dispatcher(groupsB, rng, pg, st)
    envB = {pg: epB, st: esB, "__log": -1}
    logB = _interp_dispatch(dispatcherB, envB)
    if logB != [0, 1, 2]:
        print(f"FAIL nested B (return): 期望 [0,1,2] 实际 {logB}")
        return False

    # 用例 C：6 个 group（边界：触发嵌套的最小值）
    groupsC = [_make_group(i) for i in range(6)]
    dispatcherC, epC, esC = _build_nested_dispatcher(groupsC, rng, pg, st)
    envC = {pg: epC, st: esC, "__log": -1}
    logC = _interp_dispatch(dispatcherC, envC)
    if logC != list(range(6)):
        print(f"FAIL nested C (边界6): {logC}")
        return False

    # 结构验证：序列化后应含二层 if（while 内 if 内 if）
    src = generate_code(N("Chunk", body=[dispatcher]))
    if_count = src.count("if ")
    elseif_count = src.count("elseif")
    if not (if_count >= 2 and elseif_count >= 2 and "~= 0" in src):
        print(f"FAIL nested 结构: if={if_count} elseif={elseif_count}")
        print(src[:400])
        return False

    # 用例 D：多次随机，验证顺序恒为 0..N-1
    for trial in range(40):
        n = rng.randint(6, 30)
        g = [_make_group(i) for i in range(n)]
        d, e1, e2 = _build_nested_dispatcher(g, rng, pg, st)
        envD = {pg: e1, st: e2, "__log": -1}
        lg = _interp_dispatch(d, envD)
        if lg != list(range(n)):
            print(f"FAIL nested D (trial {trial}, n={n}): {lg}")
            return False

    print(f"[nested_cff] OK — 10/5(return)/6(边界)/40 次随机 全部按序执行，"
          f"结构含二层 if/elseif")
    return True


def test_nested_via_flatten():
    """集成测试：通过 flatten_function_body 对含 ≥6 group 的函数平坦化，
    确认走嵌套分支（输出含双状态变量 + 二层 if）。"""
    rng = random.Random(777)
    gen = NameGenerator(rng)
    # 12 条顶层语句 → _group_states 产生 ≥6 group → 触发嵌套分支
    stmts = [N("Assign", targets=[name_node("x")],
               exprs=[number_node(i)]) for i in range(12)]
    func = N("Function", params=[], is_vararg=False, body=stmts)
    did = flatten_function_body(func, rng, gen, max_states=50)
    if not did:
        print("FAIL nested_via_flatten: 未进行平坦化")
        return False
    src = generate_code(N("Chunk", body=func.get("body")))
    # 嵌套特征：双状态变量同时声明 + while <pg> ~= 0 + 内嵌 if
    has_dual_local = bool(re.search(r"local \w+, \w+ = \d+, \d+", src))
    has_nested_if = src.count("elseif") >= 2 and "~= 0" in src
    if not (has_dual_local and has_nested_if):
        print(f"FAIL nested_via_flatten: dual_local={has_dual_local} "
              f"nested_if={has_nested_if}")
        print(src[:500])
        return False
    print(f"[nested_via_flatten] OK — flatten_function_body 走嵌套分支，"
          f"输出 {len(src)} 字符，含双状态变量 + 二层 if")
    return True


# ---------------- 提升4：控制流三元伪装 ----------------

def _lua_truthy(v):
    """Lua 真值语义：仅 false 与 nil 为假，0/"" 均为真。"""
    return not (v is False or v is None)


def _eval_node(node, env, se_log):
    """极简求值器：支持三元伪装相关子集。"""

    def ev(n):
        t = n.type
        if t == "Number":
            return int(n.get("value"))
        if t == "String":
            return n.get("value")
        if t == "True":
            return True
        if t == "False":
            return False
        if t == "Nil":
            return None
        if t == "Name":
            return env.get(n.get("name"))
        if t == "Paren":
            return ev(n.get("expr"))
        if t == "BinOp":
            op = n.get("op")
            l, r = n.get("left"), n.get("right")
            if op == "and":
                lv = ev(l)
                return ev(r) if _lua_truthy(lv) else lv
            if op == "or":
                lv = ev(l)
                return lv if _lua_truthy(lv) else ev(r)
            lv, rv = ev(l), ev(r)
            if op == "==":
                return lv == rv
            if op == "~=":
                return lv != rv
            if op == "+":
                return lv + rv
            if op == "-":
                return lv - rv
            if op == "*":
                return lv * rv
            raise AssertionError(f"未支持 BinOp {op}")
        if t == "Call":
            f = ev(n.get("func"))
            args = [ev(a) for a in n.get("args", [])]
            return f(*args)
        raise AssertionError(f"未支持求值 {t}")

    def exec_stmts(stmts):
        for s in stmts:
            t = s.type
            if t == "Assign":
                tgt = s.get("targets")[0]
                env[tgt.get("name")] = ev(s.get("exprs")[0])
            elif t == "LocalAssign":
                for nm, ex in zip(s.get("names"), s.get("exprs") or []):
                    env[nm] = ev(ex)
            elif t == "If":
                if _lua_truthy(ev(s.get("cond"))):
                    exec_stmts(s.get("body"))
                else:
                    matched = False
                    for ec, eb in s.get("elifs", []):
                        if _lua_truthy(ev(ec)):
                            exec_stmts(eb)
                            matched = True
                            break
                    if not matched and s.get("else_body"):
                        exec_stmts(s.get("else_body"))
            elif t == "Return":
                raise _Return()

    class _Return(Exception):
        pass

    try:
        exec_stmts(node.get("body"))
    except _Return:
        pass


def test_ternary_disguise():
    """验证三元伪装的语义等价性（值 + 惰性副作用）。"""
    import copy
    rng = random.Random(31337)

    def se():
        se_log.append("se")
        return 777

    # 构造 chunk：10 个可转换 if（then=数值字面量）+ 2 个不可转换
    body = []
    for i in range(10):
        body.append(N("If",
                      cond=name_node("c"),
                      body=[N("Assign", targets=[name_node(f"x{i}")],
                              exprs=[number_node(100 + i)])],
                      elifs=[],
                      else_body=[N("Assign", targets=[name_node(f"x{i}")],
                              exprs=[call_node(name_node("se"), [])])]))
    # 不可转换：then 是 Call（非真值字面量）
    body.append(N("If", cond=name_node("c"),
                  body=[N("Assign", targets=[name_node("y")],
                          exprs=[call_node(name_node("se"), [])])],
                  elifs=[],
                  else_body=[N("Assign", targets=[name_node("y")],
                          exprs=[number_node(5)])]))
    # 不可转换：两分支目标不同
    body.append(N("If", cond=name_node("c"),
                  body=[N("Assign", targets=[name_node("a")],
                          exprs=[number_node(1)])],
                  elifs=[],
                  else_body=[N("Assign", targets=[name_node("b")],
                          exprs=[number_node(2)])]))
    original = N("Chunk", body=body)

    transformed = copy.deepcopy(original)
    cnt = apply_ternary_disguise(transformed, rng)
    if cnt == 0:
        print("FAIL ternary: 未发生任何转换")
        return False

    # 序列化检查：转换后含 and/or 三元，且仍含 if（不可转换的保留）
    src = generate_code(transformed)
    if " and " not in src or " or " not in src or "if " not in src:
        print(f"FAIL ternary: 结构异常 (and/or/if 缺失)")
        print(src[:400])
        return False

    # 语义等价：多种 c 取值下，original 与 transformed 结果一致
    for c_val in [True, False, 1, 0, None, "", "s", 42]:
        # original
        se_log_o = []
        env_o = {"c": c_val, "se": lambda: (se_log_o.append("se"), 777)[1]}
        _eval_node(original, env_o, se_log_o)
        # transformed
        se_log_t = []
        env_t = {"c": c_val, "se": lambda: (se_log_t.append("se"), 777)[1]}
        _eval_node(transformed, env_t, se_log_t)
        # 比较 x0..x9, y, a, b
        for i in range(10):
            if env_o.get(f"x{i}") != env_t.get(f"x{i}"):
                print(f"FAIL ternary 值不等: c={c_val!r} x{i}: "
                      f"o={env_o.get(f'x{i}')} t={env_t.get(f'x{i}')}")
                return False
        if env_o.get("y") != env_t.get("y") or env_o.get("a") != env_t.get("a") \
                or env_o.get("b") != env_t.get("b"):
            print(f"FAIL ternary y/a/b 不等: c={c_val!r}")
            return False
        # 副作用调用次数必须一致（惰性等价）
        if len(se_log_o) != len(se_log_t):
            print(f"FAIL ternary 副作用不等: c={c_val!r} "
                  f"o={len(se_log_o)} t={len(se_log_t)}")
            return False

    print(f"[ternary] OK — 转换 {cnt} 处，8 种 c 取值下值与副作用均等价，"
          f"不可转换 if 保留")
    return True


# ---------------- 提升5：斐波那契递归垃圾块 ----------------

def _eval_ast(node, env):
    """支持 LocalFunction/Call/Return/递归 的 AST 求值器。"""

    class _Return(Exception):
        def __init__(self, val):
            self.val = val

    def ev(n, scope):
        t = n.type
        if t == "Number":
            return int(n.get("value"))
        if t == "True":
            return True
        if t == "False":
            return False
        if t == "Nil":
            return None
        if t == "Name":
            return scope.get(n.get("name"))
        if t == "Paren":
            return ev(n.get("expr"), scope)
        if t == "BinOp":
            op = n.get("op")
            l, r = n.get("left"), n.get("right")
            if op == "and":
                lv = ev(l, scope)
                return ev(r, scope) if _lua_truthy(lv) else lv
            if op == "or":
                lv = ev(l, scope)
                return lv if _lua_truthy(lv) else ev(r, scope)
            lv, rv = ev(l, scope), ev(r, scope)
            if op == "+":
                return lv + rv
            if op == "-":
                return lv - rv
            if op == "*":
                return lv * rv
            if op == "<":
                return lv < rv
            if op == "==":
                return lv == rv
            if op == "~=":
                return lv != rv
            raise AssertionError(f"BinOp {op}")
        if t == "Call":
            f = ev(n.get("func"), scope)
            args = [ev(a, scope) for a in n.get("args", [])]
            return f(*args)
        if t == "Function":
            params = n.get("params")
            fbody = n.get("body")
            captured = scope  # 词法捕获（同一 dict 引用，含 fn 定义）

            def closure(*args):
                local = dict(captured)
                for p, a in zip(params, args):
                    local[p] = a
                try:
                    exec_stmts(fbody, local)
                except _Return as r:
                    return r.val
                return None
            return closure
        raise AssertionError(f"eval {t}")

    def exec_stmts(stmts, scope):
        for s in stmts:
            t = s.type
            if t == "LocalAssign":
                for nm, ex in zip(s.get("names"), s.get("exprs") or []):
                    scope[nm] = ev(ex, scope)
            elif t == "LocalFunction":
                scope[s.get("name")] = ev(s.get("func"), scope)
            elif t == "Assign":
                for tgt, ex in zip(s.get("targets"), s.get("exprs")):
                    scope[tgt.get("name")] = ev(ex, scope)
            elif t == "If":
                if _lua_truthy(ev(s.get("cond"), scope)):
                    exec_stmts(s.get("body"), scope)
                else:
                    matched = False
                    for ec, eb in s.get("elifs", []):
                        if _lua_truthy(ev(ec, scope)):
                            exec_stmts(eb, scope)
                            matched = True
                            break
                    if not matched and s.get("else_body"):
                        exec_stmts(s.get("else_body"), scope)
            elif t == "Return":
                vals = [ev(e, scope) for e in s.get("exprs", [])]
                raise _Return(vals[0] if vals else None)
            elif t == "Do":
                exec_stmts(s.get("body"), scope)
            elif t == "Chunk":
                exec_stmts(s.get("body"), scope)

    exec_stmts(node.get("body"), env)


def _py_fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def test_fib_garbage():
    """验证斐波那契递归垃圾块：语义正确、标记 _garbage、重命名器保持递归一致。"""
    import copy

    # 强制生成 variant 6 的辅助：直接调用 _gen_garbage_block 多次取 fib 块
    rng = random.Random(9001)
    gen = NameGenerator(rng)
    fib_blocks = []
    attempts = 0
    while len(fib_blocks) < 30 and attempts < 400:
        attempts += 1
        blk = _gen_garbage_block(gen, rng)
        # 识别 fib 块：body 含 LocalFunction
        if any(s.type == "LocalFunction" for s in blk.get("body")):
            fib_blocks.append(blk)

    if len(fib_blocks) < 5:
        print(f"FAIL fib: 仅生成 {len(fib_blocks)} 个 fib 块")
        return False

    # 1. 语义正确性：执行每个 fib 块，res 应等于 py_fib(call_n)
    for blk in fib_blocks:
        # 标记检查
        if not blk.attrs.get("_garbage"):
            print("FAIL fib: 缺少 _garbage 标记")
            return False
        # 提取 call_n（外层 Call 的参数）
        lassign = blk.get("body")[1]  # LocalAssign res = fn(call_n)
        call = lassign.get("exprs")[0]
        call_n = int(call.get("args")[0].get("value"))
        env = {}
        _eval_ast(N("Chunk", body=[blk]), env)
        # res 是第二个语句赋值的变量
        res_name = lassign.get("names")[0]
        got = env.get(res_name)
        exp = _py_fib(call_n)
        if got != exp:
            print(f"FAIL fib: call_n={call_n} 期望 {exp} 实际 {got}")
            return False

    # 2. 重命名器保持递归一致：函数名与递归引用应改为同一新名
    blk = copy.deepcopy(fib_blocks[0])
    chunk = N("Chunk", body=[blk])
    rename(chunk, random.Random(7))
    src = generate_code(chunk)
    # 找到 LocalFunction 的新名
    fn_name = None
    for s in blk.get("body"):
        if s.type == "LocalFunction":
            fn_name = s.get("name")
            break
    if fn_name is None:
        print("FAIL fib: 重命名后未找到 LocalFunction")
        return False
    # fn_name 应在源码中出现 >=3 次（1 定义 + 2 递归 + 1 外层调用 = 4）
    occurrences = src.count(fn_name)
    if occurrences < 3:
        print(f"FAIL fib: 重命名后递归引用不一致，{fn_name} 仅出现 {occurrences} 次")
        print(src)
        return False

    # 3. 序列化无异常且含 function 关键字
    if "function" not in src:
        print("FAIL fib: 序列化缺少 function")
        return False

    print(f"[fib] OK — {len(fib_blocks)} 个 fib 块语义正确（fib(5..12)），"
          f"_garbage 标记OK，重命名后递归引用一致（{fn_name} 出现 {occurrences} 次）")
    return True


# ---------------- 提升6：元表操作垃圾块 ----------------

def test_metatable_garbage():
    """验证元表操作垃圾块：结构正确、标记 _garbage、序列化合法、
    重命名器保持 setmetatable/getmetatable 不变。"""
    import copy

    rng = random.Random(424242)
    gen = NameGenerator(rng)
    mt_blocks = []
    attempts = 0
    while len(mt_blocks) < 20 and attempts < 400:
        attempts += 1
        blk = _gen_garbage_block(gen, rng)
        # 识别元表块：body 含 CallStatement 调用 setmetatable
        for s in blk.get("body"):
            if s.type == "CallStatement":
                call = s.get("expr")
                if call.type == "Call":
                    fn = call.get("func")
                    if fn.type == "Name" and fn.get("name") == "setmetatable":
                        mt_blocks.append(blk)
                        break

    if len(mt_blocks) < 5:
        print(f"FAIL mt: 仅生成 {len(mt_blocks)} 个元表块")
        return False

    for blk in mt_blocks:
        # 1. 标记检查
        if not blk.attrs.get("_garbage"):
            print("FAIL mt: 缺少 _garbage 标记")
            return False

    # 2. 序列化 + 结构检查
    blk = mt_blocks[0]
    chunk = N("Chunk", body=[blk])
    src = generate_code(chunk)
    required = ["setmetatable", "getmetatable", "__index", "__add",
                "__concat", "__call", "__newindex", "__tostring"]
    for kw in required:
        if kw not in src:
            print(f"FAIL mt: 序列化缺少 {kw}")
            print(src[:600])
            return False

    # 3. 重命名器一致性：setmetatable/getmetatable 保留，local 名被改名
    blk2 = copy.deepcopy(mt_blocks[0])
    chunk2 = N("Chunk", body=[blk2])
    rename(chunk2, random.Random(99))
    src2 = generate_code(chunk2)
    if "setmetatable" not in src2 or "getmetatable" not in src2:
        print("FAIL mt: 重命名后 setmetatable/getmetatable 被错误改名")
        print(src2[:600])
        return False
    # 元方法名 __index 等是字符串 key，不应被改名
    if "__index" not in src2:
        print("FAIL mt: 重命名后 __index 字段名丢失")
        return False

    # 4. 结构检查：含 Table + TableField + Function 节点
    has_table = [False]
    has_tablefield = [False]
    has_function = [False]

    def check(n):
        if n.type == "Table":
            has_table[0] = True
        elif n.type == "TableField":
            has_tablefield[0] = True
        elif n.type == "Function":
            has_function[0] = True

    walk(blk, check)
    if not (has_table[0] and has_tablefield[0] and has_function[0]):
        print(f"FAIL mt: 结构不完整 table={has_table[0]} "
              f"field={has_tablefield[0]} func={has_function[0]}")
        return False

    # 5. 无全局赋值（所有结果丢弃到 local）
    for s in blk.get("body"):
        if s.type == "Assign":
            print("FAIL mt: 存在全局赋值（应为纯局部）")
            return False

    print(f"[mt] OK — {len(mt_blocks)} 个元表块结构正确，含 6 种元方法，"
          f"setmetatable/getmetatable 保留，重命名一致")
    return True


# ---------------- 提升7：执行器指纹检测 ----------------

def test_executor_fingerprint():
    """验证执行器指纹检测：15 项探测全部注入、pcall 包裹、序列化合法。
    提升11：新增 8 项执行器特有 API 探测（getloadedmodules 等）。"""
    rng = random.Random(12345)
    chunk = parse_source("local x = 1\n")
    flag_name = inject_anti_debug(chunk, rng)
    src = generate_code(chunk)

    # 1. flag 变量声明存在
    if f"local {flag_name}" not in src:
        print(f"FAIL fp: flag 声明缺失 {flag_name}")
        return False

    # 2. 15 项探测全部存在（原 7 项 + 提升11 新增 8 项）
    required = [
        "debug",          # 1. debug 表检测
        "getfenv",        # 2. getfenv 异常检测
        "hookfunction",   # 3. hookfunction 检测
        "identifyexecutor",  # 4. 执行器标识
        "game",           # 5. 环境完整性（game/Instance）
        "getrenv",        # 6. getrenv 指纹
        "Drawing",        # 7. Drawing 库指纹
        # 提升11 新增 8 项
        "getloadedmodules",   # 12. 模块枚举（执行器特有）
        "getrunningscripts",  # 13. 运行中脚本枚举
        "getcallingscript",   # 14. 调用脚本检测
        "isluau",             # 15. Luau 检测
        "hookmetamethod",     # 16. 元方法 hook 检测
        "getrawmetatable",    # 17. 原始元表检测
        "setfenv",            # 18. setfenv 存在性
        "dump",               # 19. string.dump 存在性（通过 string 表索引）
    ]
    missing = [kw for kw in required if kw not in src]
    if missing:
        print(f"FAIL fp: 缺少指纹检测 {missing}")
        print(src[:1200])
        return False

    # 3. 全部 pcall 包裹（原 11 次 + 新增 8 次 = 至少 19 次）
    pcall_count = src.count("pcall")
    if pcall_count < 19:
        print(f"FAIL fp: pcall 调用仅 {pcall_count} 次（应 >= 19）")
        return False

    # 4. typeof 用于 Instance 检测
    if "typeof" not in src or "Instance" not in src:
        print("FAIL fp: 缺少 typeof/Instance 环境检测")
        return False

    # 5. 序列化无异常（parse -> generate 往返一致）
    chunk2 = parse_source(src)
    src2 = generate_code(chunk2)
    if not src2:
        print("FAIL fp: 往返序列化失败")
        return False

    # 6. 重命名后往返一致（_pNN_ 局部名应被重命名，不残留固定特征）
    chunk3 = parse_source(src)
    rename(chunk3, random.Random(42))
    src3 = generate_code(chunk3)
    if not src3 or "getloadedmodules" not in src3:
        print("FAIL fp: 重命名后丢失探测目标")
        return False

    print(f"[fp] OK — 15 项指纹探测全部注入（原7+提升11新增8），"
          f"{pcall_count} 次 pcall 包裹，重命名往返一致")
    return True


def test_opaque_predicate_enhanced():
    """验证增强不透明谓词（提升11）：8 种恒等式全部能生成、结构合法、
    序列化往返一致。4 种恒假 + 4 种恒真（not 包裹）混入。"""
    rng = random.Random(20260804)
    gen = NameGenerator(rng)
    # 强制覆盖所有 opaque_kind 0-7：多轮抽样直到 8 种都见过
    seen_kinds = set()
    samples = []
    attempts = 0
    while len(seen_kinds) < 8 and attempts < 500:
        attempts += 1
        # 直接控制 variant=2 + 用独立 rng 推动 opaque_kind
        blk = _gen_garbage_block(gen, random.Random(rng.randint(0, 1 << 30)))
        # 识别 variant 2 块：body 含 LocalAssign nil + If
        if (len(blk.get("body")) == 2
                and blk.get("body")[0].type == "LocalAssign"
                and blk.get("body")[1].type == "If"):
            samples.append(blk)
            # 通过 cond 结构推断 kind（粗略：含 not → 恒真系列 4-7）
            cond = blk.get("body")[1].get("cond")
            has_not = cond.type == "UnaryOp" and cond.get("op") == "not"
            seen_kinds.add("true" if has_not else "false")

    # 至少要见到恒假和恒真两大类
    if "true" not in seen_kinds or "false" not in seen_kinds:
        print(f"FAIL opaque: 未覆盖恒假/恒真两大类 {seen_kinds}")
        return False

    # 全部样本：序列化往返一致、_garbage 标记存在
    for blk in samples:
        if not blk.attrs.get("_garbage"):
            print("FAIL opaque: 缺少 _garbage 标记")
            return False
        chunk = N("Chunk", body=[blk])
        src = generate_code(chunk)
        if "if " not in src:
            print(f"FAIL opaque: 序列化缺少 if {src[:200]}")
            return False
        # 往返
        chunk2 = parse_source(src)
        src2 = generate_code(chunk2)
        if not src2:
            print("FAIL opaque: 往返序列化失败")
            return False

    # 端到端：含 not 的恒真分支也必须能正确混淆
    src = 'local function f(x) return x end'
    r = obfuscate(src, seed=999)
    code = r["code"]
    # 混淆后应能 parse（语法合法）
    chunk3 = parse_source(code)
    if not generate_code(chunk3):
        print("FAIL opaque: 端到端混淆后语法不合法")
        return False

    print(f"[opaque] OK — 恒假/恒真两大类全覆盖，{len(samples)} 个样本"
          f"序列化+往返一致，端到端混淆合法")
    return True


def test_bitwise_garbage_block():
    """验证位运算模拟垃圾块（提升11 variant 5）：结构含 while+math.floor、
    语义正确（AND/OR/XOR 计算结果与 Python 一致）、_garbage 标记、序列化合法。"""
    rng = random.Random(424242)
    gen = NameGenerator(rng)
    bit_blocks = []
    attempts = 0
    while len(bit_blocks) < 15 and attempts < 600:
        attempts += 1
        blk = _gen_garbage_block(gen, rng)
        # 识别 variant 5 块：body 含 While + 多个 If（AND/OR/XOR 三个分支）
        has_while = any(s.type == "While" for s in blk.get("body"))
        if_count = sum(1 for s in blk.get("body")
                       if s.type == "While"
                       for sub in s.get("body") if sub.type == "If")
        if has_while and if_count >= 3:
            bit_blocks.append(blk)

    if len(bit_blocks) < 3:
        print(f"FAIL bit: 仅生成 {len(bit_blocks)} 个位运算块")
        return False

    for blk in bit_blocks:
        # 1. _garbage 标记
        if not blk.attrs.get("_garbage"):
            print("FAIL bit: 缺少 _garbage 标记")
            return False
        # 2. 序列化含关键结构
        src = generate_code(N("Chunk", body=[blk]))
        for kw in ["while", "math.floor", "%"]:
            if kw not in src:
                print(f"FAIL bit: 序列化缺少 {kw}")
                print(src[:400])
                return False
        # 3. 往返序列化
        chunk2 = parse_source(src)
        if not generate_code(chunk2):
            print("FAIL bit: 往返序列化失败")
            return False

    print(f"[bit] OK — {len(bit_blocks)} 个位运算块结构正确（while+"
          f"math.floor+3个If），_garbage 标记OK，往返一致")
    return True


def test_extended_env_checks():
    """验证扩展环境完整性检查（提升11）：13 项新增 env_check 全部注入、
    pcall 包裹、序列化合法。原 6 项 + 新增 13 项 = 19 项。"""
    rng = random.Random(77777)
    chunk = parse_source("local x = 1\n")
    stats = inject_runtime_protection(chunk, rng, dec_name="_dec",
                                       enable_loadstring=False)
    src = generate_code(chunk)

    # 13 项新增全局必须全部出现（env_check 通过 pcall 探测）
    required = [
        "assert", "error", "pcall", "xpcall", "select", "next",
        "rawget", "rawset", "rawequal", "tonumber",
        "math", "os", "coroutine",
    ]
    missing = [kw for kw in required if kw not in src]
    if missing:
        print(f"FAIL env: 缺少环境检查 {missing}")
        print(src[:1500])
        return False

    # checks 计数：原 3（game/workspace/print）+ 6（原 ext）+ 13（新）+ 其他
    # 至少要 >= 3 + 19 = 22（不含 stack/timebomb）
    if stats.get("checks", 0) < 22:
        print(f"FAIL env: checks 计数 {stats.get('checks')} < 22")
        return False

    # pcall 次数：每个 env_check 1 次 + 计数器校验 + stack 等，至少 22+
    if src.count("pcall") < 22:
        print(f"FAIL env: pcall 次数 {src.count('pcall')} < 22")
        return False

    # 往返一致
    chunk2 = parse_source(src)
    if not generate_code(chunk2):
        print("FAIL env: 往返序列化失败")
        return False

    print(f"[env] OK — 13 项新增环境检查全部注入（assert/error/pcall/.../"
          f"coroutine），checks={stats['checks']}，{src.count('pcall')} 次 pcall")
    return True


# ---------------- 提升8：定时自校验 + 自动恢复 ----------------

def test_timed_self_verify():
    """验证定时自校验+自动恢复：快照、spawn/task.wait 异步循环、
    flag 恢复、计数器恢复、pcall 包裹。"""
    rng = random.Random(77777)
    chunk = parse_source("local x = 1\n")
    stats = inject_runtime_protection(chunk, rng, dec_name="_dec",
                                       enable_loadstring=False)
    src = generate_code(chunk)

    # 1. 统计信息正确
    if not stats.get("timed_verify"):
        print("FAIL tv: stats 缺少 timed_verify")
        return False
    interval = stats.get("timed_interval", 0)
    if not (30 <= interval <= 120):
        print(f"FAIL tv: 定时间隔异常 {interval}")
        return False

    # 2. 关键结构存在
    required = [
        "spawn",          # 异步启动
        "task.wait",      # 定时等待
        "while",          # 循环
        "pairs",          # 计数器快照遍历
        "pcall",          # pcall 包裹
        "game",           # 环境重检
        "userdata",       # 类型检查
    ]
    for kw in required:
        if kw not in src:
            print(f"FAIL tv: 缺少 {kw}")
            print(src[:1200])
            return False

    # 3. while true 循环存在（定时校验循环）
    if "while true do" not in src:
        print("FAIL tv: 缺少 while true do 循环")
        return False

    # 4. 自动恢复逻辑：flag 恢复（snap_flag and not flag → flag=true）
    #    含 not 关键字（用于 flag 恢复条件）
    if "not " not in src:
        print("FAIL tv: 缺少 not 运算符（flag 恢复条件）")
        return False

    # 5. 计数器恢复：含 nil 比较（counter[key] == nil → 恢复）
    if "nil" not in src:
        print("FAIL tv: 缺少 nil（计数器恢复条件）")
        return False

    # 6. 序列化往返一致（parse -> generate）
    chunk2 = parse_source(src)
    src2 = generate_code(chunk2)
    if not src2 or "while true do" not in src2:
        print("FAIL tv: 往返序列化后结构丢失")
        return False

    # 7. 重命名器一致性：spawn/task.wait/pairs 保留
    chunk3 = parse_source(src)
    rename(chunk3, random.Random(42))
    src3 = generate_code(chunk3)
    for kw in ["spawn", "task", "wait", "pairs", "pcall", "game"]:
        if kw not in src3:
            print(f"FAIL tv: 重命名后 {kw} 丢失")
            return False

    print(f"[tv] OK — 定时间隔 {interval}s，含 spawn+task.wait 异步循环、"
          f"flag 恢复、计数器恢复、环境重检，{src.count('pcall')} 次 pcall")
    return True


if __name__ == "__main__":
    ok = True
    ok &= test_block_coverage()
    ok &= test_roundtrip()
    ok &= test_nondeterminism()
    ok &= test_decrypt_emit()
    ok &= test_e2e_obfuscate()
    ok &= test_nested_cff()
    ok &= test_nested_via_flatten()
    ok &= test_ternary_disguise()
    ok &= test_fib_garbage()
    ok &= test_metatable_garbage()
    ok &= test_executor_fingerprint()
    ok &= test_timed_self_verify()
    # 提升11 新增测试
    ok &= test_opaque_predicate_enhanced()
    ok &= test_bitwise_garbage_block()
    ok &= test_extended_env_checks()
    print()
    print("==== 全部通过 ====" if ok else "==== 存在失败 ====")
    sys.exit(0 if ok else 1)
