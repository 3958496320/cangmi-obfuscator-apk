# -*- coding: utf-8 -*-
"""
anti_heuristic.py
=================
第 11 层：反启发式探测（Anti-Heuristic）。

检测可疑分析模式（如 `debug.getinfo` 高频调用、`pcall` 异常捕获尝试、
`os.clock()` 时间差异常），触发诱导路径（输出部分正确结果，关键逻辑被
悄悄替换为错误值）。

设计原则：
- 仅做「观察 + 误导」，绝不阻断真实逻辑（保证 100% 兼容）；
- 所有探测均 pcall 包裹，探测失败等同于「未发现异常」；
- 诱导路径只替换「计算型中间变量」的值，不影响控制流；
- 诱导变量由调用方注入到关键计算点（通过返回的诱饵变量名映射）；
- 检测点分散在脚本运行早期，便于在分析者拿到结果前切入误导。

诱导策略：
- 时间差异常（os.clock 跨阈值）：判定为单步调试/插桩分析；
- debug.getinfo 高频：判定为反混淆器在 trace 调用栈；
- pcall 异常捕获尝试：判定为 fuzzing/动态分析；
- 触发任一：设置 flag，调用方据此选择「真实值 / 诱饵值」。
"""

from __future__ import annotations
import random
from typing import Optional, Dict

from ast_parser import Node, N
from util import (
    NameGenerator, name_node, number_node, string_node,
    call_node, index_node,
)


def _pcall(expr: Node) -> Node:
    """把表达式包成 pcall(expr)。"""
    return call_node(name_node("pcall"), [expr])


