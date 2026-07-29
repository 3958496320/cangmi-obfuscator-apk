# -*- coding: utf-8 -*-
"""
chunk_split.py
==============
第 10 层：代码块分割与重组（Chunk Split）。

对标 Prometheus。将每个函数体拆分为 3~8 个独立代码块（匿名函数存储），
运行时通过随机生成的跳转表（jump table）决定执行顺序。

核心设计：
- 仅处理「未被 CFF/VM 处理过」的 Function 节点（避免破坏第 3 层产物）；
- 仅处理「足够大」的函数体（≥6 条顶层语句才有收益）；
- 顶层 local 声明提升到外层（与 CFF 同款手法），保证跨块可见；
- 顶层 Return 转换为「返回值表」并由分发器捕获后透传；
- 跳转表长度受 max_order 限制（默认 ≤20，轻度模式 ≤10）；
- 每个块函数末尾默认返回哨兵 SENTINEL，表示「未要求外层 return」。

兼容性要点：
- 所有变换保持原语义；
- 不引入新 loadstring 调用；
- 哨兵表用空表 {} 而非 nil，避免多返回值解包歧义；
- 跳转表为静态排列，运行时无随机性（避免不同执行结果不同）。
"""

from __future__ import annotations
import random
from typing import List, Optional

from ast_parser import Node, N, walk
from util import (
    NameGenerator, name_node, number_node, string_node,
    call_node, index_node, clamp,
)


def _is_splittable(stmts: List[Node]) -> bool:
    """判断函数体是否适合做 chunk-split。

    条件：
    - 顶层语句数 ≥6（太少则切分无收益且膨胀过大）；
    - 不含顶层 Goto/Label（与跳转表语义冲突）；
    - 不含顶层 Break/Continue（顶层本就非法，但防御性跳过）。
    """
    if len(stmts) < 6:
        return False
    for s in stmts:
        if s.type in ("Goto", "Label", "Break", "Continue"):
            return False
    return True


def _collect_top_locals(stmts: List[Node]) -> List[str]:
    """收集函数体顶层 local 名（LocalAssign / LocalFunction）。"""
    names: List[str] = []
    for s in stmts:
        if s.type == "LocalAssign":
            names.extend(s.get("names"))
        elif s.type == "LocalFunction":
            names.append(s.get("name"))
    return names


def _convert_top_locals(stmts: List[Node]) -> List[Node]:
    """将顶层 local 声明转为赋值（与 CFF 同款）。"""
    out: List[Node] = []
    for s in stmts:
        if s.type == "LocalAssign":
            if s.get("exprs"):
                out.append(N("Assign",
                             targets=[N("Name", name=n) for n in s.get("names")],
                             exprs=s.get("exprs")))
            # 无初始化的 local 提升后丢弃
        elif s.type == "LocalFunction":
            out.append(N("Assign",
                         targets=[N("Name", name=s.get("name"))],
                         exprs=[s.get("func")]))
        else:
            out.append(s)
    return out


def _split_groups(stmts: List[Node], rng: random.Random,
                  min_chunks: int = 3, max_chunks: int = 8) -> List[List[Node]]:
    """将语句序列切分为 [min_chunks, max_chunks] 个连续块。"""
    n = len(stmts)
    if n < min_chunks:
        return [list(stmts)]
    # 决定块数 k：尽量在 [3,8] 内，且不超过 n
    k = clamp(rng.randint(min_chunks, max_chunks), min_chunks, n)
    # 用「切 k-1 刀」的方式分块，保证每块至少 1 条
    # 先均匀分，再随机扰动边界
    base = n // k
    rem = n % k
    groups: List[List[Node]] = []
    i = 0
    for j in range(k):
        size = base + (1 if j < rem else 0)
        # 轻微随机扰动（不破坏连续性，仅挪动相邻边界 ±1）
        size = clamp(size + rng.randint(-1, 1), 1, n - i - (k - j - 1))
        groups.append(stmts[i:i + size])
        i += size
    # 收尾：把剩余全部塞进最后一块
    if i < n:
        groups[-1].extend(stmts[i:])
    # 过滤空块（理论上不会出现）
    groups = [g for g in groups if g]
    return groups


def _rewrite_returns(stmts: List[Node], sentinel_name: str,
                     ret_holder: str) -> List[Node]:
    """把块内顶层 Return 改写为「设置返回值表 + 返回哨兵」。

    原：  return e1, e2, e3
    改：  <ret_holder> = {e1, e2, e3}; return <sentinel_name>

    块函数默认返回 nil；外层分发器据此判断是否需要 return。
    为避免「nil 返回值被吞掉」的歧义，我们让带 Return 的块返回哨兵表，
    不带 Return 的块返回 nil。外层据此分别处理。
    """
    out: List[Node] = []
    for s in stmts:
        if s.type == "Return":
            exprs = s.get("exprs") or []
            if exprs:
                # ret_holder = {e1, e2, ...}
                tbl = N("Table", fields=[
                    N("TableItem", key=None, value=e) for e in exprs
                ])
                out.append(N("Assign",
                             targets=[name_node(ret_holder)],
                             exprs=[tbl]))
            else:
                # 空 return -> 标记为「返回无值」
                out.append(N("Assign",
                             targets=[name_node(ret_holder)],
                             exprs=[N("Table", fields=[])]))
            out.append(N("Return", exprs=[name_node(sentinel_name)]))
        else:
            out.append(s)
    return out


