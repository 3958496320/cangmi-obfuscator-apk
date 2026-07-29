# -*- coding: utf-8 -*-
"""
renamer.py
==========
第 2 层：变量 / 函数 / 表字段彻底重命名。

核心策略（保证 100% 兼容、零崩溃）：
- 基于「词法作用域分析」精确解析每个名字引用所属的作用域。
- 仅重命名 **局部变量**（local / 参数 / for 变量 / local function）——这是绝对安全的。
- 额外重命名 **顶层简单名全局**（`function Foo()` / `Foo = ...`），
  但严格排除：
    * 内置库 / Roblox API（GLOBAL_LIBS、RESERVED）；
    * 通过 `_G.name` / `getfenv()` 动态访问的名字（无法安全重命名）；
    * 用户 --reserve 指定的名字。
- 不同作用域使用独立 NameGenerator，同名变量在不同作用域得到不同新名。
- 表字段访问（a.field）不在此层重命名——第 1 层字符串加密已将其转为
  a[_S("field")]，已充分混淆且绝对安全。
"""

from __future__ import annotations
import random
from typing import Optional, Set, Dict, List

from ast_parser import Node, N, walk
from util import NameGenerator, RESERVED, GLOBAL_LIBS


class Scope:
    """词法作用域。"""

    def __init__(self, parent: Optional["Scope"], rng: random.Random,
                 is_root: bool = False):
        self.parent = parent
        self.rng = rng
        self.is_root = is_root
        # old_name -> new_name（仅本作用域内声明的局部）
        self.decls: Dict[str, str] = {}
        # 根作用域拥有独立生成器；非根作用域也各自拥有（实现“独立映射”）
        self.gen = NameGenerator(rng)

    def declare(self, name: str, force: bool = False) -> str:
        """在本作用域声明一个局部，返回新名。若已声明则返回既有新名。"""
        if name in self.decls:
            return self.decls[name]
        new = self.gen.fresh()
        self.decls[name] = new
        return new

    def resolve(self, name: str) -> Optional[str]:
        """沿作用域链解析名字，返回新名；未找到返回 None（表示全局/外部）。"""
        s: Optional[Scope] = self
        while s is not None:
            if name in s.decls:
                return s.decls[name]
            s = s.parent
        return None


