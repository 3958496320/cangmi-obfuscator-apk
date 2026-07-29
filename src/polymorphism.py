# -*- coding: utf-8 -*-
"""
polymorphism.py
===============
第 6 层：多态变异引擎。

对标 MoonSec 与 ComboSec。核心目标：保证「同一源码两次混淆，输出 MD5 完全不同」，
并使静态特征每次变化。

实现手段：
1. 提供强随机种子来源（os.urandom / time），供 obfuscator_core 在未指定种子时使用。
2. 在脚本顶部注入一个「多态诱饵状态机」：一个由本次构建随机常量驱动的 do-block，
   包含若干局部变量与随机运算，其字节布局每次不同。
3. 提供随机化辅助：随机选择不同的等价写法（如 nil 写成 (nil)、true 写成 (1==1)），
   供其它层调用以增加变异度。
"""

from __future__ import annotations
import os
import random
import time
from typing import Optional

from ast_parser import Node, N
from util import NameGenerator


def make_seed() -> int:
    """生成一个 64 位强随机种子。优先使用 os.urandom。"""
    b = os.urandom(8)
    seed = int.from_bytes(b, "big")
    # 混入时间，进一步降低碰撞
    seed ^= int(time.time() * 1e6) & 0xFFFFFFFF
    return seed & 0x7FFFFFFFFFFFFFFF


def build_polymorphic_decoy(rng: random.Random) -> Node:
    """构造一个多态诱饵状态机 do-block。

    内部使用本次构建随机生成的常量与名称，使得相同源码每次混淆后该块的字节
    布局完全不同。该块无副作用、不污染全局。
    """
    gen = NameGenerator(rng)
    state = gen.fresh()
    acc = gen.fresh()
    tbl = gen.fresh()
    seed_const = rng.randint(1, 0x7FFFFFFF)
    # 状态机：循环 N 次，每次用伪随机更新 state，结果存入局部表后丢弃
    body = [
        N("LocalAssign", names=[state, acc, tbl],
          exprs=[N("Number", value=str(seed_const)),
                 N("Number", value="0"),
                 N("Table", fields=[])]),
        N("NumericFor", var=gen.fresh(),
          start=N("Number", value="1"),
          limit=N("Number", value=str(rng.randint(4, 16))),
          step=None,
          body=[
              N("Assign", targets=[N("Name", name=state)],
                exprs=[N("BinOp", op="~",
                         left=N("BinOp", op="*",
                                left=N("Name", name=state),
                                right=N("Number", value="1103515245")),
                         right=N("Number", value="12345"))]),
              N("Assign", targets=[N("Name", name=acc)],
                exprs=[N("BinOp", op="+",
                         left=N("Name", name=acc),
                         right=N("BinOp", op="%",
                                  left=N("BinOp", op=">>",
                                         left=N("Name", name=state),
                                         right=N("Number", value="16")),
                                  right=N("Number", value="1000")))]),
              N("Assign",
                targets=[N("Index", obj=N("Name", name=tbl),
                           key=N("BinOp", op="%",
                                 left=N("Name", name=state),
                                 right=N("Number", value="32")))],
                exprs=[N("Name", name=acc)]),
          ]),
    ]
    return N("Do", body=body)


def inject_polymorphism(chunk: Node, rng: random.Random) -> None:
    """在 Chunk 顶部插入多态诱饵状态机。"""
    body = chunk.get("body")
    body.insert(0, build_polymorphic_decoy(rng))


def random_truthy_literal(rng: random.Random) -> Node:
    """随机返回一个等价于 true 的字面量表达式（增加变异度）。"""
    variants = [
        N("True"),
        N("Paren", expr=N("BinOp", op="==", left=N("Number", value="1"),
                          right=N("Number", value="1"))),
        N("Paren", expr=N("UnaryOp", op="not", operand=N("False"))),
    ]
    return rng.choice(variants)


def random_falsy_literal(rng: random.Random) -> Node:
    """随机返回一个等价于 false 的字面量表达式。"""
    variants = [
        N("False"),
        N("Nil"),
        N("Paren", expr=N("BinOp", op="==", left=N("Number", value="1"),
                          right=N("Number", value="2"))),
    ]
    return rng.choice(variants)