def split_function_body(func: Node, rng: random.Random,
                        gen: NameGenerator,
                        max_order: int = 20) -> bool:
    """对一个 Function 节点执行 chunk-split。

    返回是否实际进行了切分。
    """
    if func.attrs.get("_cff_done") or func.attrs.get("_no_flatten") \
            or func.attrs.get("_chunk_split_done"):
        return False
    stmts = func.get("body")
    if not _is_splittable(stmts):
        return False

    # 1. 提升 top-level locals
    top_locals = _collect_top_locals(stmts)
    converted = _convert_top_locals(stmts)

    # 2. 切分为 3~8 块
    groups = _split_groups(converted, rng, 3, 8)
    if len(groups) < 3:
        return False

    # 3. 跳转表：随机排列，但第一块必须在最前（保证入口语义）。
    #    实现：把 [0..k-1] 除 0 外打乱，再前置 0。
    order = list(range(len(groups)))
    first = order.pop(0)
    rng.shuffle(order)
    order = [first] + order
    # 限制跳转表长度（轻度模式 max_order=10）
    if len(order) > max_order:
        order = order[:max_order]

    # 4. 为每块构造匿名函数
    sentinel = gen.fresh()       # 哨兵表（外层局部）
    ret_holder = gen.fresh()     # 当前块返回值容器
    chunks_tbl = gen.fresh()     # 块函数表
    order_tbl = gen.fresh()      # 跳转表
    idx_var = gen.fresh()        # for 循环变量
    ret_var = gen.fresh()        # 块函数返回值

    chunk_funcs: List[Node] = []
    for g_idx, group in enumerate(groups):
        rewritten = _rewrite_returns(group, sentinel, ret_holder)
        # 每个块函数：function() <rewritten> return nil end
        body = list(rewritten)
        # 若块末尾不是 return（被改写过的会带 return），补一个 return nil
        if not body or body[-1].type != "Return":
            body.append(N("Return", exprs=[N("Nil")]))
        fn = N("Function", params=[], is_vararg=False, body=body)
        chunk_funcs.append(fn)

    # 5. 构造新函数体
    new_body: List[Node] = []

    # 5.1 提升的 local 声明（一次性声明，初始 nil）
    if top_locals:
        new_body.append(N("LocalAssign", names=list(top_locals), exprs=[]))

    # 5.2 哨兵 + 返回值容器
    #     local <sentinel> = {}
    new_body.append(N("LocalAssign", names=[sentinel],
                      exprs=[N("Table", fields=[])]))
    #     local <ret_holder>
    new_body.append(N("LocalAssign", names=[ret_holder], exprs=[]))

    # 5.3 块函数表
    #     local <chunks_tbl> = { function()...end, function()...end, ... }
    tbl_fields = [
        N("TableItem", key=None, value=fn) for fn in chunk_funcs
    ]
    new_body.append(N("LocalAssign", names=[chunks_tbl],
                      exprs=[N("Table", fields=tbl_fields)]))

    # 5.4 跳转表
    #     local <order_tbl> = { <order[0]+1>, <order[1]+1>, ... }
    #     （Lua 索引从 1 开始，故 +1）
    order_fields = [
        N("TableItem", key=None, value=number_node(idx + 1))
        for idx in order
    ]
    new_body.append(N("LocalAssign", names=[order_tbl],
                      exprs=[N("Table", fields=order_fields)]))

    # 5.5 分发循环
    #     for <idx_var>, _ in ipairs(<order_tbl>) do
    #         local <ret_var> = <chunks_tbl>[<idx_var>]()
    #         if <ret_var> == <sentinel> then
    #             return table.unpack(<ret_holder>)
    #         end
    #     end
    # 用 table.unpack 而非全局 unpack：Lua 5.2+/5.3/Luau 均支持，
    # Lua 5.1 中 unpack 为全局但 Roblox Luau 同时提供两者，故 table.unpack 最安全。
    dispatch_body = [
        N("LocalAssign", names=[ret_var], exprs=[
            call_node(index_node(name_node(chunks_tbl), name_node(idx_var)), [])
        ]),
        N("If",
          cond=N("BinOp", op="==",
                 left=name_node(ret_var),
                 right=name_node(sentinel)),
          body=[N("Return", exprs=[
              call_node(index_node(name_node("table"),
                                   string_node("unpack")),
                        [name_node(ret_holder)])
          ])],
          elifs=[], else_body=None),
    ]
    new_body.append(N("GenericFor",
                      names=[idx_var, gen.fresh()],
                      exprs=[call_node(name_node("ipairs"),
                                       [name_node(order_tbl)])],
                      body=dispatch_body))

    # 6. 替换函数体并打标记
    func.attrs["body"] = new_body
    func.attrs["_chunk_split_done"] = True
    func.attrs["_no_flatten"] = True   # 防止后续 CFF（若有）破坏分发器
    func.attrs["_cff_done"] = True     # 标记已处理，避免 CFF 再触碰
    return True


def apply_chunk_split(chunk: Node, rng: random.Random,
                      max_order: int = 20) -> dict:
    """遍历 AST，对合适的 Function 节点应用 chunk-split。

    返回统计 {split_count}。
    """
    gen = NameGenerator(rng)
    stats = {"split_count": 0}

    def visit(node: Node):
        if not isinstance(node, Node):
            return
        if node.type == "Function" and not node.attrs.get("_chunk_split_done"):
            if split_function_body(node, rng, gen, max_order=max_order):
                stats["split_count"] += 1
        # 递归子节点（含刚改写的函数体里的嵌套函数）
        for key, val in list(node.attrs.items()):
            if isinstance(val, Node):
                visit(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        visit(item)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                visit(sub)

    visit(chunk)
    return stats
