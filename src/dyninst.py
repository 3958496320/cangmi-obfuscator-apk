# -*- coding: utf-8 -*-
"""
dyninst.py
==========
第 9 层：动态指令替换（DynInst）。

对标 VMProtect 思路。将关键运算符（+ - * / % ^ .. == ~=）动态替换为等效函数
调用，例如 `a + b` → `_G["<随机键>"](a, b)`，其中 `_G["<随机键>"]` 在运行时
注册为 `function(a, b) return a + b end`。

安全要点：
- 仅替换「函数可完美复刻」的运算符（不含 and/or/not，因其短路语义无法用函数复刻）；
- 替换点数量受 max_points 限制（默认 ≤20，轻度模式 ≤10），性能损耗可控；
- 运算符函数体内保留真实运算符（这才是「等效」的来源），且不会被本层再次替换；
- 替换后的 `_G["<键>"]` 字符串键交由第 1 层字符串加密处理（须在加密前运行）。
"""

from __future__ import annotations
import random
from typing import Optional, Dict

from ast_parser import Node, N, walk, transform
from util import NameGenerator, name_node, number_node, string_node, call_node

# 可替换的二元运算符（结果可由 function(a,b) return a op b end 完美复刻）
_REPLACEABLE_OPS = {"+", "-", "*", "/", "%", "^", "..", "==", "~="}


def apply_dyninst(chunk: Node, rng: random.Random,
                  max_points: int = 20) -> dict:
    """对 AST 应用动态指令替换。

    参数：
        max_points: 最多替换的运算点数（轻度模式传 10）。
    返回统计 {points, funcs}。
    """
    gen = NameGenerator(rng)

    # 1. 收集候选 BinOp 节点（可替换运算符），排除将要注入的运算符函数体
    candidates: list = []

    def collect(n: Node):
        if n.type == "BinOp" and n.get("op") in _REPLACEABLE_OPS:
            candidates.append(n)

    walk(chunk, collect)

    if not candidates:
        return {"points": 0, "funcs": 0}

    # 2. 随机选取最多 max_points 个（尽量分散）
    rng.shuffle(candidates)
    chosen = candidates[:max_points]

    # 3. 为每种运算符分配一个随机 _G 键（共享，减少函数数量）
    op_to_key: Dict[str, str] = {}
    used_ops = sorted({c.get("op") for c in chosen}, key=lambda x: rng.random())
    for op in used_ops:
        op_to_key[op] = gen.fresh()

    # 4. 注入运算符函数注册块（位于 Chunk 顶部）
    #    _G["<key>"] = function(a, b) return a <op> b end
    reg_body = []
    for op in used_ops:
        key = op_to_key[op]
        fn = N("Function", params=["a", "b"], is_vararg=False, body=[
            N("Return", exprs=[N("BinOp", op=op,
                                 left=name_node("a"),
                                 right=name_node("b"))])
        ])
        # 关键：禁止第 3 层 VM/CFF 处理这些运算符函数。
        # 它们处于热路径（每个被替换的运算符都会调用），若被 VM 编译为
        # 字节码 + 解释器循环，每次调用都要分配 R/C/P 三张表并逐指令解释，
        # 开销约 50~100x，会让含循环的脚本运行时间从毫秒级飙升到数十秒。
        # 这些函数体仅 1 条 Return，CFF 本就不会处理（需 ≥4 条），
        # 此处同时设 _cff_done / _no_flatten 以彻底跳过 VM 与 CFF。
        fn.attrs["_cff_done"] = True
        fn.attrs["_no_flatten"] = True
        # _G[key] = fn   （用 Index 赋值）
        reg_body.append(N("Assign",
            targets=[N("Index", obj=name_node("_G"), key=string_node(key))],
            exprs=[fn]))
    reg_block = N("Do", body=reg_body)
    # 标记 _dyninst_reg：供 obfuscator_core 在 L1/L8 之后将该注册块重新搬回
    # body 最前（位于 cache+dec 之后、wm_var 之前）。否则被 L1/L8/L0 诸层
    # 顶部插入挤到后面，wm_var（经 split+dyninst 后含 _G[dec(key)] 调用）
    # 与 prelude 会在注册之前使用，触发 "attempt to call a nil value"。
    reg_block.attrs["_dyninst_reg"] = True

    # 5. 标记已选节点，避免 transform 时重复处理；用 set(id) 追踪
    chosen_ids = {id(c) for c in chosen}
    replaced = [0]

    def visit(n: Node) -> Node:
        if n.type == "BinOp" and id(n) in chosen_ids and n.get("op") in op_to_key:
            key = op_to_key[n.get("op")]
            new_node = call_node(
                N("Index", obj=name_node("_G"), key=string_node(key)),
                [n.get("left"), n.get("right")],
            )
            replaced[0] += 1
            return new_node
        return n

    transform(chunk, visit)

    # 6. 把注册块插到最前
    body = chunk.get("body")
    body.insert(0, reg_block)

    return {"points": replaced[0], "funcs": len(used_ops)}