def _build_time_probe(gen: NameGenerator, rng: random.Random,
                      flag_name: str) -> Node:
    """构造时间差异常探测块。

    逻辑：
        local t1 = os.clock()        -- pcall 包裹
        -- （此处由调用方插入若干真实语句，制造可测时间差）
        local t2 = os.clock()        -- pcall 包裹
        if t1 and t2 and (t2 - t1) > <threshold> then
            <flag_name> = true        -- 触发诱导
        end

    阈值取较大值（如 0.5s），避免正常慢机器误报。
    """
    t1ok = gen.fresh()
    t1 = gen.fresh()
    t2ok = gen.fresh()
    t2 = gen.fresh()
    threshold = rng.uniform(0.3, 1.5)  # 秒
    clock_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[call_node(
            index_node(name_node("os"), string_node("clock")), [])])
    ])
    # pcall 返回 (ok, val)：第一个是布尔 ok，第二个是 os.clock() 的值
    # 故声明顺序为 [ok, val]，后续算术用 val（即 t1/t2）
    return N("Do", body=[
        N("LocalAssign", names=[t1ok, t1], exprs=[
            _pcall(N("Paren", expr=clock_fn))
        ]),
        # 制造一点真实工作（小循环），让 t2 - t1 有意义
        N("LocalAssign", names=[gen.fresh()], exprs=[number_node(0)]),
        N("NumericFor", var=gen.fresh(), start=number_node(1),
          limit=number_node(rng.randint(5, 20)), step=None,
          body=[N("NoOp")]),
        N("LocalAssign", names=[t2ok, t2], exprs=[
            _pcall(N("Paren", expr=N("Function", params=[], is_vararg=False, body=[
                N("Return", exprs=[call_node(
                    index_node(name_node("os"), string_node("clock")), [])])
            ])))
        ]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("BinOp", op="and",
                        left=N("BinOp", op="and",
                               left=name_node(t1ok),
                               right=name_node(t2ok)),
                        right=name_node(t1)),
                 right=N("BinOp", op="and",
                         left=name_node(t2),
                         right=N("BinOp", op=">",
                                 left=N("Paren", expr=N("BinOp", op="-",
                                        left=name_node(t2),
                                        right=name_node(t1))),
                                 right=number_node(round(threshold, 4))))),
          body=[N("Assign", targets=[name_node(flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ])


def _build_getinfo_probe(gen: NameGenerator, rng: random.Random,
                         flag_name: str) -> Node:
    """构造 debug.getinfo 高频调用探测块。

    逻辑：
        -- 探测当前栈是否在被「频繁 getinfo」的环境里运行
        local ok, info = pcall(function() return debug.getinfo(2, "Sl") end)
        if ok and info and info.what == "C" then
            <flag_name> = true   -- 被原生 hook 包裹，可疑
        end
        -- 进一步：若 info.source 含 "<"（如 =[C] 或 <string>），也判定可疑
    """
    info_var = gen.fresh()
    ok_var = gen.fresh()
    getinfo_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[call_node(
            index_node(name_node("debug"), string_node("getinfo")),
            [number_node(2), string_node("Sl")])])
    ])
    return N("Do", body=[
        N("LocalAssign", names=[ok_var, info_var], exprs=[
            _pcall(N("Paren", expr=getinfo_fn))
        ]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("BinOp", op="and",
                        left=name_node(ok_var),
                        right=name_node(info_var)),
                 right=N("BinOp", op="==",
                         left=index_node(name_node(info_var),
                                         string_node("what")),
                         right=string_node("C"))),
          body=[N("Assign", targets=[name_node(flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
        # info.source 含 "<" 也判定可疑（pcall 包裹 string.find）
        N("If",
          cond=N("BinOp", op="and",
                 left=name_node(ok_var),
                 right=N("BinOp", op="and",
                         left=name_node(info_var),
                         right=N("Paren", expr=N("Call",
                            func=index_node(name_node("string"),
                                            string_node("find")),
                            args=[index_node(name_node(info_var),
                                             string_node("source")),
                                  string_node("<")])))),
          body=[N("Assign", targets=[name_node(flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ])


def _build_pcall_probe(gen: NameGenerator, rng: random.Random,
                       flag_name: str) -> Node:
    """构造 pcall 异常捕获尝试探测块。

    逻辑：
        -- 反混淆器常通过「故意触发错误并捕获」来分析环境
        -- 我们检测：尝试 error() 是否被外层 pcall 拦截
        local bait_ok = pcall(function() return true end)
        -- 再做一次「会抛错」的探测，如果没被外层拦截，说明没有外层 pcall
        -- 但若被外层 pcall 拦截，本块根本不会执行到这里……
        -- 改为：检测 xpcall 是否被 hook（通过比较两次 pcall 行为一致性）
        local a = pcall(function() return 1 end)
        local b = pcall(function() error("__probe__") end)
        -- 正常情况：a==true, b==false
        -- 若 b==true，说明 error 被 hook，可疑
        if a and b then
            <flag_name> = true
        end
    """
    a_var = gen.fresh()
    b_var = gen.fresh()
    a_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[number_node(1)])
    ])
    b_fn = N("Function", params=[], is_vararg=False, body=[
        N("CallStatement", expr=call_node(
            name_node("error"), [string_node("__probe__")]))
    ])
    return N("Do", body=[
        N("LocalAssign", names=[a_var], exprs=[
            _pcall(N("Paren", expr=a_fn))
        ]),
        N("LocalAssign", names=[b_var], exprs=[
            _pcall(N("Paren", expr=b_fn))
        ]),
        N("If",
          cond=N("BinOp", op="and",
                 left=name_node(a_var),
                 right=name_node(b_var)),
          body=[N("Assign", targets=[name_node(flag_name)],
                  exprs=[N("True")])],
          elifs=[], else_body=None),
    ])


def _build_decoy_selector(gen: NameGenerator, rng: random.Random,
                          flag_name: str,
                          real_value_node: Node,
                          decoy_value_node: Node) -> Node:
    """构造诱饵选择表达式：flag 为真时返回 decoy，否则返回 real。

    生成：  (flag and decoy or real)
    """
    return N("Paren", expr=N("BinOp", op="or",
        left=N("Paren", expr=N("BinOp", op="and",
            left=name_node(flag_name),
            right=decoy_value_node)),
        right=real_value_node))


def inject_anti_heuristic(chunk: Node, rng: random.Random,
                          debug: bool = False) -> dict:
    """在 Chunk 顶部注入反启发式探测块。

    返回统计 {probes, flag_name}。flag_name 供调用方/后续层引用。
    """
    gen = NameGenerator(rng)
    stats = {"probes": 0}
    body = chunk.get("body")
    prelude: list = []

    # 1. 诱导标志位（local <flag> = false）
    flag = gen.fresh()
    prelude.append(N("LocalAssign", names=[flag], exprs=[N("False")]))

    # 2. 时间差异常探测
    prelude.append(_build_time_probe(gen, rng, flag))
    stats["probes"] += 1

    # 3. debug.getinfo 高频探测
    prelude.append(_build_getinfo_probe(gen, rng, flag))
    stats["probes"] += 1

    # 4. pcall 异常捕获探测
    prelude.append(_build_pcall_probe(gen, rng, flag))
    stats["probes"] += 1

    # 5. 调试模式：隐蔽日志（pcall 包裹，绝不抛错）
    #    须用 pcall(print, msg) 形式（print 作为函数值），而非 pcall(print(msg))
    #    ——后者先调用 print 返回 nil 再 pcall(nil) 报错。
    if debug:
        prelude.append(N("Do", body=[
            N("LocalAssign", names=["_dok"], exprs=[
                call_node(name_node("pcall"),
                          [name_node("print"),
                           string_node("[obf] anti-heuristic armed")])
            ]),
        ]))

    # 把 prelude 插到最前
    for i, stmt in enumerate(prelude):
        body.insert(i, stmt)

    stats["flag_name"] = flag
    return stats


def get_decoy_selector(flag_name: str, real_value_node: Node,
                       decoy_value_node: Node) -> Node:
    """供调用方构造「flag ? decoy : real」选择表达式（不依赖 gen/rng）。"""
    return N("Paren", expr=N("BinOp", op="or",
        left=N("Paren", expr=N("BinOp", op="and",
            left=name_node(flag_name),
            right=decoy_value_node)),
        right=real_value_node))
