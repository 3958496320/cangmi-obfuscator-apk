# -*- coding: utf-8 -*-
"""
anti_deobfuscation.py
=====================
第 5 层（反调试 / 反篡改）+ 第 7 层（反自动化反混淆）。

【第 5 层】对标 Synapse X / ComboSec。
- 检测 debug 库存在、getfenv 异常、hookfunction 篡改；全部 pcall 包裹。
- 检测到调试/篡改时进入「误导模式」（设置诱饵标志，不影响真实逻辑）。

【第 7 层】反自动化反混淆专项。
- AST 结构扰乱：冗余括号、对比较表达式施加双重否定（仅对保证返回布尔的
  比较运算符施加，语义零改变）。
- 字符串拆分与动态拼接：将字符串字面量拆为 2~3 片，运行时用 `..` 拼接
  （需在第 1 层字符串加密之前运行，加密层会分别加密各片段）。
- 关键函数动态调用：将 print/warn/pairs 等安全函数调用改为通过环境解析器
  `_env[name]` 动态索引；环境解析器 pcall 包裹 getfenv，失败回退 _G，
  保证所有注入器可用。
- 表字段访问混淆：由第 1 层字符串加密统一处理（a.field -> a[_S("field")]）。

兼容性红线：所有可能失败的探测均用 pcall 包裹；game/workspace 等环境全局
保持直接访问（避免 _G 在 Luau 中不含它们导致崩溃）。
"""

from __future__ import annotations
import random
from typing import List, Optional, Set

from ast_parser import Node, N, walk, transform
from util import NameGenerator, GLOBAL_LIBS

# 可安全动态索引的「纯函数」集合（在所有执行器的 getfenv 环境中均存在）
_SAFE_API_REDIRECT = {
    "print", "warn", "pairs", "ipairs", "tostring", "tonumber",
    "type", "select", "next", "assert", "error", "pcall", "xpcall",
    "rawget", "rawset", "rawequal", "rawlen", "setmetatable", "getmetatable",
    "unpack", "string", "table", "math", "os", "coroutine", "bit32", "task",
    "wait", "spawn", "delay", "tick",
}

# 比较运算符（结果恒为布尔，可安全施加双重否定）
_COMPARISON_OPS = {"==", "~=", "<", ">", "<=", ">="}


# ===========================================================================
# 第 7 层：AST 结构扰乱
# ===========================================================================

