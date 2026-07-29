# -*- coding: utf-8 -*-
"""
ast_parser.py
=============
Luau 词法分析器 + 递归下降解析器 + AST 节点 + 代码生成器。

本模块是整个混淆工具的解析层基础，负责：
1. 将 Luau 源码词法分析为 Token 流；
2. 通过递归下降解析器构建 AST（抽象语法树）；
3. 提供对所有 AST 节点的遍历与替换辅助方法；
4. 提供代码生成器，将 AST 重新序列化为合法 Luau 源码。

兼容 Lua 5.1 / 5.2 / 5.3 / Luau 常见子集，覆盖 Roblox 脚本绝大多数写法。
不依赖任何第三方库，纯 Python 实现，保证可移植性。
"""

from __future__ import annotations
import re
from typing import List, Optional, Any, Callable

# =============================================================================
# 一、Token 定义
# =============================================================================

# 关键字集合（Luau / Lua 5.1+）
KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while", "continue",
    "export", "type",  # Luau 类型相关关键字（按普通标识符处理也安全）
}


class Token:
    """单个词法 Token。"""

    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_: str, value: Any, line: int, col: int):
        # type 取值: 'keyword', 'name', 'number', 'string', 'symbol', 'eof'
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line})"


# =============================================================================
# 二、词法分析器（Lexer / Tokenizer）
# =============================================================================

# 多字符符号运算符（按长度降序匹配，保证贪婪匹配）
_MULTI_SYMBOLS = [
    "...", "..", "::", "==", "~=", "<=", ">=", "<<", ">>", "//",
    "+=", "-=", "*=", "/=", "%=", "^=", "..=",
    "->",  # Luau
    "{", "}", "(", ")", "[", "]", ";", ":", ",", ".", "+", "-",
    "*", "/", "%", "^", "#", "<", ">", "=", "&", "|", "~",
]


class LexError(Exception):
    """词法错误。"""