class Renamer:
    """作用域感知的改名器。"""

    def __init__(self, rng: random.Random,
                 reserve_names: Optional[Set[str]] = None):
        self.rng = rng
        self.reserve = set(RESERVED) | set(GLOBAL_LIBS)
        if reserve_names:
            self.reserve |= reserve_names
        # 通过 _G.xxx / getfenv()["xxx"] 动态访问的全局名集合（不可安全改名）
        self.dynamic_globals: Set[str] = set()
        self.root = Scope(None, rng, is_root=True)

    # ------------------------------------------------------------------
    # Pass 1：预扫描——收集顶层全局声明 & 动态访问的全局名
    # ------------------------------------------------------------------
    def prescan(self, chunk: Node):
        body: List[Node] = chunk.get("body")

        def scan_dynamic(n: Node):
            """检测 _G.name / getfenv().name / getfenv()["name"] 模式。"""
            if n.type == "Index":
                obj = n.get("obj")
                key = n.get("key")
                # _G.name
                if obj.type == "Name" and obj.get("name") in ("_G", "_ENV", "shared", "getgenv", "getrenv"):
                    if key.type == "String":
                        self.dynamic_globals.add(key.get("value"))
                # getfenv().name  —— getfenv() 作为 Call 出现在 obj
                if obj.type == "Call":
                    f = obj.get("func")
                    if f.type == "Name" and f.get("name") == "getfenv":
                        if key.type == "String":
                            self.dynamic_globals.add(key.get("value"))

        # 先全树扫描动态访问
        walk(chunk, scan_dynamic)

        # 顶层全局声明收集
        for stmt in body:
            self._collect_top_global(stmt)

    def _collect_top_global(self, stmt: Node):
        """仅处理顶层语句中的全局声明。"""
        if stmt.type == "FunctionDecl":
            name_node = stmt.get("name")
            if name_node.type == "Name":
                nm = name_node.get("name")
                if self._eligible_global(nm):
                    self.root.decls[nm] = self.root.gen.fresh()
        elif stmt.type == "Assign":
            # Name = ... (顶层全局赋值)
            for tgt in stmt.get("targets"):
                if tgt.type == "Name":
                    nm = tgt.get("name")
                    if self._eligible_global(nm):
                        self.root.decls[nm] = self.root.gen.fresh()

    def _eligible_global(self, name: str) -> bool:
        """判断一个全局名是否可安全重命名。"""
        if name in self.reserve:
            return False
        if name in self.dynamic_globals:
            return False
        return True

    # ------------------------------------------------------------------
    # Pass 2：带作用域的遍历与改写
    # ------------------------------------------------------------------
    def rewrite(self, chunk: Node):
        self._rewrite_block(chunk.get("body"), self.root)

    def _rewrite_block(self, stmts: List[Node], scope: Scope):
        for stmt in stmts:
            self._rewrite_stmt(stmt, scope)

    def _rewrite_stmt(self, node: Node, scope: Scope):
        t = node.type
        if t == "LocalAssign":
            # 先计算右侧表达式（在旧名可见的作用域下），再声明新局部
            for e in node.get("exprs"):
                self._rewrite_expr(e, scope)
            new_names = []
            for nm in node.get("names"):
                if nm == "self" or nm in self.reserve:
                    new_names.append(nm)
                    # 仍占用，避免后续局部撞名
                    scope.gen.reserve(nm)
                    continue
                new_names.append(scope.declare(nm))
            node.attrs["names"] = new_names
            return
        if t == "LocalFunction":
            nm = node.get("name")
            if nm == "self" or nm in self.reserve:
                node.gen_reserve = True  # noop 标记
            else:
                # 先在当前作用域声明（保证函数体内可递归引用）
                new = scope.declare(nm)
                node.attrs["name"] = new
            func = node.get("func")
            self._rewrite_function(func, scope)
            return
        if t == "FunctionDecl":
            # 改写函数名引用（可能是 Name / Index / MethodName）
            name_node = node.get("name")
            self._rewrite_funcname(name_node, scope)
            self._rewrite_function(node.get("func"), Scope(scope, self.rng))
            return
        if t == "Assign":
            for e in node.get("exprs"):
                self._rewrite_expr(e, scope)
            for tgt in node.get("targets"):
                self._rewrite_expr(tgt, scope)
            return
        if t == "CallStatement":
            self._rewrite_expr(node.get("expr"), scope)
            return
        if t == "Return":
            for e in node.get("exprs"):
                self._rewrite_expr(e, scope)
            return
        if t == "Do":
            self._rewrite_block(node.get("body"), Scope(scope, self.rng))
            return
        if t == "While":
            self._rewrite_expr(node.get("cond"), scope)
            self._rewrite_block(node.get("body"), Scope(scope, self.rng))
            return
        if t == "Repeat":
            # repeat-until：until 条件可见 body 内的 local
            inner = Scope(scope, self.rng)
            self._rewrite_block(node.get("body"), inner)
            self._rewrite_expr(node.get("cond"), inner)
            return
        if t == "If":
            self._rewrite_expr(node.get("cond"), scope)
            self._rewrite_block(node.get("body"), Scope(scope, self.rng))
            for ec, eb in node.get("elifs"):
                self._rewrite_expr(ec, scope)
                self._rewrite_block(eb, Scope(scope, self.rng))
            eb = node.get("else_body")
            if eb is not None:
                self._rewrite_block(eb, Scope(scope, self.rng))
            return
        if t == "NumericFor":
            inner = Scope(scope, self.rng)
            # start/limit/step 在外层作用域求值
            self._rewrite_expr(node.get("start"), scope)
            self._rewrite_expr(node.get("limit"), scope)
            step = node.get("step")
            if step is not None:
                self._rewrite_expr(step, scope)
            var = node.get("var")
            if var != "self" and var not in self.reserve:
                inner.declare(var)  # 登记新名
            # 重写 var 字段为新名
            new_var = inner.resolve(var) or var
            node.attrs["var"] = new_var
            self._rewrite_block(node.get("body"), inner)
            return
        if t == "GenericFor":
            inner = Scope(scope, self.rng)
            for e in node.get("exprs"):
                self._rewrite_expr(e, scope)
            new_names = []
            for nm in node.get("names"):
                if nm == "self" or nm in self.reserve:
                    new_names.append(nm)
                    inner.gen.reserve(nm)
                else:
                    new_names.append(inner.declare(nm))
            node.attrs["names"] = new_names
            self._rewrite_block(node.get("body"), inner)
            return
        if t in ("Break", "Continue", "Goto", "Label", "NoOp"):
            return
        # 兜底：遍历其子节点
        self._rewrite_children(node, scope)

    def _rewrite_function(self, func: Node, parent_scope: Scope):
        """改写函数体。func 必须是 Function 节点。新建函数作用域。"""
        fscope = Scope(parent_scope, self.rng)
        # 声明参数
        new_params = []
        for p in func.get("params"):
            if p == "self" or p in self.reserve:
                new_params.append(p)
                fscope.gen.reserve(p)
            else:
                new_params.append(fscope.declare(p))
        func.attrs["params"] = new_params
        self._rewrite_block(func.get("body"), fscope)

    def _rewrite_funcname(self, node: Node, scope: Scope):
        """改写函数声明名（仅 Name 部分可重命名；Index/Method 的字段名保留）。"""
        if node.type == "Name":
            nm = node.get("name")
            new = scope.resolve(nm)
            if new:
                node.attrs["name"] = new
        elif node.type == "Index":
            self._rewrite_funcname(node.get("obj"), scope)
            # key 是 String 字段名，保留不动
        elif node.type == "MethodName":
            self._rewrite_funcname(node.get("obj"), scope)

    def _rewrite_expr(self, node: Node, scope: Scope):
        t = node.type
        if t == "Name":
            nm = node.get("name")
            if nm in self.reserve:
                return
            new = scope.resolve(nm)
            if new:
                node.attrs["name"] = new
            return
        if t == "Index":
            self._rewrite_expr(node.get("obj"), scope)
            # key 若为 String，是字段名，保留；若是计算式表达式，递归
            key = node.get("key")
            if key.type != "String":
                self._rewrite_expr(key, scope)
            return
        if t == "Call":
            self._rewrite_expr(node.get("func"), scope)
            for a in node.get("args"):
                self._rewrite_expr(a, scope)
            return
        if t == "MethodCall":
            self._rewrite_expr(node.get("obj"), scope)
            # method 是字段名（字符串），保留
            for a in node.get("args"):
                self._rewrite_expr(a, scope)
            return
        if t == "Function":
            self._rewrite_function(node, scope)
            return
        if t == "BinOp":
            self._rewrite_expr(node.get("left"), scope)
            self._rewrite_expr(node.get("right"), scope)
            return
        if t == "UnaryOp":
            self._rewrite_expr(node.get("operand"), scope)
            return
        if t == "Paren":
            self._rewrite_expr(node.get("expr"), scope)
            return
        if t == "Table":
            for f in node.get("fields"):
                if f.type == "TableField":
                    # key 若为 String 字段名保留；否则递归
                    k = f.get("key")
                    if k.type != "String":
                        self._rewrite_expr(k, scope)
                    self._rewrite_expr(f.get("value"), scope)
                else:
                    self._rewrite_expr(f.get("value"), scope)
            return
        # Nil/True/False/Number/String/Vararg 无需处理
        return

    def _rewrite_children(self, node: Node, scope: Scope):
        """兜底：对未知语句类型的子节点递归改写。"""
        for key, val in list(node.attrs.items()):
            if isinstance(val, Node):
                self._rewrite_expr(val, scope) if self._is_expr_like(val) else self._rewrite_stmt(val, scope)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        if self._is_expr_like(item):
                            self._rewrite_expr(item, scope)
                        else:
                            self._rewrite_stmt(item, scope)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                if self._is_expr_like(sub):
                                    self._rewrite_expr(sub, scope)
                                else:
                                    self._rewrite_stmt(sub, scope)

    @staticmethod
    def _is_expr_like(node: Node) -> bool:
        return node.type in (
            "Name", "Number", "String", "Nil", "True", "False", "Vararg",
            "Paren", "Index", "Function", "Table", "BinOp", "UnaryOp",
            "Call", "MethodCall",
        )


def rename(chunk: Node, rng: random.Random,
           reserve_names: Optional[Set[str]] = None) -> Dict[str, str]:
    """对整棵 AST 执行作用域感知重命名。

    返回根作用域的全局名映射表 old->new（供调试/日志使用）。
    """
    r = Renamer(rng, reserve_names)
    r.prescan(chunk)
    r.rewrite(chunk)
    return dict(r.root.decls)
