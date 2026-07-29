# -*- coding: utf-8 -*-
"""
garbage_injector.py
===================
第 4 层：死代码 / 垃圾代码注入。

对标 Bill's Lua Obfuscator。在每个代码块的随机位置插入「语法正确、语义无害」
的代码片段。所有垃圾代码一律包裹在独立的 `do ... end` 块中，仅使用局部变量，
因此：
- 不会污染全局环境；
- 不会与已重命名的真实变量冲突；
- 不会产生任何副作用或崩溃。

通过 bloat_ratio 控制注入量（占原始代码的比例），由自适应引擎调节。
"""

from __future__ import annotations
import random
from typing import List, Optional

from ast_parser import Node, N
from util import NameGenerator


def _gen_garbage_block(gen: NameGenerator, rng: random.Random) -> Node:
    """生成一个独立的 do...end 垃圾块 AST。"""
    variant = rng.randint(0, 5)
    if variant == 0:
        # 算术自洽块
        a = gen.fresh(); b = gen.fresh(); c = gen.fresh()
        body = [
            N("LocalAssign", names=[a, b, c],
              exprs=[N("Number", value=str(rng.randint(1, 999999))),
                     N("Number", value=str(rng.randint(1, 999999))),
                     N("Number", value=str(rng.randint(1, 999999)))]),
            N("Assign", targets=[N("Name", name=a)],
              exprs=[N("BinOp", op="+",
                       left=N("BinOp", op="*", left=N("Name", name=a), right=N("Name", name=b)),
                       right=N("Name", name=c))]),
            N("Assign", targets=[N("Name", name=b)],
              exprs=[N("BinOp", op="%", left=N("Name", name=b), right=N("Number", value="97"))]),
        ]
    elif variant == 1:
        # 表操作块（恒不抛错）
        t = gen.fresh(); k = gen.fresh()
        body = [
            N("LocalAssign", names=[t],
              exprs=[N("Table", fields=[
                  N("TableItem", value=N("Number", value=str(rng.randint(0, 1000)))),
                  N("TableItem", value=N("Number", value=str(rng.randint(0, 1000)))),
                  N("TableItem", value=N("String", value="x")),
              ])]),
            N("LocalAssign", names=[k], exprs=[N("Number", value="1")]),
            N("NumericFor", var=gen.fresh(), start=N("Number", value="1"),
              limit=N("Number", value=str(rng.randint(2, 8))), step=None,
              body=[N("Assign",
                      targets=[N("Index", obj=N("Name", name=t), key=N("Name", name=k))],
                      exprs=[N("Number", value="0")])]),
        ]
    elif variant == 2:
        # 恒假分支（永远不执行，但静态可见）
        x = gen.fresh()
        body = [
            N("LocalAssign", names=[x], exprs=[N("Nil")]),
            N("If", cond=N("False"), body=[
                N("Assign", targets=[N("Name", name=x)],
                  exprs=[N("Number", value=str(rng.randint(0, 100)))])
            ], elifs=[], else_body=None),
        ]
    elif variant == 3:
        # 字符串拼接块（结果丢弃）
        s = gen.fresh()
        words = [N("String", value=w) for w in ("q", "z", "m", "p", "t")]
        rng.shuffle(words)
        expr = words[0]
        for w in words[1:]:
            expr = N("BinOp", op="..", left=expr, right=w)
        body = [
            N("LocalAssign", names=[s], exprs=[expr]),
            N("Assign", targets=[N("Name", name=s)],
              exprs=[N("BinOp", op="..", left=N("Name", name=s), right=N("String", value=""))]),
        ]
    elif variant == 4:
        # 嵌套 do 块 + 布尔恒等式
        v = gen.fresh()
        inner = [
            N("LocalAssign", names=[v], exprs=[N("True")]),
            N("Assign", targets=[N("Name", name=v)],
              exprs=[N("BinOp", op="and",
                       left=N("Name", name=v),
                       right=N("UnaryOp", op="not",
                               operand=N("BinOp", op="==",
                                         left=N("Number", value="1"),
                                         right=N("Number", value="2"))))]),
        ]
        body = [N("Do", body=inner)]
    else:
        # 数值循环累加（无副作用）
        acc = gen.fresh(); idx = gen.fresh()
        body = [
            N("LocalAssign", names=[acc], exprs=[N("Number", value="0")]),
            N("NumericFor", var=idx, start=N("Number", value="1"),
              limit=N("Number", value=str(rng.randint(3, 20))), step=None,
              body=[N("Assign", targets=[N("Name", name=acc)],
                      exprs=[N("BinOp", op="+", left=N("Name", name=acc),
                               right=N("Name", name=idx))])]),
        ]
    node = N("Do", body=body)
    # 标记为垃圾块：注入器不得再向其内部递归注入，否则垃圾块里的 NumericFor
    # 会被再次注入含 NumericFor 的垃圾块，层层嵌套形成指数级循环炸弹
    # （例如 16×4×14×5×4×11×14×17×16×11×9×11 ≈ 8170 亿次迭代）。
    node.attrs["_garbage"] = True
    return node