def tokenize(src: str) -> List[Token]:
    """将 Luau 源码切分为 Token 列表。

    支持：长括号字符串 [=[...]=]、长注释 --[==[...]==]、
    单/双引号字符串（含转义）、十六进制/十进制/浮点数、所有运算符。
    """
    tokens: List[Token] = []
    i = 0
    n = len(src)
    line = 1
    col = 1

    def advance(count: int = 1):
        nonlocal i, col, line
        for _ in range(count):
            if i < n and src[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        c = src[i]

        # 跳过空白
        if c in " \t\r\n":
            advance()
            continue

        # 注释
        if c == "-" and i + 1 < n and src[i + 1] == "-":
            # 长注释 --[[
            if i + 2 < n and src[i + 2] == "[":
                # 计算等号级别
                level = 0
                j = i + 3
                while j < n and src[j] == "=":
                    level += 1
                    j += 1
                if j < n and src[j] == "[":
                    close = "]" + "=" * level + "]"
                    start = j + 1
                    end = src.find(close, start)
                    if end == -1:
                        # 未闭合，吞到结尾
                        advance(n - i)
                        continue
                    span = end + len(close) - i
                    advance(span)
                    continue
            # 短注释：吞到行尾
            while i < n and src[i] != "\n":
                advance()
            continue

        # 长字符串 [[ ]] / [=[ ]=]
        if c == "[" and i + 1 < n and src[i + 1] in "[=":
            level = 0
            j = i + 1
            while j < n and src[j] == "=":
                level += 1
                j += 1
            if j < n and src[j] == "[":
                close = "]" + "=" * level + "]"
                start = j + 1
                end = src.find(close, start)
                if end == -1:
                    raise LexError(f"未闭合的长字符串 at line {line}")
                raw = src[start:end]
                start_line = line
                start_col = col
                advance(end + len(close) - i)
                # 去掉首个换行（Lua 长字符串约定）
                if raw.startswith("\n"):
                    raw = raw[1:]
                elif raw.startswith("\r\n"):
                    raw = raw[2:]
                tokens.append(Token("string", raw, start_line, start_col))
                continue

        # 单/双引号字符串
        if c == '"' or c == "'":
            quote = c
            start_line = line
            start_col = col
            advance()  # 跳过引号
            buf = []
            while i < n and src[i] != quote:
                if src[i] == "\\":
                    # 转义序列
                    if i + 1 < n:
                        nxt = src[i + 1]
                        if nxt == "n":
                            buf.append("\n"); advance(2)
                        elif nxt == "t":
                            buf.append("\t"); advance(2)
                        elif nxt == "r":
                            buf.append("\r"); advance(2)
                        elif nxt == "\\":
                            buf.append("\\"); advance(2)
                        elif nxt == "'":
                            buf.append("'"); advance(2)
                        elif nxt == '"':
                            buf.append('"'); advance(2)
                        elif nxt == "0":
                            buf.append("\0"); advance(2)
                        elif nxt == "a":
                            buf.append("\a"); advance(2)
                        elif nxt == "b":
                            buf.append("\b"); advance(2)
                        elif nxt == "f":
                            buf.append("\f"); advance(2)
                        elif nxt == "v":
                            buf.append("\v"); advance(2)
                        elif nxt == "x" and i + 3 < n:
                            hexs = src[i + 2:i + 4]
                            try:
                                buf.append(chr(int(hexs, 16)))
                            except ValueError:
                                buf.append("\\x")
                            advance(4)
                        elif nxt.isdigit():
                            # 十进制转义 \ddd
                            m = re.match(r"\\(\d{1,3})", src[i:i + 4])
                            if m:
                                buf.append(chr(int(m.group(1)) & 0xFF))
                                advance(len(m.group(0)))
                            else:
                                buf.append(nxt); advance(2)
                        elif nxt == "\n":
                            buf.append("\n"); advance(2)
                        else:
                            buf.append(nxt); advance(2)
                    else:
                        advance()
                elif src[i] == "\n":
                    raise LexError(f"字符串未闭合 at line {line}")
                else:
                    buf.append(src[i])
                    advance()
            advance()  # 跳过结束引号
            tokens.append(Token("string", "".join(buf), start_line, start_col))
            continue

        # 数字
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            start_line = line
            start_col = col
            j = i
            if c == "0" and i + 1 < n and src[i + 1] in "xX":
                # 十六进制
                j = i + 2
                while j < n and (src[j].isdigit() or src[j] in "abcdefABCDEF"):
                    j += 1
                # 支持十六进制小数与指数（Lua 5.3+ / Luau）
                if j < n and src[j] == ".":
                    j += 1
                    while j < n and (src[j].isdigit() or src[j] in "abcdefABCDEF"):
                        j += 1
                if j < n and src[j] in "pP":
                    j += 1
                    if j < n and src[j] in "+-":
                        j += 1
                    while j < n and src[j].isdigit():
                        j += 1
                num = src[i:j]
                advance(j - i)
                tokens.append(Token("number", num, start_line, start_col))
                continue
            else:
                # 十进制
                while j < n and src[j].isdigit():
                    j += 1
                if j < n and src[j] == ".":
                    j += 1
                    while j < n and src[j].isdigit():
                        j += 1
                if j < n and src[j] in "eE":
                    j += 1
                    if j < n and src[j] in "+-":
                        j += 1
                    while j < n and src[j].isdigit():
                        j += 1
                num = src[i:j]
                advance(j - i)
                tokens.append(Token("number", num, start_line, start_col))
                continue

        # 标识符 / 关键字
        if c.isalpha() or c == "_":
            start_line = line
            start_col = col
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            advance(j - i)
            if word in KEYWORDS:
                tokens.append(Token("keyword", word, start_line, start_col))
            else:
                tokens.append(Token("name", word, start_line, start_col))
            continue

        # 多字符 / 单字符符号
        matched = False
        for sym in _MULTI_SYMBOLS:
            if src.startswith(sym, i):
                tokens.append(Token("symbol", sym, line, col))
                advance(len(sym))
                matched = True
                break
        if matched:
            continue

        raise LexError(f"未知字符 {c!r} at line {line} col {col}")

    tokens.append(Token("eof", None, line, col))
    return tokens


# =============================================================================
# 三、AST 节点定义
# =============================================================================

class Node:
    """AST 节点基类。所有节点用 type 字符串区分，attrs 存属性。"""

    def __init__(self, type_: str, **attrs):
        self.type = type_
        self.attrs = attrs

    def __repr__(self):
        return f"Node({self.type!r}, {self.attrs!r})"

    def get(self, key, default=None):
        return self.attrs.get(key, default)


def N(type_: str, **attrs) -> Node:
    """快捷构造 AST 节点。"""
    return Node(type_, **attrs)


# =============================================================================
# 四、递归下降解析器（Parser）
# =============================================================================

class ParseError(Exception):
    """语法解析错误。"""


class Parser:
    """Luau 递归下降解析器，遵循 Lua 5.1 文法并兼容 Luau 扩展。"""

    # 二元运算符优先级表（左结合优先级, 右结合优先级）
    # 越大越优先；右结合运算符（如 ^, ..）左右不同
    BINOP_PRIORITY = {
        "or": (1, 1),
        "and": (2, 2),
        "<": (3, 3), ">": (3, 3), "<=": (3, 3), ">=": (3, 3),
        "==": (3, 3), "~=": (3, 3),
        "|": (4, 4), "~": (5, 5), "&": (6, 6),
        "<<": (7, 7), ">>": (7, 7),
        "..": (9, 8),   # 右结合
        "+": (10, 10), "-": (10, 10),
        "*": (11, 11), "/": (11, 11), "//": (11, 11), "%": (11, 11),
        "^": (14, 13),  # 右结合
    }

    UNARY_PRIORITY = 12

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---- Token 流辅助 ----
    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def cur(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        t = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return t

    def check(self, type_: str, value: Any = None) -> bool:
        t = self.cur()
        if t.type != type_:
            return False
        if value is not None and t.value != value:
            return False
        return True

    def accept(self, type_: str, value: Any = None) -> Optional[Token]:
        if self.check(type_, value):
            return self.next()
        return None

    def expect(self, type_: str, value: Any = None) -> Token:
        if not self.check(type_, value):
            t = self.cur()
            raise ParseError(
                f"期望 {type_} {value!r}，实际得到 {t.type} {t.value!r} at line {t.line}"
            )
        return self.next()

    # ---- 顶层解析 ----
    def parse(self) -> Node:
        """解析整段源码，返回 Chunk 节点。"""
        body = self.parse_block()
        self.expect("eof")
        return N("Chunk", body=body)

    def parse_block(self) -> List[Node]:
        """解析语句块，返回语句列表。"""
        stmts: List[Node] = []
        while not self.is_block_end():
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
                if stmt.type == "Return":
                    break
        return stmts

    def is_block_end(self) -> bool:
        """判断当前是否到达块结束（end/else/elseif/until/eof）。"""
        t = self.cur()
        if t.type == "eof":
            return True
        if t.type == "keyword" and t.value in ("end", "else", "elseif", "until"):
            return True
        return False

    # ---- 语句解析 ----
    def parse_statement(self) -> Optional[Node]:
        t = self.cur()
        if t.type == "symbol" and t.value == ";":
            self.next()
            return None
        if t.type == "keyword":
            v = t.value
            if v == "if":
                return self.parse_if()
            if v == "while":
                return self.parse_while()
            if v == "do":
                return self.parse_do()
            if v == "for":
                return self.parse_for()
            if v == "repeat":
                return self.parse_repeat()
            if v == "function":
                return self.parse_function()
            if v == "local":
                return self.parse_local()
            if v == "return":
                return self.parse_return()
            if v == "break":
                self.next()
                return N("Break")
            if v == "continue":
                self.next()
                return N("Continue")
            if v == "goto":
                self.next()
                label = self.expect("name").value
                return N("Goto", label=label)
        # Luau 类型声明 type T = ... / export type T = ... -> 跳过到 end/换行
        if t.type == "name" and t.value in ("type", "export") and \
                self.peek(1).type == "name" and self.peek(1).value == "type" if t.value == "export" else \
                (t.value == "type" and self.peek(1).type == "name"):
            return self.parse_type_decl()
        if t.type == "symbol" and t.value == "::":
            # 标签 ::label::
            self.next()
            label = self.expect("name").value
            self.expect("symbol", "::")
            return N("Label", label=label)
        # 表达式语句（赋值 / 函数调用）
        return self.parse_expr_statement()

    def parse_type_decl(self) -> Node:
        """跳过 Luau 类型声明（type/export type），不参与混淆。"""
        start_line = self.cur().line
        # 吞掉到行尾或遇到等号后的内容结束（简化处理：吞到行尾的非延续处）
        # 这里采用：吞到下一个语句边界（即遇到顶层的新语句起始或块结束）
        # 简化：吞掉该行剩余 token（类型声明通常单行）
        depth = 0
        while not self.is_block_end():
            t = self.cur()
            if t.type == "eof":
                break
            if t.type == "symbol" and t.value == "{":
                depth += 1
            elif t.type == "symbol" and t.value == "}":
                depth -= 1
            self.next()
            # 简单地：当 depth<=0 且遇到换行后的关键字起始时停止
            if depth <= 0 and t.type in ("keyword",) and t.value not in ("type",):
                break
        return N("NoOp")

    def parse_if(self) -> Node:
        self.expect("keyword", "if")
        cond = self.parse_expr()
        self.expect("keyword", "then")
        body = self.parse_block()
        elifs: List[tuple] = []
        else_body: Optional[List[Node]] = None
        while self.check("keyword", "elseif"):
            self.next()
            ec = self.parse_expr()
            self.expect("keyword", "then")
            eb = self.parse_block()
            elifs.append((ec, eb))
        if self.accept("keyword", "else"):
            else_body = self.parse_block()
        self.expect("keyword", "end")
        return N("If", cond=cond, body=body, elifs=elifs, else_body=else_body)

    def parse_while(self) -> Node:
        self.expect("keyword", "while")
        cond = self.parse_expr()
        self.expect("keyword", "do")
        body = self.parse_block()
        self.expect("keyword", "end")
        return N("While", cond=cond, body=body)

    def parse_do(self) -> Node:
        self.expect("keyword", "do")
        body = self.parse_block()
        self.expect("keyword", "end")
        return N("Do", body=body)

    def parse_repeat(self) -> Node:
        self.expect("keyword", "repeat")
        body = self.parse_block()
        self.expect("keyword", "until")
        cond = self.parse_expr()
        return N("Repeat", body=body, cond=cond)

    def parse_for(self) -> Node:
        self.expect("keyword", "for")
        first_name = self.expect("name").value
        if self.accept("symbol", "="):
            # numeric for: for var = start, limit [, step] do ... end
            start = self.parse_expr()
            self.expect("symbol", ",")
            limit = self.parse_expr()
            step = None
            if self.accept("symbol", ","):
                step = self.parse_expr()
            self.expect("keyword", "do")
            body = self.parse_block()
            self.expect("keyword", "end")
            return N("NumericFor", var=first_name, start=start, limit=limit,
                     step=step, body=body)
        else:
            # generic for: for a, b, c in exprs do ... end
            names = [first_name]
            while self.accept("symbol", ","):
                names.append(self.expect("name").value)
            self.expect("keyword", "in")
            exprs = [self.parse_expr()]
            while self.accept("symbol", ","):
                exprs.append(self.parse_expr())
            self.expect("keyword", "do")
            body = self.parse_block()
            self.expect("keyword", "end")
            return N("GenericFor", names=names, exprs=exprs, body=body)

    def parse_function(self) -> Node:
        self.expect("keyword", "function")
        # 函数名可能是 a.b.c:d 形式
        name = self.parse_funcname()
        func = self.parse_funcbody()
        return N("FunctionDecl", name=name, func=func)

    def parse_funcname(self) -> Node:
        """解析函数声明名（支持 a.b.c:method）。返回 Name/Index/MethodCall 结构。

        注意：Index 的 key（字段名 String）标记 _no_encrypt=True，禁止字符串
        加密层处理。原因：gen_funcname 直接读取 key.value 生成 `obj.field` 语法，
        若 key 被加密为 Call 节点，gen_funcname 取不到 value 会输出 "None"。
        """
        base = self.expect("name").value
        node = N("Name", name=base)
        while self.accept("symbol", "."):
            field = self.expect("name").value
            key = N("String", value=field)
            key.attrs["_no_encrypt"] = True  # 声明字段名，不可加密
            node = N("Index", obj=node, key=key)
        if self.accept("symbol", ":"):
            method = self.expect("name").value
            node = N("MethodName", obj=node, method=method)
        return node

    def parse_local(self) -> Node:
        self.expect("keyword", "local")
        if self.accept("keyword", "function"):
            name = self.expect("name").value
            func = self.parse_funcbody()
            return N("LocalFunction", name=name, func=func)
        # local name1, name2 = expr1, expr2
        names = [self.expect("name").value]
        # Luau 类型注解 :: 跳过
        while self.peek().type == "symbol" and self.peek().value == ":":
            self.next()
            self.skip_type_annotation()
        while self.accept("symbol", ","):
            names.append(self.expect("name").value)
            while self.peek().type == "symbol" and self.peek().value == ":":
                self.next()
                self.skip_type_annotation()
        exprs: List[Node] = []
        if self.accept("symbol", "="):
            exprs.append(self.parse_expr())
            while self.accept("symbol", ","):
                exprs.append(self.parse_expr())
        return N("LocalAssign", names=names, exprs=exprs)

    def skip_type_annotation(self):
        """跳过 Luau 类型注解（如 : string, : number?, : {string}, : (a)->b）。"""
        depth = 0
        while True:
            t = self.cur()
            if t.type == "eof":
                return
            if t.type == "symbol" and t.value in ("=", ","):
                if depth <= 0:
                    return
            if t.type == "symbol" and t.value in ("(", "{", "[", "<"):
                depth += 1
            elif t.type == "symbol" and t.value in (")", "}", "]", ">"):
                depth -= 1
                if depth < 0:
                    return
            elif t.type == "keyword" and t.value in ("do", "then", "in"):
                return
            elif t.type == "symbol" and t.value == ";":
                return
            self.next()

    def parse_return(self) -> Node:
        self.expect("keyword", "return")
        exprs: List[Node] = []
        t = self.cur()
        if not self.is_block_end() and not (t.type == "symbol" and t.value == ";"):
            exprs.append(self.parse_expr())
            while self.accept("symbol", ","):
                exprs.append(self.parse_expr())
        self.accept("symbol", ";")
        return N("Return", exprs=exprs)

    def parse_expr_statement(self) -> Node:
        """表达式语句：赋值或函数调用。"""
        expr = self.parse_suffixed_expr()
        if self.check("symbol", "=") or self.check("symbol", ","):
            # 赋值
            targets = [expr]
            while self.accept("symbol", ","):
                targets.append(self.parse_suffixed_expr())
            self.expect("symbol", "=")
            # 复合赋值 += 等 -> 拆解为普通赋值
            t = self.cur()
            if t.type == "symbol" and t.value in ("+=", "-=", "*=", "/=", "%=", "^=", "..="):
                op = t.value[0]
                if t.value == "..=":
                    op = ".."
                self.next()
                rhs = self.parse_expr()
                # target = target op rhs
                exprs = [N("BinOp", op=op, left=expr, right=rhs)]
                return N("Assign", targets=targets, exprs=exprs)
            exprs = [self.parse_expr()]
            while self.accept("symbol", ","):
                exprs.append(self.parse_expr())
            return N("Assign", targets=targets, exprs=exprs)
        # 必须是函数调用
        if expr.type not in ("Call", "MethodCall"):
            raise ParseError(f"语句应为函数调用 at line {self.cur().line}")
        return N("CallStatement", expr=expr)

    # ---- 表达式解析 ----
    def parse_expr(self) -> Node:
        return self.parse_binop_expr(0)

    def parse_binop_expr(self, limit: int) -> Node:
        # 一元前缀
        left = self.parse_unary_expr()
        while True:
            t = self.cur()
            op = None
            if t.type == "keyword" and t.value in ("and", "or"):
                op = t.value
            elif t.type == "symbol" and t.value in self.BINOP_PRIORITY:
                op = t.value
            if op is None:
                break
            lprio, rprio = self.BINOP_PRIORITY[op]
            if lprio <= limit:
                break
            self.next()
            right = self.parse_binop_expr(rprio)
            left = N("BinOp", op=op, left=left, right=right)
        return left

    def parse_unary_expr(self) -> Node:
        t = self.cur()
        if t.type == "keyword" and t.value == "not":
            self.next()
            operand = self.parse_binop_expr(self.UNARY_PRIORITY)
            return N("UnaryOp", op="not", operand=operand)
        if t.type == "symbol" and t.value in ("-", "#", "~"):
            self.next()
            operand = self.parse_binop_expr(self.UNARY_PRIORITY)
            return N("UnaryOp", op=t.value, operand=operand)
        return self.parse_suffixed_expr()

    def parse_suffixed_expr(self) -> Node:
        """带后缀的表达式：.field / [key] / (args) / :method(args)。"""
        expr = self.parse_primary_expr()
        while True:
            t = self.cur()
            if t.type == "symbol" and t.value == ".":
                self.next()
                field = self.expect("name").value
                expr = N("Index", obj=expr, key=N("String", value=field))
            elif t.type == "symbol" and t.value == "[":
                self.next()
                key = self.parse_expr()
                self.expect("symbol", "]")
                expr = N("Index", obj=expr, key=key)
            elif t.type == "symbol" and t.value == ":":
                self.next()
                method = self.expect("name").value
                args = self.parse_call_args()
                expr = N("MethodCall", obj=expr, method=method, args=args)
            elif t.type == "symbol" and t.value in ("(", "{", "string"):
                args = self.parse_call_args()
                expr = N("Call", func=expr, args=args)
            elif t.type == "string":
                # f"str" 形式调用
                arg = N("String", value=t.value)
                self.next()
                expr = N("Call", func=expr, args=[arg])
            elif t.type == "symbol" and t.value == "{":
                arg = self.parse_table()
                expr = N("Call", func=expr, args=[arg])
            else:
                break
        return expr

    def parse_call_args(self) -> List[Node]:
        t = self.cur()
        if t.type == "symbol" and t.value == "(":
            self.next()
            args: List[Node] = []
            if not self.check("symbol", ")"):
                args.append(self.parse_expr())
                while self.accept("symbol", ","):
                    args.append(self.parse_expr())
            self.expect("symbol", ")")
            return args
        if t.type == "string":
            s = N("String", value=t.value)
            self.next()
            return [s]
        if t.type == "symbol" and t.value == "{":
            return [self.parse_table()]
        raise ParseError(f"函数调用参数错误 at line {t.line}")

    def parse_primary_expr(self) -> Node:
        t = self.cur()
        if t.type == "keyword":
            if t.value == "nil":
                self.next(); return N("Nil")
            if t.value == "true":
                self.next(); return N("True")
            if t.value == "false":
                self.next(); return N("False")
            if t.value == "function":
                self.next()
                return self.parse_funcbody()
        if t.type == "number":
            self.next(); return N("Number", value=t.value)
        if t.type == "string":
            self.next(); return N("String", value=t.value)
        if t.type == "name":
            self.next(); return N("Name", name=t.value)
        if t.type == "symbol" and t.value == "...":
            self.next(); return N("Vararg")
        if t.type == "symbol" and t.value == "(":
            self.next()
            expr = self.parse_expr()
            self.expect("symbol", ")")
            return N("Paren", expr=expr)
        if t.type == "symbol" and t.value == "{":
            return self.parse_table()
        raise ParseError(f"意外的 Token {t.type} {t.value!r} at line {t.line}")

    def parse_table(self) -> Node:
        """解析表构造器 { ... }。"""
        self.expect("symbol", "{")
        fields: List[Node] = []
        while not self.check("symbol", "}"):
            if self.check("symbol", "["):
                self.next()
                key = self.parse_expr()
                self.expect("symbol", "]")
                self.expect("symbol", "=")
                val = self.parse_expr()
                fields.append(N("TableField", key=key, value=val))
            elif self.check("name") and self.peek(1).type == "symbol" and self.peek(1).value == "=":
                key = N("String", value=self.next().value)
                self.next()  # =
                val = self.parse_expr()
                fields.append(N("TableField", key=key, value=val))
            else:
                val = self.parse_expr()
                fields.append(N("TableItem", value=val))
            if not (self.accept("symbol", ",") or self.accept("symbol", ";")):
                break
        self.expect("symbol", "}")
        return N("Table", fields=fields)

    def parse_funcbody(self) -> Node:
        """解析函数体 (params) ... body end。"""
        self.expect("symbol", "(")
        params: List[str] = []
        is_vararg = False
        if not self.check("symbol", ")"):
            while True:
                if self.check("symbol", "..."):
                    self.next()
                    is_vararg = True
                    break
                pname = self.expect("name").value
                params.append(pname)
                # 跳过类型注解
                if self.peek().type == "symbol" and self.peek().value == ":":
                    self.next()
                    self.skip_type_annotation()
                if self.accept("symbol", "..."):
                    is_vararg = True
                    break
                if not self.accept("symbol", ","):
                    break
        self.expect("symbol", ")")
        # 跳过返回类型注解 : ...
        if self.peek().type == "symbol" and self.peek().value == ":":
            self.next()
            self.skip_type_annotation()
        body = self.parse_block()
        self.expect("keyword", "end")
        return N("Function", params=params, is_vararg=is_vararg, body=body)


def parse_source(src: str) -> Node:
    """完整解析 Luau 源码，返回 Chunk AST。"""
    tokens = tokenize(src)
    parser = Parser(tokens)
    return parser.parse()


# =============================================================================
# 五、AST 遍历辅助
# =============================================================================

def walk(node: Node, visitor: Callable[[Node], None]):
    """深度优先遍历 AST，对每个节点调用 visitor。"""
    if node is None:
        return
    visitor(node)
    for key, val in list(node.attrs.items()):
        if isinstance(val, Node):
            walk(val, visitor)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, Node):
                    walk(item, visitor)
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, Node):
                            walk(sub, visitor)