def disrupt_ast(chunk: Node, rng: random.Random,
                max_perturb: int = 200) -> int:
    """对 AST 施加冗余括号与双重否定扰乱。

    仅对保证语义不变的位置施加：
    - Name / Number / Call 节点随机包裹 Paren；
    - 比较运算 BinOp 随机施加 `not not (...)`。
    返回施加的扰乱次数。

    安全性：Name 节点若出现在赋值左侧（lvalue），禁止包裹 Paren，
    否则 `(x) = 1` 会触发 Lua 语法错误。

    额外安全性（语句首括号合并）：
    - Lua 语法中换行不是语句分隔符。若前一条语句是函数调用 `f(x)`，
      下一条语句以 `(` 开头（如 `(name)[k](...)`），解析器会把两者合并为
      链式调用 `f(x)(name)[k](...)`。由于 `f(x)` 返回 nil，调用 nil 会触发
      "attempt to call a nil value"。因此任何「语句起始前缀表达式」的最左
      Name 不得包裹 Paren。本函数收集 CallStatement.func 与 Assign 的 Index
      目标的「最左 Name」并排除。
    """
    lvalue_ids: set = set()
    stmt_call_ids: set = set()
    noreturn_ids: set = set()

    def _leftmost_name(node: Node) -> Optional[Node]:
        """返回前缀表达式链最左端的 Name 节点；若无则 None。

        例： a        -> a
             a.b      -> a
             a[b]     -> a
             a().b    -> a
             (a).b    -> a （穿透 Paren）
        """
        cur: Node = node
        seen = 0
        while isinstance(cur, Node) and seen < 64:  # 防环
            seen += 1
            t = cur.type
            if t == "Name":
                return cur
            if t == "Paren":
                cur = cur.get("expr")
                continue
            if t == "Index":
                cur = cur.get("obj")
                continue
            if t == "Call":
                cur = cur.get("func")
                continue
            if t == "MethodCall":
                cur = cur.get("obj")
                continue
            if t == "MethodName":
                cur = cur.get("obj")
                continue
            return None
        return None

    def _collect_stmt_prefix_calls(expr: Node):
        """沿语句前缀链向下收集所有 Call 节点 id。

        语句前缀链 = 从 CallStatement.expr 开始，依次穿透 Call.func /
        MethodCall.obj / Index.obj / Paren.expr，直到抵达 Name 为止。

        链上任何一个 Call 被包成 Paren 都会让整条语句以 `(` 开头，
        从而与上一条调用语句合并（Lua 不以换行作为语句分隔符）。
        例：`getObj():method()` -> `(getObj()):method()` 会与上一条
        `prev()` 合并为 `prev()(getObj()):method()`，触发
        "attempt to call a table value"。
        """
        cur: Node = expr
        seen = 0
        while isinstance(cur, Node) and seen < 64:
            seen += 1
            t = cur.type
            if t == "Call":
                stmt_call_ids.add(id(cur))
                cur = cur.get("func")
                continue
            if t == "MethodCall":
                cur = cur.get("obj")
                continue
            if t == "Index":
                cur = cur.get("obj")
                continue
            if t == "Paren":
                cur = cur.get("expr")
                continue
            break

    def _mark(node: Node):
        if not isinstance(node, Node):
            return
        if node.type == "Assign":
            for tgt in node.get("targets") or []:
                if isinstance(tgt, Node) and tgt.type == "Name":
                    lvalue_ids.add(id(tgt))
                elif isinstance(tgt, Node) and tgt.type == "Index":
                    # 形如 t[k] = v：禁止包裹 t，否则 (t)[k]=v 会与上一条
                    # 调用语句合并为 f(x)(t)[k]=v（静默语义篡改）。
                    lm = _leftmost_name(tgt)
                    if lm is not None:
                        lvalue_ids.add(id(lm))
        elif node.type == "CallStatement":
            # 统一处理 Call / MethodCall 语句：保护前缀链上所有 Call
            # 节点（避免被 Paren 包裹），以及最左 Name（同上）。
            expr = node.get("expr")
            if isinstance(expr, Node) and expr.type in ("Call", "MethodCall"):
                _collect_stmt_prefix_calls(expr)
                lm = _leftmost_name(expr)
                if lm is not None:
                    lvalue_ids.add(id(lm))
        elif node.type == "FunctionDecl":
            # 函数声明名（function a.b:method() ...）的最左 Name 不可包裹 Paren：
            # gen_funcname 不识别 Paren，会输出空接收者 → `function :method()`
            fn_name = node.get("name")
            if isinstance(fn_name, Node):
                lm = _leftmost_name(fn_name)
                if lm is not None:
                    lvalue_ids.add(id(lm))
        elif node.type == "GenericFor":
            # 泛型 for 的迭代器表达式列表：全部禁止加括号
            for e in node.get("exprs") or []:
                if isinstance(e, Node):
                    noreturn_ids.add(id(e))
        elif node.type == "Return":
            # return 的表达式列表：禁止加括号（保留多返回值与尾调用语义）
            for e in node.get("exprs") or []:
                if isinstance(e, Node):
                    noreturn_ids.add(id(e))
        for key, val in list(node.attrs.items()):
            if isinstance(val, Node):
                _mark(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        _mark(item)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                _mark(sub)

    _mark(chunk)

    count = [0]

    def visit(node: Node) -> Node:
        if count[0] >= max_perturb:
            return node
        t = node.type
        # Name：排除 lvalue 与多值上下文（noreturn_ids）
        if t == "Name" and id(node) not in lvalue_ids \
                and id(node) not in noreturn_ids and rng.random() < 0.08:
            count[0] += 1
            return N("Paren", expr=node)
        if t == "Number" and rng.random() < 0.08:
            count[0] += 1
            return N("Paren", expr=node)
        # Call：排除语句位与多值上下文（noreturn_ids 截断 ipairs 等多返回值）
        if t == "Call" and id(node) not in stmt_call_ids \
                and id(node) not in noreturn_ids and rng.random() < 0.05:
            count[0] += 1
            return N("Paren", expr=node)
        if t == "BinOp" and node.get("op") in _COMPARISON_OPS and rng.random() < 0.12:
            count[0] += 1
            inner = N("Paren", expr=node)
            return N("UnaryOp", op="not",
                     operand=N("UnaryOp", op="not", operand=inner))
        return node

    transform(chunk, visit)
    return count[0]


# ===========================================================================
# 第 7 层：字符串拆分与动态拼接（须在第 1 层加密前运行）
# ===========================================================================

def split_strings(chunk: Node, rng: random.Random,
                  min_len: int = 6, max_splits: int = 300) -> int:
    """将字符串字面量拆分为 2~3 片，用 `..` 运行时拼接。

    - 仅拆分长度 >= min_len 的普通字符串；
    - 跳过已标记 _enc_payload / _verbatim 的字符串（加密产物）；
    - 跳过方法名 / 字段名（MethodCall.method 是字符串属性，非 String 节点，天然不受影响）；
    - 表构造器的字符串键也参与拆分（拆分后仍为合法表达式）。
    返回拆分次数。
    """
    count = [0]

    def visit(node: Node) -> Node:
        if count[0] >= max_splits:
            return node
        if node.type != "String":
            return node
        if node.attrs.get("_enc_payload") or node.attrs.get("_verbatim"):
            return node
        # 跳过函数声明字段名（_no_encrypt），拆分会破坏 gen_funcname
        if node.attrs.get("_no_encrypt"):
            return node
        value = node.get("value")
        if not isinstance(value, str) or len(value) < min_len:
            return node
        # 拆成 2~3 片
        n_parts = rng.randint(2, 3)
        parts = _split_str(value, n_parts, rng)
        if len(parts) < 2:
            return node
        expr = N("String", value=parts[0])
        for p in parts[1:]:
            expr = N("BinOp", op="..", left=expr, right=N("String", value=p))
        count[0] += 1
        # 用 Paren 包裹，保证在索引/调用上下文优先级正确
        return N("Paren", expr=expr)

    transform(chunk, visit)
    return count[0]


def _split_str(s: str, n: int, rng: random.Random) -> List[str]:
    """把字符串 s 随机切成 n 段非空片段。"""
    if n <= 1 or len(s) < n:
        return [s]
    # 随机选 n-1 个切点
    cuts = sorted(rng.sample(range(1, len(s)), n - 1))
    parts = []
    prev = 0
    for c in cuts:
        parts.append(s[prev:c])
        prev = c
    parts.append(s[prev:])
    return parts


# ===========================================================================
# 第 7 层：关键函数动态调用（环境解析器）
# ===========================================================================

def redirect_apis(chunk: Node, rng: random.Random,
                  env_name: Optional[str] = None) -> str:
    """将安全函数调用改为通过环境解析器动态索引。

    在 Chunk 顶部注入：
        local <env> = (function()
            local ok, e = pcall(getfenv)
            if ok and e then return e end
            return _G
        end)()

    随后将 `print(x)` 等改写为 `<env>["print"](x)`（字符串键交由第 1 层加密）。
    返回环境解析器变量名。
    """
    gen = NameGenerator(rng)
    env_name = env_name or gen.fresh()

    # 构造解析器定义 AST
    # local function <f>() local ok, e = pcall(function() return getfenv() end); if ok and e then return e end; return _G end
    # 用 function 包裹 getfenv() 而非直接 pcall(getfenv())，避免 Lua 5.3 中
    # getfenv 为 nil 时 getfenv() 在 pcall 外先求值导致崩溃
    inner_fn = N("Function", params=[], is_vararg=False, body=[
        N("LocalAssign", names=["ok", "e"],
          exprs=[N("Call", func=N("Name", name="pcall"),
                   args=[N("Function", params=[], is_vararg=False, body=[
                       N("Return", exprs=[N("Call",
                           func=N("Name", name="getfenv"), args=[])])
                   ])])]),
        N("If",
          cond=N("BinOp", op="and", left=N("Name", name="ok"),
                 right=N("Name", name="e")),
          body=[N("Return", exprs=[N("Name", name="e")])],
          elifs=[], else_body=None),
        N("Return", exprs=[N("Name", name="_G")]),
    ])
    # local <env> = (<inner_fn>)()
    resolver_decl = N("LocalAssign", names=[env_name], exprs=[
        N("Call", func=N("Paren", expr=inner_fn), args=[])
    ])

    # 改写：Call.func 为 Name 且 name 在 _SAFE_API_REDIRECT 时 -> <env>["name"](...)
    redirected = [0]

    def visit(node: Node) -> Node:
        if node.type == "Call":
            fn = node.get("func")
            if fn.type == "Name" and fn.get("name") in _SAFE_API_REDIRECT:
                key_str = fn.get("name")
                new_func = N("Index", obj=N("Name", name=env_name),
                             key=N("String", value=key_str))
                node.attrs["func"] = new_func
                redirected[0] += 1
        return node

    transform(chunk, visit)

    # 插入到顶部
    body = chunk.get("body")
    body.insert(0, resolver_decl)
    return env_name


# ===========================================================================
# 第 5 层：反调试 / 反篡改
# ===========================================================================

def inject_anti_debug(chunk: Node, rng: random.Random,
                      flag_name: Optional[str] = None) -> str:
    """注入反调试 / 反篡改检测块（全部 pcall 包裹）。

    生成的等价逻辑：
        local <flag> = false  -- 检测到异常时为 true（用于误导模式，不影响真实逻辑）
        do
            local ok, dbg = pcall(function() return debug end)
            if ok and type(dbg) == "table" and dbg.getinfo then
                <flag> = true
            end
            local ok2, ge = pcall(getfenv)
            if ok2 and ge and ge.getfenv then
                <flag> = true
            end
            -- hookfunction 篡改检测（仅当 hookfunction 存在时）
            local ok3, hf = pcall(function() return hookfunction end)
            if ok3 and type(hf) == "function" then
                <flag> = true
            end
        end

    所有探测均 pcall 包裹，绝不抛错。flag 仅作误导模式开关，真实逻辑不受影响。
    返回 flag 变量名。
    """
    gen = NameGenerator(rng)
    flag_name = flag_name or gen.fresh()

    # local <flag> = false
    flag_decl = N("LocalAssign", names=[flag_name], exprs=[N("False")])

    # debug 检测
    dbg_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[N("Name", name="debug")])
    ])
    dbg_block_body = [
        N("LocalAssign", names=["ok", "dbg"],
          exprs=[N("Call", func=N("Name", name="pcall"),
                   args=[N("Paren", expr=dbg_fn)])]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("BinOp", op="and",
                        left=N("Name", name="ok"),
                        right=N("BinOp", op="==",
                                left=N("Call", func=N("Name", name="type"),
                                       args=[N("Name", name="dbg")]),
                                right=N("String", value="table"))),
                 right=N("Index", obj=N("Name", name="dbg"),
                         key=N("String", value="getinfo"))),
          body=[N("Assign", targets=[N("Name", name=flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ]

    # getfenv 异常检测
    ge_block_body = [
        N("LocalAssign", names=["ok2", "ge"],
          exprs=[N("Call", func=N("Name", name="pcall"),
                   args=[N("Name", name="getfenv")])]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("Name", name="ok2"),
                 right=N("Index", obj=N("Name", name="ge"),
                         key=N("String", value="getfenv"))),
          body=[N("Assign", targets=[N("Name", name=flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ]

    # hookfunction 检测
    hf_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[N("Name", name="hookfunction")])
    ])
    hf_block_body = [
        N("LocalAssign", names=["ok3", "hf"],
          exprs=[N("Call", func=N("Name", name="pcall"),
                   args=[N("Paren", expr=hf_fn)])]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("Name", name="ok3"),
                 right=N("BinOp", op="==",
                         left=N("Call", func=N("Name", name="type"),
                                args=[N("Name", name="hf")]),
                         right=N("String", value="function"))),
          body=[N("Assign", targets=[N("Name", name=flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ]

    check_block = N("Do", body=dbg_block_body + ge_block_body + hf_block_body)

    body = chunk.get("body")
    body.insert(0, check_block)
    body.insert(0, flag_decl)
    return flag_name


# ===========================================================================
# 统一入口（供 obfuscator_core 调用，控制顺序）
# ===========================================================================

def _mark_table_field_keys(chunk: Node) -> None:
    """标记 table 字段名（TableField 的 String key）为 _no_encrypt。

    必须在 split_strings 之前调用。split_strings 会把长字符串（>=6 字符）
    拆成 `..` 拼接，拆分后 TableField 的 key 不再是 String 节点，
    encrypt_strings 里的 _mark_table_field_keys 将无法识别并保护它们。
    典型受害者：opts.Callback（8 字符）被拆分+加密后，真实注入器环境若
    解密不稳定，UI 库读 opts.Callback 得到 nil，部分库会把 nil 回调
    当作默认开启，导致 Toggle 控件误开（如雷达系统进游戏即开）。
    字段名是外部 API 契约（UI 库读 opts.Value/opts.Title/opts.Callback），
    必须保持明文，本函数统一保护所有 TableField 的 String key。
    """
    def _mark(n: Node) -> None:
        if n.type == "TableField":
            key = n.attrs.get("key")
            if key is not None and isinstance(key, Node) and key.type == "String":
                key.attrs["_no_encrypt"] = True
    walk(chunk, _mark)


def apply_pre_encryption(chunk: Node, rng: random.Random) -> dict:
    """在第 1 层字符串加密「之前」运行的反自动化变换。

    包含：字符串拆分、AST 扰乱、动态 API 索引。
    返回统计信息。
    """
    stats = {}
    # 必须先标记 table 字段名，再拆分字符串。否则长字段名（如 Callback）
    # 会被 split_strings 拆成 `..` 拼接，之后 encrypt_strings 无法保护。
    _mark_table_field_keys(chunk)
    stats["split"] = split_strings(chunk, rng)
    stats["redirect"] = 0
    # redirect_apis 注入解析器并改写调用
    redirect_apis(chunk, rng)
    stats["redirect"] = 1
    stats["disrupt"] = disrupt_ast(chunk, rng)
    return stats


def apply_anti_debug(chunk: Node, rng: random.Random) -> str:
    """在第 1 层之后运行的反调试注入。返回 flag 变量名。"""
    return inject_anti_debug(chunk, rng)