# 可注入垃圾的块类型（其 body 为语句列表）
_INJECTABLE_BLOCKS = {
    "Chunk", "Do", "While", "Repeat", "If",
    "NumericFor", "GenericFor", "Function", "LocalFunction", "FunctionDecl",
}


def inject_garbage(chunk: Node, rng: random.Random,
                   bloat_ratio: float = 0.5,
                   max_blocks: int = 200) -> int:
    """向 AST 各代码块注入垃圾代码。

    参数：
        bloat_ratio: 目标垃圾量占原始代码的比例（0.5~1.0）。
        max_blocks:  注入块数硬上限，防止巨型脚本膨胀失控。

    返回：实际注入的垃圾块数量。

    兼容性红线：Lua 语法规定 `return` 必须是块的最后一条语句；为兼容
    Lua 5.1 系执行器，`break` 也按「块终结语句」处理。因此插入位置严格
    限制在第一个 Return/Break 之前，绝不插入到终结语句之后。
    """
    gen = NameGenerator(rng)
    # 统计原始语句数，据此估算目标注入量
    original_count = [0]
    _count_statements(chunk, original_count)
    target = int(original_count[0] * bloat_ratio)
    target = max(1, min(target, max_blocks))

    injected = [0]
    _walk_inject(chunk, rng, gen, target, injected)
    return injected[0]


# 块终结语句：其后不得再插入任何语句（Lua 语法 / 5.1 兼容）
_TERMINATING_STMTS = {"Return", "Break"}


def _max_insert_pos(val: list) -> int:
    """计算语句列表中允许插入垃圾的最大位置（含）。

    返回值 max_pos 满足：插入位置必须 <= max_pos。
    若列表中存在 Return/Break，则只能插在第一个终结语句「之前」；
    否则可插入到末尾（len(val)）。
    """
    n = len(val)
    for i, s in enumerate(val):
        if isinstance(s, Node) and s.type in _TERMINATING_STMTS:
            return i  # 可插入 0..i（即在终结语句之前）
    return n


def _walk_inject(node: Node, rng: random.Random, gen: NameGenerator,
                 target: int, injected: List[int]):
    """递归遍历并在合适的 block 中注入垃圾。"""
    if injected[0] >= target:
        return
    # 绝不向已标记的垃圾块内部递归注入：垃圾块可能含 NumericFor，
    # 再次注入会形成指数级嵌套循环（循环炸弹），导致脚本运行数十秒乃至超时。
    if node.attrs.get("_garbage"):
        return
    for key, val in list(node.attrs.items()):
        if isinstance(val, list) and val and isinstance(val[0], Node) and _is_stmt_list(val):
            n_insert = rng.randint(0, 2)
            for _ in range(n_insert):
                if injected[0] >= target:
                    break
                # 关键：插入位置不得超过第一个 Return/Break（避免语法错误）
                max_pos = _max_insert_pos(val)
                if max_pos < 0:
                    max_pos = 0
                pos = rng.randint(0, max_pos)
                val.insert(pos, _gen_garbage_block(gen, rng))
                injected[0] += 1
            # 继续递归这些语句
            for s in val:
                if isinstance(s, Node):
                    _walk_inject(s, rng, gen, target, injected)
        elif isinstance(val, Node):
            _walk_inject(val, rng, gen, target, injected)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, Node):
                    _walk_inject(item, rng, gen, target, injected)
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, Node):
                            _walk_inject(sub, rng, gen, target, injected)


def _is_stmt_list(lst: list) -> bool:
    """启发式判断 list 是否为语句列表（而非表达式列表/名称字符串列表）。"""
    first = lst[0]
    if not isinstance(first, Node):
        return False
    # 名称字符串列表（LocalAssign.names / GenericFor.names）是 str，不会进这里
    # 表达式列表的元素类型在 _STMT_TYPES 之外
    return first.type in _STMT_TYPES


_STMT_TYPES = {
    "LocalAssign", "Assign", "CallStatement", "Do", "While", "Repeat",
    "If", "NumericFor", "GenericFor", "FunctionDecl", "LocalFunction",
    "Return", "Break", "Continue", "Goto", "Label",
}


def _count_statements(node: Node, counter: List[int]):
    """统计 AST 中语句总数（用于估算注入量）。"""
    if not isinstance(node, Node):
        return
    for key, val in node.attrs.items():
        if isinstance(val, list) and val and isinstance(val[0], Node) and _is_stmt_list(val):
            counter[0] += len(val)
            for s in val:
                _count_statements(s, counter)
        elif isinstance(val, Node):
            _count_statements(val, counter)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, Node):
                    _count_statements(item, counter)
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, Node):
                            _count_statements(sub, counter)