def transform(node: Node, fn: Callable[[Node], Node]) -> Node:
    """后序变换：先递归变换子节点，再用 fn 变换当前节点。

    fn 返回新节点（或原节点）。子节点若为 Node/list，会就地替换为变换结果。
    """
    if node is None:
        return None
    # 先递归子节点
    for key, val in list(node.attrs.items()):
        if isinstance(val, Node):
            node.attrs[key] = transform(val, fn)
        elif isinstance(val, list):
            new_list = []
            for item in val:
                if isinstance(item, Node):
                    new_list.append(transform(item, fn))
                elif isinstance(item, tuple):
                    new_tuple = tuple(
                        transform(sub, fn) if isinstance(sub, Node) else sub
                        for sub in item
                    )
                    new_list.append(new_tuple)
                else:
                    new_list.append(item)
            node.attrs[key] = new_list
    return fn(node)


def collect_strings(node: Node) -> List[tuple]:
    """收集所有字符串字面量节点（用于字符串加密层）。返回 (node, ) 列表。"""
    result: List[Node] = []

    def visit(n: Node):
        if n.type == "String":
            result.append(n)

    walk(node, visit)
    return result


# =============================================================================
# 六、代码生成器（AST -> Luau 源码）
# =============================================================================

class CodeGenerator:
    """将 AST 重新序列化为合法 Luau 源码。"""

    def __init__(self, indent_str: str = "    "):
        self.indent_str = indent_str
        self.depth = 0

    def generate(self, node: Node) -> str:
        """生成整段代码。"""
        if node.type != "Chunk":
            raise ValueError(f"顶层节点应为 Chunk，实际 {node.type}")
        return self.gen_block(node.get("body"))

    def gen_block(self, stmts: List[Node]) -> str:
        parts = []
        for s in stmts:
            if s.type == "NoOp":
                continue
            parts.append(self.gen_stmt(s))
        return "".join(parts)

    def indent(self) -> str:
        return self.indent_str * self.depth

    def gen_stmt(self, node: Node) -> str:
        t = node.type
        pad = self.indent()
        if t == "LocalAssign":
            names = ", ".join(node.get("names"))
            exprs = node.get("exprs")
            if exprs:
                return f"{pad}local {names} = {', '.join(self.gen_expr(e) for e in exprs)}\n"
            return f"{pad}local {names}\n"
        if t == "Assign":
            targets = ", ".join(self.gen_expr(x) for x in node.get("targets"))
            exprs = ", ".join(self.gen_expr(e) for e in node.get("exprs"))
            return f"{pad}{targets} = {exprs}\n"
        if t == "CallStatement":
            return f"{pad}{self.gen_expr(node.get('expr'))}\n"
        if t == "Do":
            body = node.get("body")
            self.depth += 1
            inner = self.gen_block(body)
            self.depth -= 1
            return f"{pad}do\n{inner}{pad}end\n"
        if t == "While":
            cond = self.gen_expr(node.get("cond"))
            self.depth += 1
            body = self.gen_block(node.get("body"))
            self.depth -= 1
            return f"{pad}while {cond} do\n{body}{pad}end\n"
        if t == "Repeat":
            self.depth += 1
            body = self.gen_block(node.get("body"))
            self.depth -= 1
            cond = self.gen_expr(node.get("cond"))
            return f"{pad}repeat\n{body}{pad}until {cond}\n"
        if t == "If":
            cond = self.gen_expr(node.get("cond"))
            self.depth += 1
            body = self.gen_block(node.get("body"))
            self.depth -= 1
            out = f"{pad}if {cond} then\n{body}"
            for ec, eb in node.get("elifs"):
                self.depth += 1
                ebody = self.gen_block(eb)
                self.depth -= 1
                out += f"{pad}elseif {self.gen_expr(ec)} then\n{ebody}"
            eb = node.get("else_body")
            if eb is not None:
                self.depth += 1
                ebody = self.gen_block(eb)
                self.depth -= 1
                out += f"{pad}else\n{ebody}"
            out += f"{pad}end\n"
            return out
        if t == "NumericFor":
            var = node.get("var")
            start = self.gen_expr(node.get("start"))
            limit = self.gen_expr(node.get("limit"))
            step = node.get("step")
            head = f"{pad}for {var} = {start}, {limit}"
            if step is not None:
                head += f", {self.gen_expr(step)}"
            self.depth += 1
            body = self.gen_block(node.get("body"))
            self.depth -= 1
            return f"{head} do\n{body}{pad}end\n"
        if t == "GenericFor":
            names = ", ".join(node.get("names"))
            exprs = ", ".join(self.gen_expr(e) for e in node.get("exprs"))
            self.depth += 1
            body = self.gen_block(node.get("body"))
            self.depth -= 1
            return f"{pad}for {names} in {exprs} do\n{body}{pad}end\n"
        if t == "FunctionDecl":
            name = self.gen_funcname(node.get("name"))
            func = self.gen_funcbody(node.get("func"))
            return f"{pad}function {name}{func}\n"
        if t == "LocalFunction":
            name = node.get("name")
            func = self.gen_funcbody(node.get("func"))
            return f"{pad}local function {name}{func}\n"
        if t == "Return":
            exprs = node.get("exprs")
            if exprs:
                return f"{pad}return {', '.join(self.gen_expr(e) for e in exprs)}\n"
            return f"{pad}return\n"
        if t == "Break":
            return f"{pad}break\n"
        if t == "Continue":
            return f"{pad}continue\n"
        if t == "Goto":
            return f"{pad}goto {node.get('label')}\n"
        if t == "Label":
            return f"{pad}::{node.get('label')}::\n"
        if t == "NoOp":
            return ""
        # 未知语句类型降级为空
        return ""

    def gen_funcname(self, node: Node) -> str:
        if node.type == "Name":
            return node.get("name")
        if node.type == "Index":
            return f"{self.gen_funcname(node.get('obj'))}.{node.get('key').get('value')}"
        if node.type == "MethodName":
            return f"{self.gen_funcname(node.get('obj'))}:{node.get('method')}"
        return ""

    def gen_funcbody(self, node: Node) -> str:
        params = node.get("params")
        is_vararg = node.get("is_vararg")
        param_str = ", ".join(params)
        if is_vararg:
            param_str = param_str + ", ..." if params else "..."
        self.depth += 1
        body = self.gen_block(node.get("body"))
        self.depth -= 1
        return f"({param_str})\n{body}{self.indent()}end"

    def gen_expr(self, node: Node) -> str:
        t = node.type
        if t == "Nil":
            return "nil"
        if t == "True":
            return "true"
        if t == "False":
            return "false"
        if t == "Number":
            return str(node.get("value"))
        if t == "String":
            # _verbatim 标记：value 已是完整的字面量（含引号与转义），原样输出
            if node.attrs.get("_verbatim"):
                return node.get("value")
            return self.gen_string(node.get("value"))
        if t == "Vararg":
            return "..."
        if t == "Name":
            return node.get("name")
        if t == "Paren":
            return f"({self.gen_expr(node.get('expr'))})"
        if t == "Index":
            obj = self.gen_expr(node.get("obj"))
            key = node.get("key")
            if key.type == "String" and self.is_valid_ident(key.get("value")):
                return f"{obj}.{key.get('value')}"
            return f"{obj}[{self.gen_expr(key)}]"
        if t == "Function":
            return "function " + self.gen_funcbody(node).lstrip()
        if t == "Table":
            return self.gen_table(node)
        if t == "BinOp":
            left = self.gen_expr(node.get("left"))
            right = self.gen_expr(node.get("right"))
            op = node.get("op")
            # 对字符串连接与某些运算符加括号保护优先级
            left = self.wrap_if_needed(node.get("left"), left, op, True)
            right = self.wrap_if_needed(node.get("right"), right, op, False)
            return f"{left} {op} {right}"
        if t == "UnaryOp":
            op = node.get("op")
            operand = self.gen_expr(node.get("operand"))
            if node.get("operand").type in ("BinOp",):
                operand = f"({operand})"
            if op == "not":
                return f"not {operand}"
            return f"{op}{operand}"
        if t == "Call":
            func = self.gen_expr(node.get("func"))
            args = ", ".join(self.gen_expr(a) for a in node.get("args"))
            return f"{func}({args})"
        if t == "MethodCall":
            obj = self.gen_expr(node.get("obj"))
            method = node.get("method")
            args = ", ".join(self.gen_expr(a) for a in node.get("args"))
            return f"{obj}:{method}({args})"
        return ""

    def wrap_if_needed(self, node: Node, text: str, op: str, is_left: bool) -> str:
        """根据优先级判断是否需要给子表达式加括号（保守处理：BinOp 一律加括号）。"""
        if node.type == "BinOp":
            return f"({text})"
        return text

    def gen_table(self, node: Node) -> str:
        fields = node.get("fields")
        if not fields:
            return "{}"
        parts = []
        for f in fields:
            if f.type == "TableField":
                key = f.get("key")
                val = self.gen_expr(f.get("value"))
                if key.type == "String" and self.is_valid_ident(key.get("value")):
                    parts.append(f"{key.get('value')} = {val}")
                else:
                    parts.append(f"[{self.gen_expr(key)}] = {val}")
            else:
                parts.append(self.gen_expr(f.get("value")))
        return "{" + ", ".join(parts) + "}"

    def is_valid_ident(self, s: str) -> bool:
        """判断字符串是否为合法标识符（用于决定 a.b 还是 a["b"]）。"""
        if not s:
            return False
        if not (s[0].isalpha() or s[0] == "_"):
            return False
        return all(c.isalnum() or c == "_" for c in s)

    def gen_string(self, value: str) -> str:
        """生成字符串字面量，优先用双引号并转义特殊字符。"""
        out = ['"']
        for ch in value:
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ord(ch) < 32:
                out.append(f"\\{ord(ch)}")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)


def generate_code(node: Node) -> str:
    """便捷入口：AST -> Luau 源码。"""
    return CodeGenerator().generate(node)


# =============================================================================
# 七、便捷入口
# =============================================================================

def parse_and_generate(src: str) -> str:
    """解析再生成（用于验证 round-trip 正确性）。"""
    return generate_code(parse_source(src))
