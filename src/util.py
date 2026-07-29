# -*- coding: utf-8 -*-
"""
util.py
=======
各混淆层共享的实用工具函数：随机名称生成、字节编/解码、
AST 常见模式构造等。集中存放以避免循环依赖与重复代码。
"""

from __future__ import annotations
import random
import string as _string
from typing import Set, Optional

from ast_parser import Node, N


# ---------------------------------------------------------------------------
# 名称生成
# ---------------------------------------------------------------------------

# 首字符候选（避免数字开头）；续字符候选。刻意使用易混淆字符提升反汇编难度。
_FIRST_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_REST_CHARS = _FIRST_CHARS + "0123456789"

# 保留字与内置库，禁止用作生成的名称（防止遮蔽导致语义变化）
RESERVED = {
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while", "continue",
    "self",
}

# Roblox / Luau 常见全局，混淆后仍需可直接访问（运行时通过环境拿，不必保留原名）
GLOBAL_LIBS = {
    "print", "pairs", "ipairs", "next", "tostring", "tonumber", "select",
    "type", "typeof", "pcall", "xpcall", "error", "assert", "rawget",
    "rawset", "rawequal", "rawlen", "setmetatable", "getmetatable",
    "unpack", "require", "loadstring", "load", "setfenv", "getfenv",
    "string", "table", "math", "os", "io", "coroutine", "bit32", "task",
    "wait", "spawn", "delay", "tick", "time", "warn", "game", "workspace",
    "script", "Enum", "Instance", "Vector3", "CFrame", "Color3", "UDim2",
    "UDim", "Ray", "Region3", "TweenInfo", "BrickColor", "Random",
    "debug", "shared", "_G", "_ENV", "Drawing", "syn", "hookfunction",
    "getgenv", "getrenv", "getreg", "getloadedmodules", "loadstring",
}


class NameGenerator:
    """生成不重复的随机短标识符（长度 8~15）。

    不同作用域可实例化独立生成器，实现“不同作用域独立映射”。
    """

    def __init__(self, rng: Optional[random.Random] = None,
                 min_len: int = 8, max_len: int = 15):
        self.rng = rng or random.Random()
        self.min_len = min_len
        self.max_len = max_len
        self._used: Set[str] = set()
        # 预置保留集合，避免生成器产出冲突名
        self._used.update(RESERVED)

    def fresh(self, length: Optional[int] = None) -> str:
        """返回一个新的、未使用过的随机标识符。"""
        for _ in range(10000):
            L = length or self.rng.randint(self.min_len, self.max_len)
            name = self._rng_char(_FIRST_CHARS) + "".join(
                self._rng_char(_REST_CHARS) for _ in range(L - 1)
            )
            if name not in self._used and name not in RESERVED:
                self._used.add(name)
                return name
        # 极端情况下退化为带计数器的名称
        name = "_x" + str(len(self._used))
        self._used.add(name)
        return name

    def _rng_char(self, pool: str) -> str:
        return self.rng.choice(pool)

    def reserve(self, name: str):
        """显式占用某个名称（例如保留列表中的用户名）。"""
        self._used.add(name)

    def is_used(self, name: str) -> bool:
        return name in self._used


# ---------------------------------------------------------------------------
# 字节 <-> Lua 字符串字面量
# ---------------------------------------------------------------------------

def bytes_to_lua_literal(data: bytes) -> str:
    """将任意字节序列编码为合法 Lua 双引号字符串字面量（用 \\ddd 十进制转义）。

    这样可安全嵌入任意字节（含不可打印字符），且在所有注入器中行为一致。

    关键：所有 \\ddd 转义一律补零到 3 位（如 \\026 而非 \\26），
    否则当转义后紧跟数字字符时，Lua 会贪婪读取 3 位导致值 > 255
    （例如 \\26 后跟 '1' 会被解析为 \\261，触发 "decimal escape too large"）。
    """
    parts = ['"']
    for b in data:
        # 控制字符与引号/反斜杠一律使用 \ddd；可打印 ASCII 直接写以提升可读性
        if b == 34:        # "
            parts.append('\\"')
        elif b == 92:      # backslash
            parts.append("\\\\")
        elif 32 <= b < 127:
            parts.append(chr(b))
        else:
            # 补零到 3 位，防止后随数字被贪婪吞入
            parts.append(f"\\{b:03d}")
    parts.append('"')
    return "".join(parts)


def lua_char_byte_expr(byte: int) -> str:
    """生成单个字节的 Lua 表达式字符串（用于动态拼接场景）。"""
    return f"\\{byte & 0xFF}"


# ---------------------------------------------------------------------------
# AST 快捷构造
# ---------------------------------------------------------------------------

def name_node(name: str) -> Node:
    return N("Name", name=name)


def number_node(num) -> Node:
    return N("Number", value=str(num))


def string_node(value: str) -> Node:
    return N("String", value=value)


def call_node(func: Node, args) -> Node:
    return N("Call", func=func, args=list(args))


def index_node(obj: Node, key: Node) -> Node:
    return N("Index", obj=obj, key=key)


def local_assign(names, exprs) -> Node:
    return N("LocalAssign", names=list(names), exprs=list(exprs))


def assign(targets, exprs) -> Node:
    return N("Assign", targets=list(targets), exprs=list(exprs))


def call_stmt(expr: Node) -> Node:
    return N("CallStatement", expr=expr)


# ---------------------------------------------------------------------------
# 杂项
# ---------------------------------------------------------------------------

def count_lines(src: str) -> int:
    """统计源码行数（用于自适应引擎）。"""
    if not src:
        return 0
    return src.count("\n") + (0 if src.endswith("\n") else 1)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))
