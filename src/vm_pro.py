# -*- coding: utf-8 -*-
"""
vm_pro.py — 苍米独家混淆 · 付费级字节码 VM（核心突破层）
=========================================================

把整个脚本编译成一条扁平化的自定义字节码流，外层包裹加密、多态、
反调试的解释器。攻击者拿到的不再是「可读 Lua 源码 + 可读 VM 解释器」，
而是「加密字节码流 + 每次不同的多态解释器」。

架构：
1. 整脚本编译：顶层语句 + 所有函数体压成单条字节码流。
   函数调用通过 CLOSURE 创建 Lua 闭包，闭包内部调用 _run(funcStartPC, ...)。
2. _run(startPC, ...) 解释器：每个调用有独立的寄存器表 R 和返回值表 _rets。
   PARAMS 指令从 varargs 加载参数，GETRET 取上次调用的第 N 个返回值。
3. 字节码流加密：位置密钥 + 滚动 XOR（enc = val ^ ((key + pc + i) & 0xFFFFFFFF)），32-bit 有符号还原支持负跳转偏移。
4. 多态 dispatcher：每次混淆 opcode 表完全重排，handler 顺序随机化，变体码 1-3 个。
5. 解释器内嵌反调试（debug 库检测 + _G 键计数 + 时间戳校验）。

安全闸：任何编译异常 → 返回 None → 调用方回退到现有逐函数 VM。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# Node 类型用于 _iter_child_nodes 的 isinstance 检查（运行时由 obfuscator_core 注入）
try:
    from obfuscator_core import Node
except Exception:
    # bundle（单文件）：obfuscator_core 段已定义真正的 Node，直接复用，勿覆盖
    try:
        Node  # noqa: F821  — 已由同文件前段定义
    except NameError:
        class Node:  # type: ignore
            pass


# =============================================================================
# 一、操作码定义（覆盖完整 Luau 子集 + 假 opcode 花指令混淆）
# =============================================================================
# 真 opcode（编译器会主动 emit）
_PRO_OPCODES = [
    "LOADK", "LOADSTR", "LOADBOOL", "LOADNIL", "MOVR",
    "BINOP", "UNOP",
    "JMP", "CJMP", "NJMP",
    "CALL", "CALLV", "RET", "CLOSURE", "PARAMS", "GETRET",
    "NEWTAB", "GETTAB", "SETTAB", "GETTABK", "SETTABK",
    "GETGLOB", "SETGLOB", "GETUV", "SETUV", "COPYUV",
    "FORPREP", "FORLOOP",
    "BREAK",
]
# 假 opcode（编译器从不 emit，但占用 opcode 码点 + 在 dispatcher 有 handler）
# 反汇编工具会看到这些 opcode 并尝试分析其语义，浪费精力
_PRO_FAKE_OPCODES = ["JUNK1", "JUNK2", "JUNK3", "JUNK4", "JUNK5", "JUNK6", "JUNK7", "JUNK8"]

_PRO_BINOPS = ["+", "-", "*", "/", "%", "^", "..",
               "==", "~=", "<", ">", "<=", ">=", "and", "or",
               "&", "|", "~", "<<", ">>", "//"]
_PRO_UNOPS = ["-", "not", "#"]


# P1-3 字节码防篡改校验：CRC32 (IEEE 802.3) 查表
# 编译期（Python）与运行期（Lua）使用同一张表、同一算法，保证两侧校验和一致。
def _make_crc32_table() -> List[int]:
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c & 1:
                c = (c >> 1) ^ 0xEDB88320
            else:
                c = c >> 1
        table.append(c & 0xFFFFFFFF)
    return table


_CRC32_TABLE = _make_crc32_table()


# =============================================================================
# 二、字节码编译器
# =============================================================================
class ProVMCompiler:
    """把整个 chunk AST 编译成扁平字节码流。"""

    def __init__(self, rng: random.Random, gen):
        self.rng = rng
        self.gen = gen
        # 操作码随机化（真 opcode + 假 opcode 一起分配码点，假 opcode 占位增加反汇编噪音）
        ops = list(_PRO_OPCODES) + list(_PRO_FAKE_OPCODES)
        rng.shuffle(ops)
        self.opcode: Dict[str, int] = {name: i for i, name in enumerate(ops)}
        # 变体扩展：每个 opcode 有 1-3 个变体码（真 opcode 才参与编译器 emit）
        self.variant_to_real: Dict[int, int] = {}
        self.opcode_variants: Dict[str, List[int]] = {}
        next_code = len(ops)
        for name in ops:
            real = self.opcode[name]
            variants = [real]
            for _ in range(rng.randint(1, 2)):
                variants.append(next_code)
                self.variant_to_real[next_code] = real
                next_code += 1
            self.opcode_variants[name] = variants
            self.variant_to_real[real] = real
        # binop / unop 随机化
        bl = list(_PRO_BINOPS)
        rng.shuffle(bl)
        self.bincode = {op: i for i, op in enumerate(bl)}
        ul = list(_PRO_UNOPS)
        rng.shuffle(ul)
        self.uncode = {op: i for i, op in enumerate(ul)}
        # 字节码流（1-based，prog[0] 占位）
        self.prog: List[List[Any]] = [[None]]
        # 常量池（0-based 索引，Lua 表 1-based，handler 里 +1）
        self.consts: List[Any] = []
        self.strs: List[str] = []
        # 寄存器映射
        self._reg: Dict[str, str] = {}
        # 跳转回填
        self._patches: List[Tuple[int, int, str]] = []
        self._labels: Dict[str, int] = {}
        # CLOSURE 绝对地址回填
        self._closure_patches: List[Tuple[int, str]] = []
        # 作用域
        self._local_stack: List[set] = [set()]
        # 循环结束标签栈（用于 BREAK）
        self._loop_end_stack: List[str] = []
        # 待编译函数
        self._pending_funcs: List[Tuple] = []
        # 闭包捕获变量集合：这些变量改用 _G 存储（GETGLOB/SETGLOB），实现跨调用帧共享
        self._captured_vars: set = set()
        # 花指令概率（控制插入密度，0.08 ≈ 每 12 条指令插 1 条）
        self._junk_rate = 0.08
        # 死寄存器计数器（花指令写入专用，不污染真寄存器）
        self._dead_reg_counter = 0

    # ---- 花指令生成 ----
    def _dead_reg(self) -> str:
        """生成死寄存器名（只写不读，不影响真实逻辑）。"""
        self._dead_reg_counter += 1
        return f"_d{self._dead_reg_counter}"

    def _emit_raw(self, op_name: str, *args) -> int:
        """直接 emit 不触发花指令（花指令自身用，避免无限递归）。"""
        idx = len(self.prog)
        variants = self.opcode_variants[op_name]
        emitted_op = self.rng.choice(variants)
        self.prog.append([emitted_op] + list(args))
        return idx

    def _maybe_emit_junk(self):
        """以小概率插入花指令，破坏反汇编模式识别。
        三类花指令随机选择：
        1) LOADK 到死寄存器（看起来像真实赋值但结果被丢弃）
        2) LOADNIL 到死寄存器
        3) MOVR 死寄存器之间互相拷贝
        所有花指令都用真 opcode（变体随机），让反汇编器以为是真实逻辑。"""
        if self.rng.random() > self._junk_rate:
            return
        kind = self.rng.randint(1, 3)
        if kind == 1:
            # LOADK 假常量到死寄存器
            self._emit_raw("LOADK", self._dead_reg(), self._const_idx(self.rng.randint(0, 9999)))
        elif kind == 2:
            # LOADNIL 到死寄存器
            self._emit_raw("LOADNIL", self._dead_reg())
        else:
            # MOVR 死寄存器互相拷贝
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            self._emit_raw("LOADNIL", d1)
            self._emit_raw("MOVR", d2, d1)

    # ---- 基础工具 ----
    def _emit(self, op_name: str, *args) -> int:
        # 花指令：在真指令前以小概率插入无害指令，干扰反汇编模式识别
        # 注意：花指令本身不参与跳转回填（_patches 只记录真指令 idx）
        self._maybe_emit_junk()
        return self._emit_raw(op_name, *args)

    def _cur_pc(self) -> int:
        return len(self.prog)

    def _label(self, name: str):
        self._labels[name] = self._cur_pc()

    def _jmp_ph(self, op_name: str, *args, label_key: str, field: int) -> int:
        idx = self._emit(op_name, *args)
        self._patches.append((idx, field, label_key))
        return idx

    def _patch_all(self):
        # P1-2 控制流平坦化：跳转目标间接化
        # 把所有 label 的 PC 存入 jump_targets 表，跳转指令存 label 索引
        # 运行时 pc = jump_targets[idx]，反汇编器无法静态确定跳转目标
        # 收集所有被引用的 label，分配索引
        used_labels: List[str] = []
        label_to_idx: Dict[str, int] = {}
        for _, _, label_key in self._patches:
            if label_key not in label_to_idx:
                label_to_idx[label_key] = len(used_labels)
                used_labels.append(label_key)
        # 编译期暂存 label->PC 映射，运行时由解释器生成 jump_targets 表
        self._used_labels = used_labels
        self._label_to_idx = label_to_idx
        # 回填跳转指令：把相对偏移改为 label 索引（1-based，匹配 Lua 表）
        for prog_idx, field, label_key in self._patches:
            idx_1based = label_to_idx.get(label_key, 0) + 1
            self.prog[prog_idx][field] = idx_1based
        # CLOSURE 绝对地址仍直接回填（不走间接表）
        for prog_idx, func_id in self._closure_patches:
            target = self._labels.get(func_id, 1)
            self.prog[prog_idx][2] = target

    def _reg_of(self, name: str) -> str:
        if name not in self._reg:
            self._reg[name] = self.gen.fresh()
        return self._reg[name]

    def _new_reg(self) -> str:
        return self.gen.fresh()

    def _const_idx(self, val) -> int:
        self.consts.append(val)
        return len(self.consts) - 1

    def _str_idx(self, s: str) -> int:
        # 每个字符串独立密钥（基于位置派生），三层加密元数据存入 strs 池
        # 运行时解密：XOR(k1) -> ADD(k2) -> 字节置换(perm)
        if not hasattr(self, '_str_keys'):
            self._str_keys: List[Tuple[int, int, List[int]]] = []
        k1 = self.rng.randint(1, 0xFF)
        k2 = self.rng.randint(1, 0xFF)
        # 字节置换表（0-255 的排列，避免退化成恒等）
        perm = list(range(256))
        self.rng.shuffle(perm)
        self.strs.append(s)
        self._str_keys.append((k1, k2, perm))
        return len(self.strs) - 1

    # ---- 作用域 ----
    def _push_scope(self):
        self._local_stack.append(set())

    def _pop_scope(self):
        self._local_stack.pop()

    def _declare_local(self, name: str):
        self._local_stack[-1].add(name)

    def _is_local(self, name: str) -> bool:
        # 捕获变量不是局部变量（走 _G），其他正常判断
        if name in self._captured_vars:
            return False
        return any(name in s for s in self._local_stack)

    # ---- 闭包捕获变量预扫描 ----
    def _iter_child_nodes(self, node):
        """递归遍历 AST 节点的所有子 Node。"""
        if not hasattr(node, 'attrs'):
            return
        for v in node.attrs.values():
            if isinstance(v, Node):
                yield v
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, Node):
                        yield item
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                yield sub

    def _collect_free_vars(self, node, declared: set, free: set):
        """递归收集一个节点中的自由变量（引用但未在 declared 中声明的 Name）。
        对引入新作用域的节点（LocalAssign / LocalFunction / Function / NumericFor /
        GenericFor）做特殊处理，其余节点通用递归。"""
        if node is None or not hasattr(node, 'type'):
            return
        t = node.type
        if t == "Name":
            name = node.get("name")
            if name and name not in declared:
                free.add(name)
            return
        if t == "LocalAssign":
            for e in (node.get("exprs") or []):
                self._collect_free_vars(e, declared, free)
            for n in (node.get("names") or []):
                declared.add(n)
            return
        if t == "LocalFunction":
            name = node.get("name")
            declared.add(name)
            func = node.get("func")
            inner_declared = set(func.get("params") or [])
            inner_free = set()
            for s in (func.get("body") or []):
                self._collect_free_vars(s, inner_declared, inner_free)
            for f in inner_free:
                if f not in declared:
                    free.add(f)
                else:
                    self._captured_vars.add(f)
            # 自递归引用走 _G，不作为捕获变量：
            # CLOSURE 会复制 uv 表，SETTABK 补设发生在复制之后 → GETUV 读到 nil。
            # 用 SETGLOB/GETGLOB 经 _G 共享，正确支持递归。
            self._captured_vars.discard(name)
            return
        if t in ("Function", "FunctionDecl"):
            func = node.get("func") or node
            params = set(func.get("params") or [])
            if t == "FunctionDecl":
                name_node = node.get("name")
                if name_node and hasattr(name_node, 'type') and name_node.type == "MethodName":
                    params.add("self")
            inner_declared = set(params)
            inner_free = set()
            for s in (func.get("body") or []):
                self._collect_free_vars(s, inner_declared, inner_free)
            for f in inner_free:
                if f not in declared:
                    free.add(f)
                else:
                    self._captured_vars.add(f)
            return
        if t == "NumericFor":
            self._collect_free_vars(node.get("start"), declared, free)
            self._collect_free_vars(node.get("limit"), declared, free)
            step = node.get("step")
            if step:
                self._collect_free_vars(step, declared, free)
            declared.add(node.get("var"))
            for s in (node.get("body") or []):
                self._collect_free_vars(s, declared, free)
            return
        if t == "GenericFor":
            for e in (node.get("exprs") or []):
                self._collect_free_vars(e, declared, free)
            for n in (node.get("names") or []):
                declared.add(n)
            for s in (node.get("body") or []):
                self._collect_free_vars(s, declared, free)
            return
        # 通用递归：遍历所有子节点
        for child in self._iter_child_nodes(node):
            self._collect_free_vars(child, declared, free)

    def _pre_scan_captured(self, chunk):
        """扫描整个 chunk，找出被内层函数捕获的变量名。"""
        body = chunk.get("body") or []
        declared = set()
        for s in body:
            self._collect_free_vars(s, declared, set())

    # ---- 表达式编译 ----
    def _compile_expr(self, node, dest_reg: Optional[str] = None) -> str:
        if dest_reg is None:
            dest_reg = self._new_reg()
        t = node.type
        if t == "Number":
            try:
                v = str(node.get("value"))
                if "." in v or "e" in v.lower():
                    val = float(v)
                else:
                    val = int(v)
            except Exception:
                val = 0
            self._emit("LOADK", dest_reg, self._const_idx(val))
        elif t == "String":
            self._emit("LOADSTR", dest_reg, self._str_idx(node.get("value")))
        elif t == "Nil":
            self._emit("LOADNIL", dest_reg)
        elif t == "True":
            self._emit("LOADBOOL", dest_reg, 1)
        elif t == "False":
            self._emit("LOADBOOL", dest_reg, 0)
        elif t == "Name":
            name = node.get("name")
            if name in self._captured_vars:
                self._emit("GETUV", dest_reg, self._str_idx(name))
            elif self._is_local(name):
                self._emit("MOVR", dest_reg, self._reg_of(name))
            else:
                self._emit("GETGLOB", dest_reg, self._str_idx(name))
        elif t == "BinOp":
            self._compile_binop(node, dest_reg)
        elif t in ("UnOp", "UnaryOp"):
            self._compile_unop(node, dest_reg)
        elif t == "Index":
            obj_reg = self._compile_expr(node.get("obj"))
            key = node.get("key")
            if key.type == "String" and self._is_ident(key.get("value")):
                self._emit("GETTABK", dest_reg, obj_reg, self._str_idx(key.get("value")))
            else:
                key_reg = self._compile_expr(key)
                self._emit("GETTAB", dest_reg, obj_reg, key_reg)
        elif t == "Call":
            self._compile_call(node, dest_reg)
        elif t == "MethodCall":
            self._compile_method_call(node, dest_reg)
        elif t == "Function":
            self._compile_function_expr(node, dest_reg)
        elif t == "Table":
            self._compile_table(node, dest_reg)
        elif t == "Paren":
            self._compile_expr(node.get("expr"), dest_reg)
        else:
            self._emit("LOADNIL", dest_reg)
        return dest_reg

    def _compile_binop(self, node, dest_reg: str):
        op = node.get("op")
        left = node.get("left")
        right = node.get("right")
        if op in ("and", "or"):
            # 短路求值：先算 left，根据真假决定是否跳过 right
            self._compile_expr(left, dest_reg)
            if op == "and":
                # and: if not dest (falsy), skip right
                self._jmp_ph("NJMP", dest_reg, 0, label_key=f"sc_{id(node)}", field=2)
            else:
                # or: if dest (truthy), skip right
                self._jmp_ph("CJMP", dest_reg, 0, label_key=f"sc_{id(node)}", field=2)
            self._compile_expr(right, dest_reg)
            self._label(f"sc_{id(node)}")
        else:
            left_reg = self._compile_expr(left)
            right_reg = self._compile_expr(right)
            self._emit("BINOP", dest_reg, left_reg, right_reg, self.bincode[op])

    def _compile_unop(self, node, dest_reg: str):
        op = node.get("op")
        operand_reg = self._compile_expr(node.get("operand"))
        self._emit("UNOP", dest_reg, operand_reg, self.uncode[op])

    def _compile_call(self, node, dest_reg: str):
        func_node = node.get("func")
        args = node.get("args") or []
        if func_node.type == "Name":
            fname = func_node.get("name")
            if self._is_local(fname):
                func_reg = self._reg_of(fname)
            else:
                func_reg = self._new_reg()
                self._emit("GETGLOB", func_reg, self._str_idx(fname))
        else:
            func_reg = self._compile_expr(func_node)
        arg_regs = [self._compile_expr(a) for a in args]
        self._emit("CALL", dest_reg, func_reg, len(arg_regs), *arg_regs)

    def _compile_method_call(self, node, dest_reg: str):
        obj_node = node.get("obj")
        method = node.get("method")
        args = node.get("args") or []
        obj_reg = self._compile_expr(obj_node)
        # method 可能是纯字符串（parser 直接存 name value），也可能是 String 节点
        if isinstance(method, str):
            method_str = method
        elif hasattr(method, "get"):
            method_str = method.get("value") or str(method)
        else:
            method_str = str(method)
        arg_regs = [self._compile_expr(a) for a in args]
        self._emit("CALLV", dest_reg, obj_reg, self._str_idx(method_str),
                   len(arg_regs), *arg_regs)

    def _compile_function_expr(self, node, dest_reg: str, func_name: str = None):
        func_id = f"func_{id(node)}"
        # 创建闭包 upvalue 表：捕获当前作用域中已定义的捕获变量
        uv_reg = self._new_reg()
        self._emit("NEWTAB", uv_reg)
        for var in self._captured_vars:
            # 跳过函数自身（尚未定义，由调用方在 CLOSURE 后补设）
            if var == func_name:
                continue
            if var in self._reg:
                self._emit("SETTABK", uv_reg, self._str_idx(var), self._reg_of(var))
        # CLOSURE 指令：[opcode, dest_reg, startPC(待回填), uv_reg]
        idx = self._emit("CLOSURE", dest_reg, 0, uv_reg)
        self._closure_patches.append((idx, func_id))
        self._pending_funcs.append((node, func_id))
        self._last_uv_reg = uv_reg  # 供调用方在 CLOSURE 后补充捕获
        return dest_reg

    def _compile_table(self, node, dest_reg: str):
        fields = node.get("fields") or []
        self._emit("NEWTAB", dest_reg)
        seq_idx = 0
        for field in fields:
            if field.type in ("TableItem", "TableField"):
                key = field.get("key")
                val = field.get("value")
                if key is None:
                    seq_idx += 1
                    val_reg = self._compile_expr(val)
                    k_reg = self._new_reg()
                    self._emit("LOADK", k_reg, self._const_idx(seq_idx))
                    self._emit("SETTAB", dest_reg, k_reg, val_reg)
                else:
                    if key.type == "String" and self._is_ident(key.get("value")):
                        val_reg = self._compile_expr(val)
                        self._emit("SETTABK", dest_reg, self._str_idx(key.get("value")), val_reg)
                    else:
                        key_reg = self._compile_expr(key)
                        val_reg = self._compile_expr(val)
                        self._emit("SETTAB", dest_reg, key_reg, val_reg)

    def _is_ident(self, s: str) -> bool:
        if not s:
            return False
        if not (s[0].isalpha() or s[0] == "_"):
            return False
        return all(c.isalnum() or c == "_" for c in s)

    def _store_name(self, name: str, val_reg: str):
        """把值存入变量：捕获变量走 SETUV（闭包 upvalue 表），局部变量走 declare + MOVR。"""
        if name in self._captured_vars:
            self._emit("SETUV", self._str_idx(name), val_reg)
        else:
            self._declare_local(name)
            self._emit("MOVR", self._reg_of(name), val_reg)

    # ---- 语句编译 ----
    def _compile_stmt(self, node):
        t = node.type
        if t == "LocalAssign":
            names = node.get("names") or []
            exprs = node.get("exprs") or []
            n_names = len(names)
            n_exprs = len(exprs)
            # 多返回值：单个表达式赋给多个变量
            if n_exprs == 1 and n_names > 1 and exprs[0].type in ("Call", "MethodCall"):
                self._compile_expr(exprs[0], self._new_reg())
                for i, name in enumerate(names):
                    tmp = self._new_reg()
                    self._emit("GETRET", tmp, i + 1)
                    self._store_name(name, tmp)
            else:
                # 先编译所有表达式（到临时寄存器），再赋值
                val_regs = []
                for i in range(n_names):
                    if i < n_exprs:
                        val_regs.append(self._compile_expr(exprs[i]))
                    else:
                        val_regs.append(None)
                for i, name in enumerate(names):
                    if name in self._captured_vars:
                        if val_regs[i] is not None:
                            self._emit("SETUV", self._str_idx(name), val_regs[i])
                        else:
                            nil_reg = self._new_reg()
                            self._emit("LOADNIL", nil_reg)
                            self._emit("SETUV", self._str_idx(name), nil_reg)
                    else:
                        self._declare_local(name)
                        if val_regs[i] is not None:
                            self._emit("MOVR", self._reg_of(name), val_regs[i])
                        else:
                            self._emit("LOADNIL", self._reg_of(name))
        elif t == "Assign":
            targets = node.get("targets") or []
            exprs = node.get("exprs") or []
            n_targets = len(targets)
            n_exprs = len(exprs)
            # 多返回值：最后一个表达式是 Call/MethodCall 且目标数 > 表达式数
            if n_exprs >= 1 and n_targets > n_exprs and exprs[-1].type in ("Call", "MethodCall"):
                # 先编译前面的表达式
                val_regs = [self._compile_expr(exprs[i]) for i in range(n_exprs - 1)]
                # 编译最后一个 Call，获取额外返回值
                self._compile_expr(exprs[-1], self._new_reg())
                # 前面的值
                for i in range(n_exprs - 1):
                    val_regs.append(val_regs[i])
                # 后面的值从 GETRET 获取
                for i in range(n_exprs - 1, n_targets):
                    r = self._new_reg()
                    self._emit("GETRET", r, i - (n_exprs - 1) + 1)
                    val_regs.append(r)
            else:
                # 先编译所有表达式，再赋值（避免赋值顺序影响）
                val_regs = []
                for i in range(n_targets):
                    if i < n_exprs:
                        val_regs.append(self._compile_expr(exprs[i]))
                    else:
                        val_regs.append(None)
            for i, tgt in enumerate(targets):
                val_reg = val_regs[i] if val_regs[i] is not None else self._new_reg()
                if val_regs[i] is None:
                    self._emit("LOADNIL", val_reg)
                if tgt.type == "Name":
                    name = tgt.get("name")
                    if name in self._captured_vars:
                        self._emit("SETUV", self._str_idx(name), val_reg)
                    elif self._is_local(name):
                        self._emit("MOVR", self._reg_of(name), val_reg)
                    else:
                        self._emit("SETGLOB", self._str_idx(name), val_reg)
                elif tgt.type == "Index":
                    obj_reg = self._compile_expr(tgt.get("obj"))
                    key = tgt.get("key")
                    if key.type == "String" and self._is_ident(key.get("value")):
                        self._emit("SETTABK", obj_reg, self._str_idx(key.get("value")), val_reg)
                    else:
                        key_reg = self._compile_expr(key)
                        self._emit("SETTAB", obj_reg, key_reg, val_reg)
        elif t in ("Call", "MethodCall"):
            self._compile_expr(node, self._new_reg())
        elif t == "CallStatement":
            self._compile_expr(node.get("expr"), self._new_reg())
        elif t == "If":
            self._compile_if(node)
        elif t == "While":
            self._compile_while(node)
        elif t == "Repeat":
            self._compile_repeat(node)
        elif t == "NumericFor":
            self._compile_numeric_for(node)
        elif t == "GenericFor":
            self._compile_generic_for(node)
        elif t == "Return":
            self._compile_return(node)
        elif t == "Break":
            if self._loop_end_stack:
                self._jmp_ph("JMP", 0, label_key=self._loop_end_stack[-1], field=1)
            else:
                self._emit("JMP", 0)
        elif t == "LocalFunction":
            name = node.get("name")
            func = node.get("func")
            self._declare_local(name)
            self._compile_function_expr(func, self._reg_of(name), func_name=name)
            # 递归支持：捕获变量 → SETTABK 到 _uv 表，普通变量 → SETGLOB 到 _G
            if name in self._captured_vars:
                self._emit("SETTABK", self._last_uv_reg, self._str_idx(name), self._reg_of(name))
            else:
                self._emit("SETGLOB", self._str_idx(name), self._reg_of(name))
        elif t == "FunctionDecl":
            name_node = node.get("name")
            func = node.get("func")
            dest_reg = self._new_reg()
            # 方法定义 function obj:m() ... end → 需注入 self 作为第一个参数
            if name_node.type == "MethodName":
                # 在 func 节点的 params 前插入 "self"
                orig_params = func.get("params") or []
                if not orig_params or orig_params[0] != "self":
                    func.attrs["params"] = ["self"] + list(orig_params)
            self._compile_function_expr(func, dest_reg)
            if name_node.type == "Name":
                self._emit("SETGLOB", self._str_idx(name_node.get("name")), dest_reg)
            elif name_node.type == "Index":
                obj_reg = self._compile_expr(name_node.get("obj"))
                key = name_node.get("key")
                if key.type == "String" and self._is_ident(key.get("value")):
                    self._emit("SETTABK", obj_reg, self._str_idx(key.get("value")), dest_reg)
            elif name_node.type == "MethodName":
                obj_reg = self._compile_expr(name_node.get("obj"))
                method_name = name_node.get("method")
                self._emit("SETTABK", obj_reg, self._str_idx(method_name), dest_reg)
        elif t == "Do":
            self._push_scope()
            for s in (node.get("body") or []):
                self._compile_stmt(s)
            self._pop_scope()

    def _compile_if(self, node):
        cond = node.get("cond")
        body = node.get("body") or []
        elifs = node.get("elifs") or []
        else_body = node.get("else_body") or []
        end_label = f"if_end_{id(node)}"
        cond_reg = self._compile_expr(cond)
        self._jmp_ph("NJMP", cond_reg, 0, label_key=f"if_skip_{id(node)}_0", field=2)
        self._push_scope()
        for s in body:
            self._compile_stmt(s)
        self._pop_scope()
        self._jmp_ph("JMP", 0, label_key=end_label, field=1)
        self._label(f"if_skip_{id(node)}_0")
        end_labels = [end_label]
        for i, ef in enumerate(elifs):
            ec = ef[0] if isinstance(ef, tuple) else ef.get("cond")
            eb = ef[1] if isinstance(ef, tuple) else ef.get("body")
            ec_reg = self._compile_expr(ec)
            skip_l = f"if_skip_{id(node)}_{i+1}"
            end_l = f"if_end_{id(node)}_{i+1}"
            self._jmp_ph("NJMP", ec_reg, 0, label_key=skip_l, field=2)
            self._push_scope()
            for s in (eb or []):
                self._compile_stmt(s)
            self._pop_scope()
            self._jmp_ph("JMP", 0, label_key=end_l, field=1)
            self._label(skip_l)
            end_labels.append(end_l)
        if else_body:
            self._push_scope()
            for s in else_body:
                self._compile_stmt(s)
            self._pop_scope()
        for lbl in end_labels:
            self._label(lbl)

    def _compile_while(self, node):
        start = f"while_start_{id(node)}"
        end = f"while_end_{id(node)}"
        self._label(start)
        cond_reg = self._compile_expr(node.get("cond"))
        self._jmp_ph("NJMP", cond_reg, 0, label_key=end, field=2)
        self._loop_end_stack.append(end)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()
        self._jmp_ph("JMP", 0, label_key=start, field=1)
        self._label(end)

    def _compile_repeat(self, node):
        start = f"repeat_start_{id(node)}"
        end = f"repeat_end_{id(node)}"
        self._label(start)
        self._loop_end_stack.append(end)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        cond_reg = self._compile_expr(node.get("cond"))
        self._pop_scope()
        self._loop_end_stack.pop()
        self._jmp_ph("NJMP", cond_reg, 0, label_key=start, field=2)
        self._label(end)

    def _compile_numeric_for(self, node):
        var = node.get("var")
        start_reg = self._compile_expr(node.get("start"))
        limit_reg = self._compile_expr(node.get("limit"))
        step = node.get("step")
        if step:
            step_reg = self._compile_expr(step)
        else:
            step_reg = self._new_reg()
            self._emit("LOADK", step_reg, self._const_idx(1))
        loop_var_reg = self._reg_of(var)
        self._declare_local(var)
        # 专用寄存器保存 limit 和 step（跨迭代不变）
        limit_store = self._new_reg()
        step_store = self._new_reg()
        self._emit("MOVR", limit_store, limit_reg)
        self._emit("MOVR", step_store, step_reg)
        loop_start_label = f"forstart_{id(node)}"
        end_label = f"forend_{id(node)}"
        # FORPREP: var = start; 如果初始就不满足条件则跳过循环体
        # inst = [op, var_reg, start_reg, limit_store, step_store, skip_offset]
        self._jmp_ph("FORPREP", loop_var_reg, start_reg, limit_store, step_store,
                      0, label_key=end_label, field=5)
        self._label(loop_start_label)
        self._loop_end_stack.append(end_label)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()
        # FORLOOP: var += step; 如果仍满足条件则跳回 loop_start
        # inst = [op, var_reg, limit_store, step_store, back_offset]
        # back_offset 在 field=4（第 5 个元素）
        # 用 label 回填，避免花指令插入导致偏移计算错误
        self._jmp_ph("FORLOOP", loop_var_reg, limit_store, step_store,
                      0, label_key=loop_start_label, field=4)
        self._label(end_label)

    def _compile_generic_for(self, node):
        """编译 generic for: for v1, v2, ... in explist do body end
        等价于:
          local f, s, var = explist
          while true do
            local r1, r2, ... = f(s, var)
            if r1 == nil then break end
            var = r1
            v1, v2, ... = r1, r2, ...
            body
          end
        """
        vars_ = node.get("names") or []
        exprs = node.get("exprs") or []

        # 获取迭代器 f, 状态 s, 控制变量 var
        f_reg = self._new_reg()
        s_reg = self._new_reg()
        var_reg = self._new_reg()

        if len(exprs) == 1:
            # 常见情况：单个表达式（通常是函数调用）返回 3 个值
            self._compile_expr(exprs[0], f_reg)
            # CALL 已经把所有返回值存入 _rets
            self._emit("GETRET", f_reg, 1)
            self._emit("GETRET", s_reg, 2)
            self._emit("GETRET", var_reg, 3)
        else:
            regs = [self._compile_expr(e) for e in exprs]
            if len(regs) >= 1:
                self._emit("MOVR", f_reg, regs[0])
            if len(regs) >= 2:
                self._emit("MOVR", s_reg, regs[1])
            if len(regs) >= 3:
                self._emit("MOVR", var_reg, regs[2])

        for v in vars_:
            self._declare_local(v)

        start_label = f"genfor_start_{id(node)}"
        end_label = f"genfor_end_{id(node)}"
        self._label(start_label)

        # 调用迭代器: r1, r2, ... = f(s, var)
        iter_dest = self._new_reg()
        self._emit("CALL", iter_dest, f_reg, 2, s_reg, var_reg)

        # 把返回值赋给循环变量
        for i, v in enumerate(vars_):
            self._emit("GETRET", self._reg_of(v), i + 1)

        # 检查第一个变量是否为 nil → 跳出循环
        nil_reg = self._new_reg()
        self._emit("LOADNIL", nil_reg)
        eq_reg = self._new_reg()
        self._emit("BINOP", eq_reg, self._reg_of(vars_[0]), nil_reg, self.bincode["=="])
        self._jmp_ph("CJMP", eq_reg, 0, label_key=end_label, field=2)

        # 更新控制变量: var = v1
        self._emit("MOVR", var_reg, self._reg_of(vars_[0]))

        # 循环体
        self._loop_end_stack.append(end_label)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()

        # 跳回循环开始
        self._jmp_ph("JMP", 0, label_key=start_label, field=1)
        self._label(end_label)

    def _compile_return(self, node):
        exprs = node.get("exprs") or []
        if not exprs:
            self._emit("RET")
        else:
            regs = [self._compile_expr(e) for e in exprs]
            self._emit("RET", regs[0], len(regs), *regs)

    # ---- 函数体编译 ----
    def _compile_function_body(self, node, func_id: str):
        params = node.get("params") or []
        old_locals = self._local_stack[:]
        old_reg = self._reg
        self._local_stack = [set()]
        self._reg = {}
        # 在函数体开头插入 PARAMS 指令（label 必须在 PARAMS 之前，确保 _run 从 PARAMS 开始）
        self._label(func_id)
        param_regs = [self._reg_of(p) for p in params]
        # 必须声明参数为局部变量，否则函数体内会误用 GETGLOB 取全局
        for p in params:
            self._declare_local(p)
        self._emit("PARAMS", len(params), *param_regs)
        # 捕获变量参数：PARAMS 把参数加载到寄存器后，还需 SETUV 存入 _uv，
        # 否则内层闭包通过 GETUV 读取时会得到 nil。
        # 典型场景：local function makeAdder(n) return function(x) return x + n end end
        for p in params:
            if p in self._captured_vars:
                self._emit("SETUV", self._str_idx(p), self._reg_of(p))
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._emit("RET")
        self._local_stack = old_locals
        self._reg = old_reg

    # ---- 主编译入口 ----
    def compile_chunk(self, chunk) -> Optional[str]:
        try:
            # 预扫描：找出被闭包捕获的变量，这些变量改用 _G 存储
            self._pre_scan_captured(chunk)
            body = chunk.get("body") or []
            for stmt in body:
                self._compile_stmt(stmt)
            self._emit("RET")
            for func_node, func_id in self._pending_funcs:
                self._compile_function_body(func_node, func_id)
            self._patch_all()
            return self._gen_interpreter()
        except Exception:
            return None

    # ---- 解释器生成 ----
    def _gen_interpreter(self) -> str:
        gen = self.gen
        key = self.rng.randint(1, 0xFFFFFFFF)
        # 变量名
        fn_name = gen.fresh()
        bc_var = gen.fresh()
        key_var = gen.fresh()
        consts_var = gen.fresh()
        strs_var = gen.fresh()
        run_var = gen.fresh()
        pc_var = gen.fresh()
        reg_var = gen.fresh()
        inst_var = gen.fresh()
        op_var = gen.fresh()
        va_var = gen.fresh()
        rets_var = gen.fresh()
        ad_var = gen.fresh()
        raw_var = gen.fresh()
        bc_len_var = gen.fresh()
        uv_var = gen.fresh()  # 闭包 upvalue 表变量名

        consts_lua = "{" + ",".join(self._fmt_const(c) for c in self.consts) + "}"
        strs_lua = self._gen_str_pool_lua(strs_var)

        bin_dispatch = self._gen_binop_dispatch(reg_var)
        un_dispatch = self._gen_unop_dispatch(reg_var)
        # P1-2 控制流平坦化：跳转目标间接表
        jt_var = gen.fresh()  # jump_targets 表变量名
        handler_chain = self._gen_handler_chain(
            op_var, reg_var, consts_var, strs_var, pc_var, inst_var,
            bin_dispatch, un_dispatch, run_var, rets_var, va_var, uv_var, jt_var)

        # 自修改 dispatcher：opcode 字段额外异或 shift_key
        # shift_key = (pc // shift_period) & 0xFFFF，每 shift_period 条指令变化一次
        # 反汇编器无法静态确定 opcode 含义，必须模拟 shift_key 演化
        shift_period = self.rng.randint(7, 19)
        shift_var = gen.fresh()
        bc_lua = self._encrypt_program(key, shift_period)
        ad_period = self.rng.randint(50, 150)
        ad_threshold = self.rng.choice([500, 999, 1500, 2000])
        # 反 trace 细化：高频时间检测阈值 + hook 检测
        # time_limit：每 ad_period 条指令的累计耗时上限（秒）
        # 单步执行会让这个值暴涨 100-1000 倍，触发静默 corrupt
        time_limit = self.rng.choice([0.05, 0.1, 0.2, 0.5])
        time_var = gen.fresh()
        last_time_var = gen.fresh()
        hook_chk_var = gen.fresh()
        corrupt_var = gen.fresh()

        # P1-3 字节码防篡改校验：CRC32 分段校验
        # 把字节码流切成若干段，每段预存 CRC32，运行期轮询重算并比对。
        # 篡改任一字节 → 校验和失配 → 静默 corrupt（不报错，结果错乱，更难排查）。
        segments = self._build_segments(key, shift_period)
        crc_segs_var = gen.fresh()    # 段表变量名
        crc_fn_var = gen.fresh()      # _crc_seg 函数变量名
        seg_chk_var = gen.fresh()      # 段轮询计数器
        crc_tab_var = gen.fresh()      # CRC 查表缓存
        # 序列化段表：{ {lo, hi, crc}, ... }
        seg_items = []
        for lo, hi, crc in segments:
            seg_items.append(f'{{{lo},{hi},{crc}}}')
        crc_segs_lua = "{" + ",".join(seg_items) + "}"
        # 运行期 CRC32 算法与编译期 _compute_seg_crc 完全一致（同表、同字节序、同遍历）
        # 每个数字元素拆成 4 个小端字节喂入 CRC（与 Python 侧逐字节对齐）
        crc_fn_lua = (
            f'local {crc_tab_var}=nil '
            f'local function {crc_fn_var}(_bc,_lo,_hi) '
            f'if not {crc_tab_var} then '
            f'{crc_tab_var}={{}} '
            f'for _i=0,255 do local _c=_i for _=1,8 do '
            f'if _c%2==1 then _c=(_c//2)~0xEDB88320 else _c=_c//2 end end '
            f'{crc_tab_var}[_i]=_c end end '
            f'local _crc=0xFFFFFFFF '
            f'for _pc=_lo,_hi do local _ins=_bc[_pc] '
            f'if _ins then for _i=1,#_ins do local _e=_ins[_i] '
            f'if type(_e)=="number" then local _v=_e '
            f'local _b0=_v%256 local _b1=(_v//256)%256 '
            f'local _b2=(_v//65536)%256 local _b3=(_v//16777216)%256 '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b0)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b1)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b2)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b3)%256] '
            f'end end end end '
            f'return _crc~0xFFFFFFFF end'
        )

        # 生成 jump_targets 表：每个被引用的 label 对应一个 PC 值
        jt_items = []
        for i, label_key in enumerate(getattr(self, '_used_labels', [])):
            target_pc = self._labels.get(label_key, 1)
            jt_items.append(f'[{i+1}]={target_pc}')
        jt_lua = "{" + ",".join(jt_items) + "}"

        src = f'''-- [AI-DETECT] 付费级字节码 VM 保护
local function {fn_name}()
    local {bc_var} = {bc_lua}
    local {key_var} = {key}
    local {consts_var} = {consts_lua}
    local {jt_var} = {jt_lua}
    {strs_lua}
    local {corrupt_var} = false  -- 反 trace 触发标志：true 时静默 corrupt 内部状态
    {crc_fn_lua}
    local {crc_segs_var} = {crc_segs_lua}
    local function {run_var}({pc_var}_start, {uv_var}, ...)
        if {uv_var} == nil then {uv_var} = {{}} end
        local {va_var} = {{...}}
        local {pc_var} = {pc_var}_start
        local {reg_var} = {{}}
        local {rets_var} = {{}}
        local {ad_var} = 0
        local {bc_len_var} = #{bc_var}
        local {last_time_var} = os.clock()
        local {seg_chk_var} = 0
        while {pc_var} <= {bc_len_var} do
            local {raw_var} = {bc_var}[{pc_var}]
            if not {raw_var} then break end
            local {inst_var} = {{}}
            for _i = 1, #{raw_var} do
                local _e = {raw_var}[_i]
                if type(_e) == "number" then
                    local _v = _e ~ (({key_var} + {pc_var} + _i) & 0xFFFFFFFF)
                    if _v >= 2147483648 then _v = _v - 4294967296 end
                    {inst_var}[_i] = _v
                else
                    {inst_var}[_i] = _e
                end
            end
            -- 自修改 dispatcher：opcode 二次解密
            -- shift_key = (pc // shift_period) & 0xFFFF，每 shift_period 条指令变化
            -- 编译时 opcode 已按此规律加密，运行时反向异或还原
            local {shift_var} = ({pc_var} // {shift_period}) & 0xFFFF
            local {op_var} = {inst_var}[1] ~ {shift_var}
            {ad_var} = {ad_var} + 1
            if {ad_var} % {ad_period} == 0 then
                -- 反 trace 1: _G 表大小监测（注入器环境注入大量全局）
                local _gc = 0
                for _ in pairs(_G) do _gc = _gc + 1 end
                if _gc > {ad_threshold} then return nil end
                -- 反 trace 2: 高频时间检测
                -- 正常执行 ad_period 条指令耗时 << time_limit
                -- 单步/trace 会让耗时暴涨 100-1000 倍
                local {time_var} = os.clock()
                if {time_var} - {last_time_var} > {time_limit} then
                    {corrupt_var} = true
                end
                -- last_time_var 在本块末尾重置（见 P1-3 后），避免 CRC 计算耗时被计入下一窗口
                -- 反 trace 3: debug hook 检测
                -- debug.sethook 被设置说明有人在 trace（line/call/return 断点）
                local {hook_chk_var} = debug and debug.gethook and debug.gethook()
                if {hook_chk_var} then
                    {corrupt_var} = true
                end
                -- 反 trace 4: 调用栈深度检测
                -- VM 正常调用栈深度有限，过深说明被包装/trace
                if debug and debug.getinfo then
                    local _di = debug.getinfo(3, "f")
                    -- _di 为 nil 说明栈很浅（正常），非 nil 说明有外层包装
                    -- 但 VM 自身也有包装，这里只检测极深栈（>20 层）
                    local _depth = 0
                    local _frame = debug.getinfo(1, "f")
                    while _frame and _depth < 30 do
                        _depth = _depth + 1
                        _frame = debug.getinfo(_depth + 1, "f")
                    end
                    if _depth >= 25 then {corrupt_var} = true end
                end
                -- P1-3 字节码防篡改校验：CRC32 分段轮询
                -- 每个 ad_period 周期校验一段，轮询覆盖全部段。
                -- 任一字节被篡改 → 校验和失配 → 静默 corrupt。
                local _ns = #{crc_segs_var}
                if _ns > 0 then
                    local _si = ({seg_chk_var} % _ns) + 1
                    local _seg = {crc_segs_var}[_si]
                    local _rc = {crc_fn_var}({bc_var}, _seg[1], _seg[2])
                    if _rc ~= _seg[3] then {corrupt_var} = true end
                    {seg_chk_var} = {seg_chk_var} + 1
                end
                -- 重置时间窗口基准：把本块全部工作（含 CRC 计算）排除出下一窗口
                {last_time_var} = os.clock()
            end
            -- corrupt 触发：静默破坏内部状态（不报错，让结果错乱，比直接崩更难排查）
            if {corrupt_var} then
                {reg_var}[1] = nil
                {reg_var}[2] = "corrupted"
                {pc_var} = {pc_var} + {ad_var} % 7 + 1
            end
            -- jump_flag：跳转指令设置后，跳过 pc+1（因为已设绝对目标）
            local _jmp = false
            {handler_chain}
            if not _jmp then {pc_var} = {pc_var} + 1 end
        end
    end
    return {run_var}(1, {{}})
end
return {fn_name}()
'''
        return src

    def _encrypted_elem(self, pc: int, i: int, p, key: int, shift_period: int):
        """计算单条字节码元素 (pc, i) 的加密形式。
        返回 (is_num, value)：
          is_num=True  → value 是加密后的 32-bit 整数（用于 CRC 校验）
          is_num=False → value 是 Lua 字符串字面量（寄存器名等，原样透传）
        与 _encrypt_program 序列化、运行期 bc_var 表内容完全一致。"""
        if isinstance(p, str):
            return False, self._fmt_str(p)
        if isinstance(p, bool):
            return True, 1 if p else 0
        if isinstance(p, (int, float)):
            val = int(p) & 0xFFFFFFFF
            enc = (val ^ ((key + pc + i) & 0xFFFFFFFF)) & 0xFFFFFFFF
            if i == 1:
                shift_key = (pc // shift_period) & 0xFFFF
                enc = (enc ^ shift_key) & 0xFFFFFFFF
            return True, enc
        if p is None:
            return True, 0
        return False, str(p)

    def _encrypt_program(self, key: int, shift_period: int) -> str:
        """序列化 prog 为 Lua 表，数字元素加密。
        加密公式与解密公式一致：enc = val ^ ((key + pc + i) & 0xFFFFFFFF)
        其中 pc = 指令索引(1-based), i = 元素索引(1-based)。
        使用 32-bit 掩码 + 有符号转换，确保负数跳转偏移正确还原。
        自修改 dispatcher：opcode 字段（i=1）额外异或 shift_key，
        shift_key = (pc // shift_period) & 0xFFFF，让 opcode 含义随 PC 位置变化。"""
        parts = []
        for pc, ins in enumerate(self.prog[1:], start=1):
            elem_parts = []
            for i, p in enumerate(ins, start=1):
                is_num, val = self._encrypted_elem(pc, i, p, key, shift_period)
                if is_num:
                    elem_parts.append(str(val))
                else:
                    elem_parts.append(val)
            parts.append("{" + ",".join(elem_parts) + "}")
        return "{" + ",".join(parts) + "}"

    def _compute_seg_crc(self, lo: int, hi: int, key: int, shift_period: int) -> int:
        """计算字节码段 [lo, hi]（1-based PC，闭区间）的 CRC32。
        仅对数字元素（加密后的 32-bit 值，每个拆成 4 个小端字节）参与计算，
        与运行期 _crc_seg 的遍历方式逐字节一致。"""
        crc = 0xFFFFFFFF
        tab = _CRC32_TABLE
        for pc in range(lo, hi + 1):
            ins = self.prog[pc]
            for i, p in enumerate(ins, start=1):
                is_num, val = self._encrypted_elem(pc, i, p, key, shift_period)
                if not is_num:
                    continue
                v = val & 0xFFFFFFFF
                for j in range(4):
                    b = (v >> (8 * j)) & 0xFF
                    crc = (crc >> 8) ^ tab[(crc ^ b) & 0xFF]
        return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF

    def _build_segments(self, key: int, shift_period: int):
        """把字节码流切成 3-6 段，每段计算 CRC32 校验和。
        返回 [(lo, hi, crc), ...]，运行期逐段校验，篡改任一段即触发静默 corrupt。"""
        bc_len = len(self.prog) - 1  # prog[0] 是占位
        if bc_len < 1:
            return []
        num_segments = self.rng.randint(3, 6)
        num_segments = min(num_segments, bc_len)
        seg_size = max(1, bc_len // num_segments)
        segments = []
        for s in range(num_segments):
            lo = 1 + s * seg_size
            if s == num_segments - 1:
                hi = bc_len
            else:
                hi = lo + seg_size - 1
            if lo > hi:
                continue
            crc = self._compute_seg_crc(lo, hi, key, shift_period)
            segments.append((lo, hi, crc))
        return segments


    def _fmt_const(self, c):
        if isinstance(c, float) and c.is_integer():
            return str(int(c))
        if isinstance(c, bool):
            return "true" if c else "false"
        if isinstance(c, str):
            return self._fmt_str(c)
        return repr(c)

    def _fmt_str(self, s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

    def _encrypt_str(self, s: str, k1: int, k2: int, perm: List[int]) -> str:
        """三层加密字符串：
        layer1: 字节置换 perm[b]
        layer2: ADD k2
        layer3: XOR k1
        输出为 Lua 字符串字面量（含转义），运行时反向解密。"""
        enc_bytes = []
        for b in s.encode('utf-8', errors='replace'):
            b = perm[b & 0xFF]          # layer1 置换
            b = (b + k2) & 0xFF          # layer2 ADD
            b = b ^ k1                    # layer3 XOR
            enc_bytes.append(b)
        # 编码为 Lua 转义字符串
        return '"' + ''.join(f'\\{b:03d}' for b in enc_bytes) + '"'

    def _gen_str_pool_lua(self, strs_var: str) -> str:
        """生成 strs 池：每个元素是加密字节串 + 元数据，运行时按需解密。
        返回 Lua 代码：定义 strs 表 + 解密函数。"""
        if not self.strs:
            return f'local {strs_var} = {{}}'
        items = []
        for i, s in enumerate(self.strs):
            k1, k2, perm = self._str_keys[i]
            enc = self._encrypt_str(s, k1, k2, perm)
            # 存储：{enc_str, k1, k2, perm_table}
            # perm 表只存 0-255 值（运行时构造逆表），用字符串压缩以减小体积
            perm_str = '"' + ''.join(f'\\{b:03d}' for b in perm) + '"'
            items.append(f'[{i+1}]={{data={enc},k1={k1},k2={k2},perm={perm_str},dec=nil}}')
        # 生成解密函数：懒解密，第一次访问时解密并缓存
        return f'''local {strs_var} = {{{",".join(items)}}}
        local function _dec_str(s)
            if s.dec then return s.dec end
            local inv = {{}}
            for i = 0, 255 do inv[(string.byte(string.sub(s.perm, i+1, i+1)))] = i end
            local out = {{}}
            for i = 1, #s.data do
                local b = string.byte(string.sub(s.data, i, i))
                b = b ~ s.k1
                b = (b - s.k2) % 256
                b = inv[b]
                out[i] = string.char(b)
            end
            s.dec = table.concat(out)
            return s.dec
        end'''

    def _gen_binop_dispatch(self, reg_var) -> str:
        R = reg_var
        code_to_op = {c: op for op, c in self.bincode.items()}
        parts = []
        for code in range(len(_PRO_BINOPS)):
            op = code_to_op[code]
            if op == "and":
                parts.append(f'if c=={code} then {R}[d]={R}[a] and {R}[b] end')
            elif op == "or":
                parts.append(f'if c=={code} then {R}[d]={R}[a] or {R}[b] end')
            else:
                parts.append(f'if c=={code} then {R}[d]={R}[a]{op}{R}[b] end')
        return " ".join(parts)

    def _gen_unop_dispatch(self, reg_var) -> str:
        R = reg_var
        code_to_op = {c: op for op, c in self.uncode.items()}
        parts = []
        for code in range(len(_PRO_UNOPS)):
            op = code_to_op[code]
            if op == "-":
                parts.append(f'if c=={code} then {R}[d]=-{R}[a] end')
            elif op == "not":
                parts.append(f'if c=={code} then {R}[d]=not {R}[a] end')
            elif op == "#":
                parts.append(f'if c=={code} then {R}[d]=#{R}[a] end')
        return " ".join(parts)

    def _gen_handler_chain(self, op_var, reg_var, consts_var, strs_var,
                           pc_var, inst_var, bin_dispatch, un_dispatch,
                           run_var, rets_var, va_var, uv_var, jt_var) -> str:
        op_order = list(self.opcode.keys())
        self.rng.shuffle(op_order)
        handlers = []
        for op_name in op_order:
            variants = self.opcode_variants[op_name]
            h = self._gen_handler(op_name, reg_var, consts_var,
                                  strs_var, pc_var, inst_var, bin_dispatch, un_dispatch,
                                  run_var, rets_var, va_var, uv_var, jt_var)
            handlers.append((variants, h))
        handlers.sort(key=lambda x: x[0][0])
        parts = []
        for i, (variants, h) in enumerate(handlers):
            conds = " or ".join(f"{op_var}=={v}" for v in variants)
            if i == 0:
                parts.append(f'if {conds} then\n{h}')
            else:
                parts.append(f'elseif {conds} then\n{h}')
        parts.append('end')
        return "\n".join(parts)

    def _gen_handler(self, op_name, R, C, S, pc_var, I, bin_d, un_d,
                     RUN, RETS, VA, UV, JT) -> str:
        # 假 opcode（JUNK1-8）：dispatcher 里有 handler，看起来像真实逻辑
        # 但执行无害操作（写入死寄存器或读取后丢弃），反汇编器无法分辨真假
        # 每个 JUNK 用不同的伪操作模式，增加分析难度
        if op_name.startswith("JUNK"):
            junk_kind = int(op_name[4:])  # JUNK1 -> 1
            if junk_kind == 1:
                # 假算术：看起来像 BINOP 但结果丢弃
                return f'local _j={R}[{I}[2]]+{R}[{I}[3]]'
            elif junk_kind == 2:
                # 假表访问：看起来像 GETTAB 但结果丢弃
                return f'local _j={R}[{I}[2]][{I}[3]]'
            elif junk_kind == 3:
                # 假比较：看起来像条件判断但无副作用
                return f'if {R}[{I}[2]] then local _j=1 end'
            elif junk_kind == 4:
                # 假字符串操作：看起来像字符串拼接
                return f'local _j=tostring({R}[{I}[2]])..tostring({R}[{I}[3]])'
            elif junk_kind == 5:
                # 假循环计数：看起来像 for 循环初始化
                return f'local _j=#{{}} for _k=1,3 do _j=_j+1 end'
            elif junk_kind == 6:
                # 假全局读取：看起来像 GETGLOB 但丢弃
                return f'local _j=_G[{I}[2]]'
            elif junk_kind == 7:
                # 假数学运算：看起来像数学计算
                return f'local _j=math.floor({R}[{I}[2]])'
            else:
                # JUNK8: 假闭包创建：看起来像 CLOSURE 但丢弃
                return f'local _j=function() end'
        if op_name == "LOADK":
            return f'{R}[{I}[2]]={C}[{I}[3]+1]'
        elif op_name == "LOADSTR":
            # 三层加密字符串：懒解密（第一次访问解密，缓存）
            return f'{R}[{I}[2]]=_dec_str({S}[{I}[3]+1])'
        elif op_name == "LOADBOOL":
            return f'{R}[{I}[2]]=({I}[3]~=0)'
        elif op_name == "LOADNIL":
            return f'{R}[{I}[2]]=nil'
        elif op_name == "MOVR":
            return f'{R}[{I}[2]]={R}[{I}[3]]'
        elif op_name == "BINOP":
            return f'local d,a,b,c={I}[2],{I}[3],{I}[4],{I}[5] {bin_d}'
        elif op_name == "UNOP":
            return f'local d,a,c={I}[2],{I}[3],{I}[4] {un_d}'
        elif op_name == "JMP":
            # P1-2 控制流平坦化：跳转目标间接化
            # I[2] 是 jump_targets 表的索引（1-based），运行时查找真实 PC
            return f'{pc_var}={JT}[{I}[2]] _jmp=true'
        elif op_name == "CJMP":
            return f'if {R}[{I}[2]] then {pc_var}={JT}[{I}[3]] _jmp=true end'
        elif op_name == "NJMP":
            return f'if not {R}[{I}[2]] then {pc_var}={JT}[{I}[3]] _jmp=true end'
        elif op_name == "CALL":
            return (f'local _fn={R}[{I}[3]] local _args={{}} '
                    f'for _ai=1,{I}[4] do _args[_ai]={R}[{I}[4+_ai]] end '
                    f'{RETS}=table.pack(_fn(table.unpack(_args))) '
                    f'{R}[{I}[2]]={RETS}[1]')
        elif op_name == "CALLV":
            return (f'local _obj={R}[{I}[3]] local _m=_dec_str({S}[{I}[4]+1]) '
                    f'local _args={{}} '
                    f'for _ai=1,{I}[5] do _args[_ai]={R}[{I}[5+_ai]] end '
                    f'local _fn=_obj[_m] '
                    f'{RETS}=table.pack(_fn(_obj,table.unpack(_args))) '
                    f'{R}[{I}[2]]={RETS}[1]')
        elif op_name == "RET":
            return (f'if {I}[3] and {I}[3]>0 then '
                    f'local _rv={{}} for _ri=1,{I}[3] do _rv[_ri]={R}[{I}[3+_ri]] end '
                    f'return table.unpack(_rv) end '
                    f'return')
        elif op_name == "CLOSURE":
            # 合并外层 _uv 和本层捕获变量表 R[I[4]]，创建独立闭包 upvalue 副本。
            # 这样每次 CLOSURE 都有自己的 _uv 副本（不共享外层 _uv），
            # 解决 makeAdder(5)/makeAdder(10) 共享 n 的问题。
            return (f'local _uvc={{}} '
                    f'for _k,_v in pairs({UV}) do _uvc[_k]=_v end '
                    f'for _k,_v in pairs({R}[{I}[4]]) do _uvc[_k]=_v end '
                    f'{R}[{I}[2]]=function(...) return {RUN}({I}[3],_uvc,...) end')
        elif op_name == "PARAMS":
            return f'for _pi=1,{I}[2] do {R}[{I}[2+_pi]]={VA}[_pi] end'
        elif op_name == "GETRET":
            return f'{R}[{I}[2]]={RETS}[{I}[3]]'
        elif op_name == "NEWTAB":
            return f'{R}[{I}[2]]={{}}'
        elif op_name == "GETTAB":
            return f'{R}[{I}[2]]={R}[{I}[3]][{R}[{I}[4]]]'
        elif op_name == "SETTAB":
            return f'{R}[{I}[2]][{R}[{I}[3]]]={R}[{I}[4]]'
        elif op_name == "GETTABK":
            return f'{R}[{I}[2]]={R}[{I}[3]][_dec_str({S}[{I}[4]+1])]'
        elif op_name == "SETTABK":
            return f'{R}[{I}[2]][_dec_str({S}[{I}[3]+1])]={R}[{I}[4]]'
        elif op_name == "GETGLOB":
            return f'{R}[{I}[2]]=_G[_dec_str({S}[{I}[3]+1])]'
        elif op_name == "SETGLOB":
            return f'_G[_dec_str({S}[{I}[2]+1])]={R}[{I}[3]]'
        elif op_name == "GETUV":
            # 从闭包 upvalue 表读取捕获变量
            return f'{R}[{I}[2]]={UV}[_dec_str({S}[{I}[3]+1])]'
        elif op_name == "SETUV":
            # 写入闭包 upvalue 表（捕获变量）
            return f'{UV}[_dec_str({S}[{I}[2]+1])]={R}[{I}[3]]'
        elif op_name == "FORPREP":
            # I[6] 是 jump_targets 索引（1-based），跳到循环结束
            return (f'{R}[{I}[2]]={R}[{I}[3]] '
                    f'if ({R}[{I}[5]]>0 and {R}[{I}[3]]>{R}[{I}[4]]) '
                    f'or ({R}[{I}[5]]<0 and {R}[{I}[3]]<{R}[{I}[4]]) '
                    f'then {pc_var}={JT}[{I}[6]] _jmp=true end')
        elif op_name == "FORLOOP":
            # I[5] 是 jump_targets 索引（1-based），跳回循环开始
            return (f'{R}[{I}[2]]={R}[{I}[2]]+{R}[{I}[4]] '
                    f'if ({R}[{I}[4]]>0 and {R}[{I}[2]]<={R}[{I}[3]]) '
                    f'or ({R}[{I}[4]]<0 and {R}[{I}[2]]>={R}[{I}[3]]) '
                    f'then {pc_var}={JT}[{I}[5]] _jmp=true end')
        elif op_name == "BREAK":
            # BREAK 跳到循环结束 label（通过 jump_targets 间接查找）
            return f'{pc_var}={JT}[{I}[2]]'
        return f'-- unknown {op_name}'


# =============================================================================
# 三、公开 API
# =============================================================================
def vm_pro_compile(chunk, rng: random.Random, gen) -> Optional[str]:
    """尝试用付费级字节码 VM 编译整个 chunk。

    成功返回解释器 Lua 源码字符串，失败返回 None（调用方回退）。
    """
    compiler = ProVMCompiler(rng, gen)
    return compiler.compile_chunk(chunk)
