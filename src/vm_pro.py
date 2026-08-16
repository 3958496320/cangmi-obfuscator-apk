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
    "GETGLOB", "SETGLOB", "GETUV", "SETUV", "DECLUV", "COPYUV",
    "FORPREP", "FORLOOP",
    "BREAK",
    "LOADVA", "APPENDVA",  # varargs 表加载/追加（function(...){...}）
    "CALLVA",  # 带尾部 vararg 展开的函数调用 f(a, b, ...)
    "RETVA",   # return ... 或 return a, b, ...（vararg 返回值展开）
    "CALLMR",  # 带尾部多返回值展开的函数调用 f(a, b, g()) — g() 的所有返回值作为尾部参数
    "TABMR",   # 表构造器追加多返回值：{a, b, g()} — g() 的所有返回值追加到表
    "RETMR",   # return a, b, g() — g() 的所有返回值作为尾部返回值
]
# 假 opcode（编译器从不 emit，但占用 opcode 码点 + 在 dispatcher 有 handler）
# P3 升级：假 opcode 数量超过真 opcode（34 真 → 40 假），大幅增加反汇编噪音
# 反汇编工具会看到这些 opcode 并尝试分析其语义，浪费精力
_PRO_FAKE_OPCODES = [
    "JUNK1", "JUNK2", "JUNK3", "JUNK4", "JUNK5", "JUNK6", "JUNK7", "JUNK8",
    "JUNK9", "JUNK10", "JUNK11", "JUNK12", "JUNK13", "JUNK14", "JUNK15", "JUNK16",
    "JUNK17", "JUNK18", "JUNK19", "JUNK20", "JUNK21", "JUNK22", "JUNK23", "JUNK24",
    "JUNK25", "JUNK26", "JUNK27", "JUNK28", "JUNK29", "JUNK30", "JUNK31", "JUNK32",
    "JUNK33", "JUNK34", "JUNK35", "JUNK36", "JUNK37", "JUNK38", "JUNK39", "JUNK40",
]

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
        # 作用域遮蔽恢复栈：每层记录 (name, 外层寄存器或None)，pop 时恢复
        self._scope_shadows: List[List[Tuple[str, Optional[str]]]] = [[]]
        # 循环结束标签栈（用于 BREAK）
        self._loop_end_stack: List[str] = []
        # 循环 continue 标签栈（用于 CONTINUE，指向循环条件检查入口）
        self._loop_continue_stack: List[str] = []
        # 待编译函数
        self._pending_funcs: List[Tuple] = []
        # 闭包捕获变量集合：这些变量改用 _G 存储（GETGLOB/SETGLOB），实现跨调用帧共享
        self._captured_vars: set = set()
        # 是否正在编译函数体（True=函数体内，False=顶层）
        # 顶层引用捕获变量应走 GETGLOB（顶层无 _uv 表），函数体内走 GETUV
        self._in_function: bool = False
        # 花指令概率（控制插入密度，0.08 ≈ 每 12 条指令插 1 条）
        self._junk_rate = 0.08
        # 死寄存器计数器（花指令写入专用，不污染真寄存器）
        self._dead_reg_counter = 0
        # P3 字符串第四层：全局盐（运行期密钥派生用，编译期/运行期共用）
        # 从已随机化的 opcode 表派生，不额外消耗 rng，避免影响后续指令编译
        self._str_salt = sum(self.opcode.values()) & 0xFFFF

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
        P3 升级：8 类花指令随机选择，覆盖更多指令模式。
        1) LOADK 假常量到死寄存器（赋值模式）
        2) LOADNIL 到死寄存器（初始化模式）
        3) MOVR 死寄存器互相拷贝（数据流模式）
        4) LOADBOOL 假布尔到死寄存器（条件赋值模式）
        5) BINOP 死寄存器运算（算术模式，结果丢弃）
        6) NEWTAB 死寄存器建表（表创建模式）
        7) GETTABK 死寄存器读表（表访问模式）
        8) 花指令链：LOADK+MOVR+BINOP 三连（复合模式，更难识别）
        9) C-4 不透明谓词：同值比较恒假 + CJMP 永假条件跳转，扰乱控制流分析
        所有花指令都用真 opcode（变体随机），让反汇编器以为是真实逻辑。"""
        if self.rng.random() > self._junk_rate:
            return
        kind = self.rng.randint(1, 9)
        if kind == 1:
            self._emit_raw("LOADK", self._dead_reg(), self._const_idx(self.rng.randint(0, 9999)))
        elif kind == 2:
            self._emit_raw("LOADNIL", self._dead_reg())
        elif kind == 3:
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            self._emit_raw("LOADNIL", d1)
            self._emit_raw("MOVR", d2, d1)
        elif kind == 4:
            # LOADBOOL 假布尔（条件赋值模式）
            self._emit_raw("LOADBOOL", self._dead_reg(), self.rng.choice([0, 1]))
        elif kind == 5:
            # BINOP 死寄存器运算（算术模式）
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            d3 = self._dead_reg()
            self._emit_raw("LOADK", d1, self._const_idx(self.rng.randint(1, 999)))
            self._emit_raw("LOADK", d2, self._const_idx(self.rng.randint(1, 999)))
            self._emit_raw("BINOP", d3, d1, d2, self.rng.randint(0, 20))
        elif kind == 6:
            # NEWTAB 死寄存器建表（表创建模式）
            self._emit_raw("NEWTAB", self._dead_reg())
        elif kind == 7:
            # GETTABK 死寄存器读表（表访问模式，需先建表）
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            self._emit_raw("NEWTAB", d1)
            self._emit_raw("GETTABK", d2, d1, self._str_idx("_junk"))
        elif kind == 8:
            # 花指令链：LOADK+MOVR+BINOP 三连（复合模式）
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            d3 = self._dead_reg()
            self._emit_raw("LOADK", d1, self._const_idx(self.rng.randint(1, 999)))
            self._emit_raw("MOVR", d2, d1)
            self._emit_raw("BINOP", d3, d1, d2, self.rng.randint(0, 20))
        else:
            # C-4 不透明谓词：同值比较恒假 + CJMP 永假条件跳转
            # LOADK dead1,K; LOADK dead2,K(同值); BINOP dead3,dead1,dead2,~= (恒假)
            # CJMP dead3, 1 (条件假不跳转，目标 1=合法 jump_target 索引)
            # 分析者看到条件跳转须判断真伪，CJMP 恒不执行，控制流不变
            kv = self._const_idx(self.rng.randint(1, 9999))
            d1 = self._dead_reg()
            d2 = self._dead_reg()
            d3 = self._dead_reg()
            self._emit_raw("LOADK", d1, kv)
            self._emit_raw("LOADK", d2, kv)
            self._emit_raw("BINOP", d3, d1, d2, self.bincode["~="])
            self._emit_raw("CJMP", d3, 1)

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
        # P2-1 运行期字节码自擦除：计算 safe_erase_set
        # 擦除策略：只擦「线性序言段」——即第一个跳转目标之前的 PC。
        # 这些 PC 是循环/分支之前的一次性初始化代码，执行完永不再回访，
        # 擦掉不影响任何控制流（含嵌套循环：内层循环体 PC 都 > 外层 min(jt)，受保护）。
        # 边界：safe_erase_pcs = { p | 1 <= p < min(jump_target_pcs) }
        #   - min(jt) 是第一个跳转目标（最早循环/分支入口），其前都是序言
        #   - CLOSURE 入口单独保护（_run 可被多次调用，其后的指令也保留）
        # 无跳转目标（纯线性脚本）时全部 PC 可擦。
        bc_len = len(self.prog) - 1
        jt_pcs = [self._labels.get(l, 1) for l in self._used_labels]
        for _, func_id in self._closure_patches:
            jt_pcs.append(self._labels.get(func_id, 1))
        if jt_pcs:
            first_jt = min(jt_pcs)
            self._safe_erase_pcs = [p for p in range(1, first_jt) if p >= 1]
        else:
            self._safe_erase_pcs = list(range(1, bc_len + 1))

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
        # 每个字符串独立密钥（基于位置派生），四层加密元数据存入 strs 池
        # 运行时解密：XOR(k3派生) -> XOR(k1) -> ADD(k2) -> 字节置换(perm)
        # P3 第四层 k3：运行期由 (idx*0x9E37+salt)&0xFF 派生，编译期同步应用
        # P3 密钥校验 chk：原始字节和的低 8 位，运行期解密后验证，防密钥篡改
        if not hasattr(self, '_str_keys'):
            self._str_keys: List[Tuple[int, int, List[int], int, int]] = []
        k1 = self.rng.randint(1, 0xFF)
        k2 = self.rng.randint(1, 0xFF)
        # 字节置换表（0-255 的排列，避免退化成恒等）
        perm = list(range(256))
        self.rng.shuffle(perm)
        idx = len(self.strs) + 1  # 1-based 索引，与运行期 s.idx 一致
        # 第四层派生密钥（编译期/运行期算法一致，均用 1-based idx）
        k3 = (idx * 0x9E37 + self._str_salt) & 0xFF
        if k3 == 0:
            k3 = 0x5A  # 避免 0 退化（异或 0 等于不加密）
        # 校验字节：原始 UTF-8 字节和的低 8 位
        chk = sum(s.encode('utf-8', errors='replace')) & 0xFF
        self.strs.append(s)
        self._str_keys.append((k1, k2, perm, k3, chk))
        return len(self.strs) - 1  # 0-based 索引（idx 仅用于 k3 派生与 s.idx 存储）

    # ---- 作用域 ----
    def _push_scope(self):
        self._local_stack.append(set())
        self._scope_shadows.append([])

    def _pop_scope(self):
        # 作用域退出：恢复被内层同名局部变量遮蔽的外层寄存器绑定。
        # 【作用域遮蔽修复】旧实现 _reg 是平坦名字表，do block / 内层作用域
        # 声明同名局部变量会直接复用外层寄存器，作用域结束后外层变量被
        # 内层值污染（local x=1 do local x=10 end print(x) 输出 10 而非 1）。
        self._local_stack.pop()
        shadows = self._scope_shadows.pop()
        for name, old_reg in reversed(shadows):
            if old_reg is None:
                self._reg.pop(name, None)
            else:
                self._reg[name] = old_reg

    def _declare_local(self, name: str):
        cur = self._local_stack[-1]
        if name in cur:
            return  # 同作用域重复声明：复用寄存器（Lua 顺序覆盖语义）
        cur.add(name)
        if name in self._reg:
            # 遮蔽外层同名绑定：本作用域分配全新寄存器，退出时恢复外层映射
            self._scope_shadows[-1].append((name, self._reg[name]))
            self._reg[name] = self._new_reg()
        else:
            self._scope_shadows[-1].append((name, None))

    def _is_local(self, name: str) -> bool:
        # 捕获变量不是局部变量（走 box/_uv），其他正常判断
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
                # 捕获变量：无论顶层还是函数体内，都走 GETUV 读 UV 表。
                # 顶层 _run(1, {}) 的 UV 表存储了所有 SETUV 写入的捕获变量；
                # 函数体内 UV 表是 CLOSURE 时从外层 UV 复制而来。
                # 之前仅对 _in_function=True 走 GETUV，导致顶层引用捕获变量时
                # 走 GETGLOB 读 _G（变量从未 SETGLOB）→ 返回 nil → 索引 nil 报错。
                self._emit("GETUV", dest_reg, self._str_idx(name))
            elif self._is_local(name):
                self._emit("MOVR", dest_reg, self._reg_of(name))
            else:
                # 未捕获变量：走 GETGLOB 读 _G
                # 注：顶层 local function 也会 SETGLOB 到 _G，保证函数体内 GETGLOB 能读到
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
        elif t == "Vararg":
            # `...` 表达式：加载当前调用的 varargs 表 va_var（{...}）
            # 用于 function(...) return {...} end 或 local t = {...} 等场景
            self._emit("LOADVA", dest_reg)
        elif t == "Dots":
            # 兼容别名
            self._emit("LOADVA", dest_reg)
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
            if fname in self._captured_vars:
                # 捕获变量函数：无论顶层还是函数体内，都走 GETUV 读 UV 表
                # （与 Name handler 的修复保持一致）
                func_reg = self._new_reg()
                self._emit("GETUV", func_reg, self._str_idx(fname))
            elif self._is_local(fname):
                func_reg = self._reg_of(fname)
            else:
                # 未捕获变量：走 GETGLOB
                func_reg = self._new_reg()
                self._emit("GETGLOB", func_reg, self._str_idx(fname))
        else:
            func_reg = self._compile_expr(func_node)
        # 检测尾部 vararg 参数：f(a, b, ...) 需要展开所有 varargs
        # 这种情况下使用 CALLVA 指令（带 varargs 展开）
        has_trailing_vararg = args and args[-1].type == "Vararg"
        if has_trailing_vararg:
            # 固定参数部分（不含尾部 ...）
            fixed_args = args[:-1]
            arg_regs = [self._compile_expr(a) for a in fixed_args]
            # CALLVA: 展开固定参数 + va_var 全部传给被调函数
            self._emit("CALLVA", dest_reg, func_reg, len(arg_regs), *arg_regs)
        elif args and args[-1].type in ("Call", "Invoke"):
            # 尾部多返回值展开：f(a, b, g()) — g() 的所有返回值作为尾部参数
            # 只有最后一个参数会展开所有返回值，中间参数取首个返回值（Lua 语义）
            fixed_args = args[:-1]
            arg_regs = [self._compile_expr(a) for a in fixed_args]
            # 编译最后一个 call — 这会填充 _rets（保留所有返回值）
            last_call_reg = self._new_reg()
            self._compile_call(args[-1], last_call_reg)
            # CALLMR: 固定参数 + _rets 的所有返回值作为尾部参数
            self._emit("CALLMR", dest_reg, func_reg, len(arg_regs), *arg_regs)
        else:
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
        # 检测尾部 vararg / 多返回值（与 _compile_call 保持一致）
        has_trailing_vararg = args and args[-1].type == "Vararg"
        if has_trailing_vararg:
            fixed_args = args[:-1]
            arg_regs = [self._compile_expr(a) for a in fixed_args]
            # CALLVVA: 方法调用 + vararg 展开（暂复用 CALLVA 语义，但带 self）
            # 这里用 CALLVA 但把 self 作为第一个固定参数
            # 实际上方法调用 obj:m(...) 等价于 obj.m(obj, ...)
            # 我们先取 _fn = obj[m]，再 CALLVA(_fn, obj, ...)
            func_reg = self._new_reg()
            self._emit("GETTABK", func_reg, obj_reg, self._str_idx(method_str))
            self._emit("CALLVA", dest_reg, func_reg, len(arg_regs) + 1, obj_reg, *arg_regs)
        elif args and args[-1].type in ("Call", "Invoke"):
            # 尾部多返回值展开：obj:m(a, b, g())
            fixed_args = args[:-1]
            arg_regs = [self._compile_expr(a) for a in fixed_args]
            last_call_reg = self._new_reg()
            self._compile_call(args[-1], last_call_reg)
            # obj:m(...) 等价于调用 obj.m(obj, ...)
            func_reg = self._new_reg()
            self._emit("GETTABK", func_reg, obj_reg, self._str_idx(method_str))
            # CALLMR: 固定参数（含 self）+ _rets 多返回值
            self._emit("CALLMR", dest_reg, func_reg, len(arg_regs) + 1, obj_reg, *arg_regs)
        else:
            arg_regs = [self._compile_expr(a) for a in args]
            self._emit("CALLV", dest_reg, obj_reg, self._str_idx(method_str),
                       len(arg_regs), *arg_regs)

    def _compile_function_expr(self, node, dest_reg: str, func_name: str = None):
        func_id = f"func_{id(node)}"
        # 闭包 UV 表（box 语义）：
        # 捕获变量在外层通过 DECLUV 声明为单元素 box（{value}）存于外层 _uv；
        # CLOSURE handler 会浅拷贝外层 _uv（box 引用共享），无需寄存器快照预填充。
        # 旧实现按寄存器值快照填充，导致闭包间不共享 upvalue（快照语义错误）。
        uv_reg = self._new_reg()
        self._emit("NEWTAB", uv_reg)
        # 【强度增强】诱饵 upvalue 污染：向闭包 UV 合并表注入随机名字的伪捕获项，
        # 误导逆向者分析「函数捕获了哪些变量」。诱饵名为 fresh 随机标识符，
        # 永不与任何真实变量名冲突（编译器只为真实捕获名发射 GETUV/SETUV/DECLUV），
        # 因此零语义影响、零兼容风险，仅增加 _uv 命名空间噪音。
        for _ in range(self.rng.randint(1, 3)):
            decoy_key = self.gen.fresh()
            decoy_val = self._new_reg()
            self._emit("LOADK", decoy_val, self._const_idx(self.rng.randint(0, 65535)))
            self._emit("SETTABK", uv_reg, self._str_idx(decoy_key), decoy_val)
        # CLOSURE 指令：[opcode, dest_reg, startPC(待回填), uv_reg]
        idx = self._emit("CLOSURE", dest_reg, 0, uv_reg)
        self._closure_patches.append((idx, func_id))
        self._pending_funcs.append((node, func_id))
        self._last_uv_reg = uv_reg  # 供调用方在 CLOSURE 后补充捕获
        return dest_reg

    def _compile_table(self, node, dest_reg: str):
        fields = node.get("fields") or []
        # 特殊优化：{...} → 直接复制 va_var（当前调用的 varargs 表）
        # 这保证 local t = {...} 的 t[1], t[2]... 是所有传入参数
        if len(fields) == 1:
            f = fields[0]
            if f.type in ("TableItem", "TableField"):
                key = f.get("key")
                val = f.get("value")
                if key is None and val is not None and val.type == "Vararg":
                    # {...} 必须创建一个新表，包含所有 vararg 值
                    # 用 NEWTAB + APPENDVA(1) 把 va_var 全部追加到新表
                    self._emit("NEWTAB", dest_reg)
                    self._emit("APPENDVA", dest_reg, 1)
                    return
        self._emit("NEWTAB", dest_reg)
        seq_idx = 0
        for field in fields:
            if field.type in ("TableItem", "TableField"):
                key = field.get("key")
                val = field.get("value")
                if key is None:
                    seq_idx += 1
                    # {...} 作为表元素：展开所有 varargs 到顺序索引
                    if val is not None and val.type == "Vararg":
                        # 需要 APPENDVA 指令把 va_var 全部追加到当前表
                        # 直接传 seq_idx 作为字面量（不经过 const_idx，避免索引误解）
                        self._emit("APPENDVA", dest_reg, seq_idx)
                        # 后续 seq_idx 无法预知数量，但常见用法 {...} 是唯一元素，直接 return
                        continue
                    # 尾部多返回值：{a, b, g()} — g() 的所有返回值追加到表末尾
                    # 只有最后一个无 key 字段才展开多返回值（Lua 语义）
                    is_last_seq = (field is fields[-1])
                    if is_last_seq and val is not None and val.type in ("Call", "Invoke"):
                        # 先编译该 call 填充 _rets，再 TABMR 追加
                        last_call_reg = self._new_reg()
                        self._compile_call(val, last_call_reg)
                        # 直接传 seq_idx 作为字面量
                        self._emit("TABMR", dest_reg, seq_idx)
                        # 多返回值数量未知，后续无法继续顺序索引（Lua 语义：多返回值后不能有更多无 key 字段）
                        continue
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

    def _store_name(self, name: str, val_reg: str, is_decl: bool = False):
        """把值存入变量。
        捕获变量（box 语义）：
        - 声明（is_decl=True，LocalAssign）：DECLUV 新建 box —— 每次执行到此（函数调用/循环迭代）
          都产生独立 box，与 Lua 局部变量语义一致；
        - 纯赋值：SETUV 写入既有 box（与外层/其他闭包共享）。
        局部变量：declare + MOVR。"""
        if name in self._captured_vars:
            self._emit("DECLUV" if is_decl else "SETUV", self._str_idx(name), val_reg)
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
                    self._store_name(name, tmp, is_decl=True)
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
                        # local 声明 → DECLUV 新 box（每次函数调用/循环迭代独立，
                        # 同名局部变量互不串扰；闭包经 box 引用共享该变量）
                        if val_regs[i] is not None:
                            self._emit("DECLUV", self._str_idx(name), val_regs[i])
                        else:
                            nil_reg = self._new_reg()
                            self._emit("LOADNIL", nil_reg)
                            self._emit("DECLUV", self._str_idx(name), nil_reg)
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
        elif t == "Continue":
            # continue = 跳到当前循环的起始（Continue label）
            if self._loop_continue_stack:
                self._jmp_ph("JMP", 0, label_key=self._loop_continue_stack[-1], field=1)
            else:
                # 无循环上下文：回退为 break 语义（顶层非法，但防御性处理）
                if self._loop_end_stack:
                    self._jmp_ph("JMP", 0, label_key=self._loop_end_stack[-1], field=1)
                else:
                    self._emit("JMP", 0)
        elif t == "Goto":
            # goto label → 跳到 label 定义处（同函数作用域内）
            label = node.get("label")
            if label:
                self._jmp_ph("JMP", 0, label_key=f"_goto_{label}", field=1)
        elif t == "Label":
            # ::label:: → 注册 jump target
            label = node.get("label")
            if label:
                self._label(f"_goto_{label}")
        elif t == "LocalFunction":
            name = node.get("name")
            func = node.get("func")
            self._declare_local(name)
            # 【box 语义】local function f 等价于 local f; f = function...
            # Lua 中局部名在闭包创建前已声明。被捕获（含自递归+被他人捕获的
            # 组合场景）时：先 DECLUV(nil) 声明 box → CLOSURE 复制带上 box 引用
            # → SETUV 把闭包值填入共享 box。这样函数体内自递归（GETUV）与
            # 外部捕获者（GETUV）读到的都是同一个 box，时序正确。
            if name in self._captured_vars:
                _nil = self._new_reg()
                self._emit("LOADNIL", _nil)
                self._emit("DECLUV", self._str_idx(name), _nil)
            self._compile_function_expr(func, self._reg_of(name), func_name=name)
            if name in self._captured_vars:
                self._emit("SETUV", self._str_idx(name), self._reg_of(name))
            # 顶层 local function 始终 SETGLOB 到 _G：
            # - 顶层引用（print(isEven(10))）走 GETGLOB 读取
            # - 前向引用（mutual recursion: isEven 调用尚未定义的 isOdd）走 GETGLOB
            # - 自递归（预扫描已 discard，不在 captured）函数体内走 GETGLOB 读取
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
        # continue: 跳回条件检查（start）
        self._loop_continue_stack.append(start)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()
        self._loop_continue_stack.pop()
        self._jmp_ph("JMP", 0, label_key=start, field=1)
        self._label(end)

    def _compile_repeat(self, node):
        start = f"repeat_start_{id(node)}"
        end = f"repeat_end_{id(node)}"
        # repeat 的 continue 跳到条件检查（end of body, before cond）
        cont = f"repeat_cont_{id(node)}"
        self._label(start)
        self._loop_end_stack.append(end)
        self._loop_continue_stack.append(cont)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._label(cont)
        cond_reg = self._compile_expr(node.get("cond"))
        self._loop_end_stack.pop()
        self._loop_continue_stack.pop()
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
        # 先声明再取寄存器：声明时若遮蔽外层同名变量会分配全新寄存器，
        # 之后的 _reg_of(var) 才与循环体引用一致
        self._declare_local(var)
        loop_var_reg = self._reg_of(var)
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
        # 循环变量被闭包捕获：每次迭代进入循环体时 DECLUV 新 box。
        # Lua 语义：for 的循环变量每轮都是全新变量，
        # fns[i] = function() return i end 各闭包捕获各自的 i。
        if var in self._captured_vars:
            self._emit("DECLUV", self._str_idx(var), loop_var_reg)
        self._loop_end_stack.append(end_label)
        # continue: 跳到 FORLOOP（递增 + 条件重检）
        forloop_label = f"forloop_{id(node)}"
        self._loop_continue_stack.append(forloop_label)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()
        self._loop_continue_stack.pop()
        # FORLOOP: var += step; 如果仍满足条件则跳回 loop_start
        # inst = [op, var_reg, limit_store, step_store, back_offset]
        # back_offset 在 field=4（第 5 个元素）
        # 用 label 回填，避免花指令插入导致偏移计算错误
        self._label(forloop_label)
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

        # 循环变量被闭包捕获：每轮迭代 DECLUV 新 box（Lua for-in 语义：每轮全新变量）
        for v in vars_:
            if v in self._captured_vars:
                self._emit("DECLUV", self._str_idx(v), self._reg_of(v))

        # 循环体
        self._loop_end_stack.append(end_label)
        # continue: 跳回 start_label（重新调用迭代器）
        self._loop_continue_stack.append(start_label)
        self._push_scope()
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._pop_scope()
        self._loop_end_stack.pop()
        self._loop_continue_stack.pop()

        # 跳回循环开始
        self._jmp_ph("JMP", 0, label_key=start_label, field=1)
        self._label(end_label)

    def _compile_return(self, node):
        exprs = node.get("exprs") or []
        if not exprs:
            self._emit("RET")
        else:
            # 检查最后一个表达式是否为 vararg（return ... 或 return f(), ...）
            # 这种情况下需要展开 vararg 的所有值作为返回值
            if len(exprs) == 1 and exprs[0].type == "Vararg":
                # return ... → 直接返回 va_var 的所有值（I[2]=0 表示无固定值）
                self._emit("RETVA", 0)
                return
            if len(exprs) >= 2 and exprs[-1].type == "Vararg":
                # return a, b, ... → 固定部分 + vararg 展开
                fixed_regs = [self._compile_expr(e) for e in exprs[:-1]]
                self._emit("RETVA", len(fixed_regs), *fixed_regs)
                return
            # 尾部多返回值：return a, b, g() — g() 的所有返回值作为尾部返回值
            # 只有最后一个表达式才展开多返回值（Lua 语义）
            if len(exprs) >= 1 and exprs[-1].type in ("Call", "Invoke"):
                fixed_regs = [self._compile_expr(e) for e in exprs[:-1]]
                # 编译最后一个 call — 填充 _rets
                last_call_reg = self._new_reg()
                self._compile_call(exprs[-1], last_call_reg)
                # RETMR: 固定返回值 + _rets 的所有返回值作为尾部
                # 这里复用 RETVA 的 _rv 拼接逻辑，但用 _rets 替代 _va
                self._emit("RETMR", len(fixed_regs), *fixed_regs)
                return
            regs = [self._compile_expr(e) for e in exprs]
            self._emit("RET", regs[0], len(regs), *regs)

    # ---- 函数体编译 ----
    def _compile_function_body(self, node, func_id: str):
        params = node.get("params") or []
        old_locals = self._local_stack[:]
        old_reg = self._reg
        old_shadows = self._scope_shadows
        old_in_func = self._in_function
        self._local_stack = [set()]
        self._reg = {}
        self._scope_shadows = [[]]
        self._in_function = True  # 进入函数体：捕获变量走 GETUV
        # 在函数体开头插入 PARAMS 指令（label 必须在 PARAMS 之前，确保 _run 从 PARAMS 开始）
        self._label(func_id)
        # 必须先声明参数再取寄存器：声明时若遮蔽外层同名变量会分配全新寄存器，
        # PARAMS 写入的寄存器与函数体引用的寄存器才能保持一致
        for p in params:
            self._declare_local(p)
        param_regs = [self._reg_of(p) for p in params]
        self._emit("PARAMS", len(params), *param_regs)
        # 捕获变量参数：PARAMS 把参数加载到寄存器后，DECLUV 新建 box 存入 _uv。
        # 必须用 DECLUV（新 box）而非 SETUV：同一闭包多次调用时参数各自独立
        # （local function makeAdder(n) return function(x) return x + n end end，
        #  makeAdder(1)/makeAdder(2) 的内层闭包不应共享 n）。
        for p in params:
            if p in self._captured_vars:
                self._emit("DECLUV", self._str_idx(p), self._reg_of(p))
        for s in (node.get("body") or []):
            self._compile_stmt(s)
        self._emit("RET")
        self._local_stack = old_locals
        self._reg = old_reg
        self._scope_shadows = old_shadows
        self._in_function = old_in_func

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

        # P2-2 寄存器虚拟化：收集所有寄存器名，生成运行期映射表 RK
        # RK[reg_name] = random_int，运行期 R[RK[name]] 间接寻址防数据流追踪
        # enable_register_virt=False 时退化为恒等映射 RK[name]=name（调试/兼容用）
        rk_var = gen.fresh()
        all_regs = set()
        for ins in self.prog[1:]:
            for elem in ins[1:]:
                if isinstance(elem, str):
                    all_regs.add(elem)
        _enable_rv = getattr(self, '_enable_register_virt', True)
        if _enable_rv and all_regs:
            rk_range = max(len(all_regs) * 3 + 100, 1000)
            rk_keys = self.rng.sample(range(1, rk_range + 1), len(all_regs))
            rk_items = []
            for name, k in zip(sorted(all_regs), rk_keys):
                rk_items.append(f'[{self._fmt_str(name)}]={k}')
        else:
            # 恒等映射：RK[name] = name，R[RK[name]] = R[name]（无虚拟化）
            rk_items = [f'[{self._fmt_str(name)}]={self._fmt_str(name)}'
                       for name in sorted(all_regs)]
        rk_lua = "{" + ",".join(rk_items) + "}"

        bin_dispatch = self._gen_binop_dispatch(reg_var, rk_var)
        un_dispatch = self._gen_unop_dispatch(reg_var, rk_var)
        # P1-2 控制流平坦化：跳转目标间接表
        jt_var = gen.fresh()  # jump_targets 表变量名
        # P2-3 解释器分片嵌套：敏感 opcode 走独立 secure dispatcher
        secure_candidates = ["CALL", "CALLV", "RET", "CLOSURE",
                             "GETGLOB", "SETGLOB", "GETUV", "SETUV", "DECLUV"]
        secure_opnames = [op for op in secure_candidates if op in self.opcode]
        main_chain, secure_chain, secure_codes = self._gen_handler_chain(
            op_var, reg_var, consts_var, strs_var, pc_var, inst_var,
            bin_dispatch, un_dispatch, run_var, rets_var, va_var, uv_var,
            jt_var, rk_var, secure_opnames)
        sec_var = gen.fresh()  # secure opcode 查找表变量名
        sec_items = ",".join(f'[{c}]=true' for c in secure_codes)
        sec_lua = "{" + sec_items + "}"

        # 自修改 dispatcher：opcode 字段额外异或 shift_key
        # shift_key = (pc // shift_period) & 0xFFFF，每 shift_period 条指令变化一次
        # 反汇编器无法静态确定 opcode 含义，必须模拟 shift_key 演化
        shift_period = self.rng.randint(7, 19)
        shift_var = gen.fresh()
        # P3-3 多轴 VM：在 _encrypt_program 之前设置轴参数（编译期同步应用）
        axis_period = self.rng.randint(23, 47)
        axis_seed = self.rng.randint(0x100, 0xFFFF)
        self._axis_period = axis_period
        self._axis_seed = axis_seed
        bc_lua = self._encrypt_program(key, shift_period)
        ad_period = self.rng.randint(50, 150)
        # 反 trace 细化：高频时间检测阈值 + hook 检测
        # time_limit：每 ad_period 条指令的累计耗时上限（秒）
        # 单步执行会让这个值暴涨 100-1000 倍，触发静默 corrupt
        # 注意阈值下限 1.0s：真实注入器（手机端/低端PC）在 GC 停顿、UI 渲染
        # 抖动、后台抢占时短窗耗时可达数百毫秒，过低的阈值会把正常玩家
        # 误判为调试器导致脚本静默无反应（实测根因之一）。
        # 单步执行耗时 >> 1s，1.0-3.0s 仍能可靠区分。
        time_limit = self.rng.choice([1.0, 1.5, 2.0, 3.0])
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
        # 序列化段表：{ {lo, hi, crc32, adler32, fnv}, ... }  C-3 三算法冗余
        seg_items = []
        for lo, hi, crc, adler, fnv in segments:
            seg_items.append(f'{{{lo},{hi},{crc},{adler},{fnv}}}')
        crc_segs_lua = "{" + ",".join(seg_items) + "}"
        # P2-1 兼容 P1-3：预计算与 safe_erase_pcs 重叠的 CRC 段索引。
        # 这些段在运行期会被擦除（bc[pc]=噪音），校验必然失配。
        # 预标记后校验轮询跳过这些段，其余段保持完整检测覆盖。
        safe_set_for_segs = getattr(self, '_safe_erase_pcs', [])
        erased_seg_indices = set()
        if safe_set_for_segs:
            for si, (lo, hi, _c, _a, _f) in enumerate(segments, start=1):
                if any(lo <= p <= hi for p in safe_set_for_segs):
                    erased_seg_indices.add(si)
        erased_seg_var = gen.fresh()  # 运行期「已擦除段」集合（1-based 段索引 → true）
        erased_seg_list_var = gen.fresh()  # 临时：已擦除段索引列表
        if erased_seg_indices:
            esi_items = ",".join(str(i) for i in sorted(erased_seg_indices))
            erased_seg_lua = f'{{{esi_items}}}'
        else:
            erased_seg_lua = '{}'
        # 运行期三算法校验：CRC32 + Adler32 + FNV-1a，C-3 多算法冗余
        # 与编译期 _compute_seg_crc/_adler32/_fnv 完全一致（同表、同字节序、同遍历）
        # 每个数字元素拆成 4 个小端字节喂入三算法，返回三校验和。
        # 攻击者只修复单一算法（如 CRC32）仍会被另两算法检出。
        crc_fn_lua = (
            f'local {crc_tab_var}=nil '
            f'local function {crc_fn_var}(_bc,_lo,_hi) '
            f'if not {crc_tab_var} then '
            f'{crc_tab_var}={{}} '
            f'for _i=0,255 do local _c=_i for _=1,8 do '
            f'if _c%2==1 then _c=(_c//2)~0xEDB88320 else _c=_c//2 end end '
            f'{crc_tab_var}[_i]=_c end end '
            f'local _crc=0xFFFFFFFF '
            f'local _a=1 local _b=0 '
            f'local _h=0x811C9DC5 '
            f'for _pc=_lo,_hi do local _ins=_bc[_pc] '
            f'if _ins then for _i=1,#_ins do local _e=_ins[_i] '
            f'if type(_e)=="number" then local _v=_e '
            f'local _b0=_v%256 local _b1=(_v//256)%256 '
            f'local _b2=(_v//65536)%256 local _b3=(_v//16777216)%256 '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b0)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b1)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b2)%256] '
            f'_crc=(_crc//256)~{crc_tab_var}[(_crc~_b3)%256] '
            f'_a=(_a+_b0)%65521 _b=(_b+_a)%65521 '
            f'_a=(_a+_b1)%65521 _b=(_b+_a)%65521 '
            f'_a=(_a+_b2)%65521 _b=(_b+_a)%65521 '
            f'_a=(_a+_b3)%65521 _b=(_b+_a)%65521 '
            f'_h=(_h~_b0)&0xFFFFFFFF _h=(_h*0x01000193)&0xFFFFFFFF '
            f'_h=(_h~_b1)&0xFFFFFFFF _h=(_h*0x01000193)&0xFFFFFFFF '
            f'_h=(_h~_b2)&0xFFFFFFFF _h=(_h*0x01000193)&0xFFFFFFFF '
            f'_h=(_h~_b3)&0xFFFFFFFF _h=(_h*0x01000193)&0xFFFFFFFF '
            f'end end end end '
            f'return (_crc~0xFFFFFFFF)&0xFFFFFFFF,((_b<<16)|_a)&0xFFFFFFFF,_h end'
        )

        # 生成 jump_targets 表：每个被引用的 label 对应一个 PC 值
        jt_items = []
        for i, label_key in enumerate(getattr(self, '_used_labels', [])):
            target_pc = self._labels.get(label_key, 1)
            jt_items.append(f'[{i+1}]={target_pc}')
        jt_lua = "{" + ",".join(jt_items) + "}"

        # P2-1 运行期字节码自擦除：safe_erase_set
        # 运行期维护 erased_watermark，每步把 (pc - lag) 且在 safe_set 中、
        # 且超过 watermark 的 PC 置 nil（bc[pc]=nil → 下次访问 break）。
        # safe_set 已在 _patch_all 排除所有 jump_targets/CLOSURE 入口，回跳安全。
        safe_set = getattr(self, '_safe_erase_pcs', [])
        safe_set_var = gen.fresh()
        watermark_var = gen.fresh()
        lag_var = self.rng.randint(5, 15)
        if safe_set:
            ss_items = ",".join(str(p) for p in safe_set)
            safe_set_lua = f'{{{ss_items}}}'
        else:
            safe_set_lua = '{}'
        erase_flag_var = gen.fresh()  # safe_set 查找表（set[pc]=true）
        erase_done_var = gen.fresh()  # 擦除发生标志，置 true 后 CRC 跳过

        # P3-1 环境指纹绑定：运行期检测 _VERSION/collectgarbage/debug.getregistry
        # 软检测策略：只检存在性/异常值，不绑定具体版本（兼容多 Lua 环境）

        # P3-2 反 Hook：关键 API 完整性校验
        # 编译期记录关键 API 的 tostring 签名哈希，运行期比对
        # 被包装/hook 后签名变化 → corrupt
        api_chk_var = gen.fresh()        # API 校验结果变量
        api_expect_var = gen.fresh()     # 预期签名哈希表

        # P3-3 多轴 VM：轴参数已在 _encrypt_program 之前设置（编译期同步应用）

        # P3-2 反 Hook：关键 API 预期签名
        # 运行期对 _G.print / _G.pairs / _G.string.byte 做 tostring 类型校验
        # 被 hook/wrap 后 type 可能变化 → corrupt
        # enable_anti_hook=False 时跳过此检测（兼容特殊注入器环境）
        _enable_ah = getattr(self, '_enable_anti_hook', True)
        _api_names = ['print', 'pairs', 'ipairs', 'tostring', 'tonumber']
        _api_expect_items = []
        for _an in _api_names:
            _api_expect_items.append(f'["{_an}"]=true')
        api_expect_lua = '{' + ",".join(_api_expect_items) + '}'
        # 反 Hook 检测代码片段（仅在 enable_anti_hook=True 时注入）
        if _enable_ah:
            _anti_hook_lua = f'''
                -- P3-2 反 Hook：关键 API 存在性校验
                -- 检测 _G.print/pairs/ipairs/tostring/tonumber 是否被删除/替换为 nil
                -- 被 hook 删除 → corrupt（宽松检测：只检 nil，避免误判环境差异）
                for _an, _ in pairs({api_expect_var}) do
                    if _G[_an] == nil then {corrupt_var} = true end
                end'''
        else:
            _anti_hook_lua = '\n                -- P3-2 反 Hook：已禁用（enable_anti_hook=False）'

        src = f'''-- [AI-DETECT] 付费级字节码 VM 保护
local function {fn_name}()
    local {bc_var} = {bc_lua}
    local {key_var} = {key}
    local {consts_var} = {consts_lua}
    local {jt_var} = {jt_lua}
    local {rk_var} = {rk_lua}  -- P2-2 寄存器虚拟化映射表
    local {sec_var} = {sec_lua}  -- P2-3 secure opcode 查找表
    {strs_lua}
    local {corrupt_var} = false  -- 反 trace 触发标志：true 时静默 corrupt 内部状态
    {crc_fn_lua}
    local {crc_segs_var} = {crc_segs_lua}
    -- P3-2 反 Hook：关键 API 预期签名
        local {api_expect_var} = {api_expect_lua}
    -- P2-1 兼容 P1-3：预标记将与 safe_erase_pcs 重叠的 CRC 段（擦除后必然失配，跳过）
        local {erased_seg_list_var} = {erased_seg_lua}
        local {erased_seg_var} = {{}}
        for _i = 1, #{erased_seg_list_var} do {erased_seg_var}[{erased_seg_list_var}[_i]] = true end
    -- P2-1 自擦除：safe_erase_set（已排除 jump_targets/CLOSURE 入口，回跳安全）
        local {safe_set_var} = {safe_set_lua}
        local {erase_flag_var} = {{}}
        for _i = 1, #{safe_set_var} do {erase_flag_var}[{safe_set_var}[_i]] = true end
        local {erase_done_var} = false  -- 保留兼容（不再永久跳过 CRC，改用 erased_seg 精细跳过）
        local function {run_var}({pc_var}_start, {uv_var}, ...)
        if {uv_var} == nil then {uv_var} = {{}} end
        -- varargs 表：用 table.pack 保留 nil 参数（select('#', ...) 给出真实数量）
        -- 之前用 {{...}} 会丢失 nil 之后的所有参数（{{}} 按 # 取长度）
        local {va_var} = table.pack(...)
        local {pc_var} = {pc_var}_start
        local {reg_var} = {{}}
        local {rets_var} = {{}}
        local {ad_var} = 0
        local {bc_len_var} = #{bc_var}
        local {last_time_var} = os.clock()
        local {seg_chk_var} = 0
        local {watermark_var} = 0  -- P2-1 自擦除水位线（已擦除到的最高 PC）
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
            -- P3-3 多轴 VM：额外异或轴密钥（位置相关，编译期同步应用）
            -- axis_key = ((pc // axis_period) * axis_seed) & 0xFFFF
            -- 每轴指令段用不同密钥，反汇编器须模拟轴切换才能解码
            {op_var} = {op_var} ~ ((({pc_var} // {axis_period}) * {axis_seed}) & 0xFFFF)
            {ad_var} = {ad_var} + 1
            if {ad_var} % {ad_period} == 0 then
                -- 反 trace 1: _G 表大小监测
                -- 【兼容性修复】真实执行器（Ninja/Synapse/Wave/Delta 等）会向 _G
                -- 注入数百到上千个自定义全局（getgenv/hookfunction/fire* 全家桶），
                -- 旧阈值 500-2000 会把真实注入器误判为异常环境并 return nil
                -- 静默退出 —— 这是「混淆后无反应」的实测根因之一。
                -- 新阈值 20000：只有刻意构造的巨型沙箱才会触及，正常永不触发。
                local _gc = 0
                for _ in pairs(_G) do _gc = _gc + 1 end
                if _gc > 20000 then return nil end
                -- 反 trace 2: 高频时间检测
                -- 正常执行 ad_period 条指令耗时 << time_limit
                -- 单步/trace 会让耗时暴涨 100-1000 倍
                local {time_var} = os.clock()
                if {time_var} - {last_time_var} > {time_limit} then
                    {corrupt_var} = true
                end
                -- last_time_var 在本块末尾重置（见 P1-3 后），避免 CRC 计算耗时被计入下一窗口
                -- 反 trace 3: debug hook 检测
                -- 【兼容性修复】部分执行器自设 count 型 hook 做超时看门狗，属正常环境。
                -- 只检测 line 型 hook（断点/单步 trace 的标志），count/call 型忽略。
                -- debug.gethook() 返回 hook函数, mask字符串, count
                local {hook_chk_var} = debug and debug.gethook
                if {hook_chk_var} then
                    local _okh, _hf, _hm = pcall(debug.gethook)
                    if _okh and _hf and type(_hm) == "string" and _hm:find("l", 1, true) then
                        {corrupt_var} = true
                    end
                end
                -- 反 trace 4: 调用栈深度检测
                -- VM 正常调用栈深度有限，过深说明被包装/trace
                if debug and debug.getinfo then
                    local _di = debug.getinfo(3, "f")
                    -- _di 为 nil 说明栈很浅（正常），非 nil 说明有外层包装
                    -- 但 VM 自身也有包装，这里只检测极深栈（>20 层）
                    local _depth = 0
                    local _frame = debug.getinfo(1, "f")
                    while _frame and _depth < 40 do
                        _depth = _depth + 1
                        _frame = debug.getinfo(_depth + 1, "f")
                    end
                    if _depth >= 35 then {corrupt_var} = true end
                end
                -- P3-1 环境指纹绑定：_VERSION 校验
                -- 【兼容性修复】部分执行器沙箱合法地移除 _VERSION，只在其
                -- 「存在但被篡改为非字符串」时才判异常。
                if _VERSION ~= nil and type(_VERSION) ~= "string" then {corrupt_var} = true end
                -- P3-1b collectgarbage 异常检测
                -- 【兼容性修复】真实游戏/执行器 Lua 堆可达数百 MB，50MB 旧阈值误判。
                if collectgarbage then
                    local _mem = collectgarbage("count")
                    if _mem and _mem > 1000000 then {corrupt_var} = true end
                end
                -- P3-1c debug.getregistry 注入检测
                -- 【兼容性修复】执行器自身向 registry 注册大量对象，200 旧阈值误判。
                if debug and debug.getregistry then
                    local _ok, _reg = pcall(debug.getregistry)
                    if _ok and _reg then
                        local _rc = 0
                        for _ in pairs(_reg) do _rc = _rc + 1 end
                        if _rc > 20000 then {corrupt_var} = true end
                    end
                end
                -- P3-2 反 Hook：关键 API 存在性校验（条件注入）
                {_anti_hook_lua}
                -- P1-3 字节码防篡改校验：CRC32 分段轮询
                -- 每个 ad_period 周期校验一段，轮询覆盖全部段。
                -- 任一字节被篡改 → 校验和失配 → 静默 corrupt。
                -- P2-1 兼容：跳过与 safe_erase_pcs 重叠的段（已预标记 erased_seg），
                -- 其余段保持完整 CRC 检测覆盖。
                local _ns = #{crc_segs_var}
                if _ns > 0 then
                    local _si = ({seg_chk_var} % _ns) + 1
                    if not {erased_seg_var}[_si] then
                        local _seg = {crc_segs_var}[_si]
                        -- C-3 三算法并行校验：CRC32 + Adler32 + FNV-1a
                        -- 任一失配即 corrupt，防攻击者只修复单一算法
                        local _c,_a,_f = {crc_fn_var}({bc_var}, _seg[1], _seg[2])
                        if _c ~= _seg[3] or _a ~= _seg[4] or _f ~= _seg[5] then {corrupt_var} = true end
                    end
                    {seg_chk_var} = {seg_chk_var} + 1
                end
                -- 重置时间窗口基准：把本块全部工作（含 CRC 计算）排除出下一窗口
                {last_time_var} = os.clock()
                -- P2-1 运行期字节码自擦除：防 dump（C-2 升级：写噪音而非 nil）
                -- 在 CRC 校验之后执行（CRC 先看到完整 bc 表，再擦除历史指令）。
                -- 擦除 (pc - lag) 且在 safe_set 中、且超过 watermark 的 PC。
                -- safe_set 仅含第一个跳转目标之前的线性序言，永不被回跳重访。
                -- 擦除段已在编译期预标记到 erased_seg，CRC 自动跳过；其余段不受影响。
                -- C-2 写噪音：用基于 pc 的确定性伪随机加密大数表替换原指令，
                -- 保持表结构与字段数不变，内容形似周围加密真指令。
                -- 防 dump 工具通过连续 nil 模式识别擦除痕迹。
                local _ep = {pc_var} - {lag_var}
                if _ep > {watermark_var} and {erase_flag_var}[_ep] then
                    -- C-3 增强首次校验：第一次擦除前，序言段（erased_seg）尚未被擦除，
                    -- 此时对序言段做一次完整三算法校验，检测篡改后才开始擦除。
                    -- 修复序言段被跳过校验导致篡改漏检的问题。
                    if not {erase_done_var} then
                        {erase_done_var} = true
                        for _esi, _ in pairs({erased_seg_var}) do
                            local _seg = {crc_segs_var}[_esi]
                            local _c,_a,_f = {crc_fn_var}({bc_var}, _seg[1], _seg[2])
                            if _c ~= _seg[3] or _a ~= _seg[4] or _f ~= _seg[5] then {corrupt_var} = true end
                        end
                    end
                    local _oi = {bc_var}[_ep]
                    if type(_oi) == "table" then
                        local _nz = {{}}
                        local _s = _ep * 2654435761 + 1
                        for _i = 1, #_oi do
                            _s = (_s * 1103515245 + 12345) & 0xFFFFFFFF
                            _nz[_i] = _s
                        end
                        {bc_var}[_ep] = _nz
                    end
                    {watermark_var} = _ep
                end
            end
            -- corrupt 触发：静默破坏内部状态（不报错，让结果错乱，比直接崩更难排查）
            if {corrupt_var} then
                {reg_var}[1] = nil
                {reg_var}[2] = "corrupted"
                {pc_var} = {pc_var} + {ad_var} % 7 + 1
            end
            -- jump_flag：跳转指令设置后，跳过 pc+1（因为已设绝对目标）
            local _jmp = false
            -- P2-3 分片嵌套：secure opcode 走独立 dispatcher 链
            if {sec_var}[{op_var}] then
                {secure_chain}
            else
                {main_chain}
            end
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
                # P3-3 多轴 VM：opcode 额外异或轴密钥
                # axis_key = ((pc // axis_period) * axis_seed) & 0xFFFF
                # 编译期与运行期同步，确保解密后 opcode 正确
                axis_key = ((pc // self._axis_period) * self._axis_seed) & 0xFFFF
                enc = (enc ^ axis_key) & 0xFFFFFFFF
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

    def _compute_seg_adler32(self, lo: int, hi: int, key: int, shift_period: int) -> int:
        """Adler-32 校验和（RFC 1950）。与运行期逐字节一致：数字元素拆 4 小端字节。
        C-3 多算法冗余：攻击者只修复 CRC32 仍会被 Adler32 检出。"""
        a, b = 1, 0
        for pc in range(lo, hi + 1):
            ins = self.prog[pc]
            for i, p in enumerate(ins, start=1):
                is_num, val = self._encrypted_elem(pc, i, p, key, shift_period)
                if not is_num:
                    continue
                v = val & 0xFFFFFFFF
                for j in range(4):
                    byte = (v >> (8 * j)) & 0xFF
                    a = (a + byte) % 65521
                    b = (b + a) % 65521
        return ((b << 16) | a) & 0xFFFFFFFF

    def _compute_seg_fnv(self, lo: int, hi: int, key: int, shift_period: int) -> int:
        """FNV-1a 32-bit 校验和。与运行期逐字节一致：数字元素拆 4 小端字节。
        C-3 多算法冗余：第三算法，进一步增加绕过难度。"""
        h = 0x811C9DC5
        for pc in range(lo, hi + 1):
            ins = self.prog[pc]
            for i, p in enumerate(ins, start=1):
                is_num, val = self._encrypted_elem(pc, i, p, key, shift_period)
                if not is_num:
                    continue
                v = val & 0xFFFFFFFF
                for j in range(4):
                    byte = (v >> (8 * j)) & 0xFF
                    h = (h ^ byte) & 0xFFFFFFFF
                    h = (h * 0x01000193) & 0xFFFFFFFF
        return h & 0xFFFFFFFF

    def _build_segments(self, key: int, shift_period: int):
        """把字节码流切成 3-6 段，每段计算三算法校验和（CRC32 + Adler32 + FNV-1a）。
        返回 [(lo, hi, crc32, adler32, fnv), ...]，运行期三路并行校验，
        篡改任一字节 → 任一算法失配 → 静默 corrupt。
        C-3 多算法冗余：防攻击者只修复单一算法绕过。"""
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
            adler = self._compute_seg_adler32(lo, hi, key, shift_period)
            fnv = self._compute_seg_fnv(lo, hi, key, shift_period)
            segments.append((lo, hi, crc, adler, fnv))
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

    def _encrypt_str(self, s: str, k1: int, k2: int, perm: List[int], k3: int) -> str:
        """四层加密字符串：
        layer1: 字节置换 perm[b]
        layer2: ADD k2
        layer3: XOR k1
        layer4: XOR k3（运行期派生密钥，编译期同步应用，最外层）
        输出为 Lua 字符串字面量（含转义），运行时反向解密。"""
        enc_bytes = []
        for b in s.encode('utf-8', errors='replace'):
            b = perm[b & 0xFF]          # layer1 置换
            b = (b + k2) & 0xFF          # layer2 ADD
            b = b ^ k1                    # layer3 XOR
            b = b ^ k3                    # layer4 运行期派生密钥 XOR（最外层）
            enc_bytes.append(b)
        # 编码为 Lua 转义字符串
        return '"' + ''.join(f'\\{b:03d}' for b in enc_bytes) + '"'

    def _gen_str_pool_lua(self, strs_var: str) -> str:
        """生成 strs 池：每个元素是加密字节串 + 元数据，运行时按需解密。
        返回 Lua 代码：定义 strs 表 + 解密函数。
        P3 升级：四层加密（layer4 运行期派生密钥）+ 解密后字节和校验。"""
        if not self.strs:
            return f'local {strs_var} = {{}}'
        salt = self._str_salt
        items = []
        for i, s in enumerate(self.strs):
            k1, k2, perm, k3, chk = self._str_keys[i]
            enc = self._encrypt_str(s, k1, k2, perm, k3)
            # 存储：{data, k1, k2, perm, idx, salt, chk, dec}
            # idx/salt 运行期派生 layer4 密钥；chk 解密后校验字节和防密钥篡改
            # perm 表只存 0-255 值（运行时构造逆表），用字符串压缩以减小体积
            perm_str = '"' + ''.join(f'\\{b:03d}' for b in perm) + '"'
            items.append(f'[{i+1}]={{data={enc},k1={k1},k2={k2},perm={perm_str},idx={i+1},salt={salt},chk={chk},dec=nil}}')
        # 生成解密函数：懒解密，第一次访问时解密并缓存
        # 解密顺序（加密逆序）：XOR(k3) -> XOR(k1) -> SUB(k2) -> inv_perm
        return f'''local {strs_var} = {{{",".join(items)}}}
        local function _dec_str(s)
            if s.dec then return s.dec end
            -- P3 layer4：运行期派生密钥 k3 = (idx*0x9E37+salt)&0xFF
            local k3 = (s.idx * 0x9E37 + s.salt) & 0xFF
            if k3 == 0 then k3 = 0x5A end
            local inv = {{}}
            for i = 0, 255 do inv[(string.byte(string.sub(s.perm, i+1, i+1)))] = i end
            local out = {{}}
            local sum = 0
            for i = 1, #s.data do
                local b = string.byte(string.sub(s.data, i, i))
                b = b ~ k3
                b = b ~ s.k1
                b = (b - s.k2) % 256
                b = inv[b]
                out[i] = string.char(b)
                sum = (sum + b) & 0xFF
            end
            -- P3 密钥校验：字节和不匹配说明密钥(k1/k2/k3/perm)被篡改
            if sum ~= s.chk then return nil end
            s.dec = table.concat(out)
            return s.dec
        end'''

    def _gen_binop_dispatch(self, reg_var, rk_var) -> str:
        # P2-2 寄存器虚拟化：R[d] → R[RK[d]]，间接寻址防数据流追踪
        R = reg_var
        RK = rk_var
        code_to_op = {c: op for op, c in self.bincode.items()}
        parts = []
        for code in range(len(_PRO_BINOPS)):
            op = code_to_op[code]
            if op == "and":
                parts.append(f'if c=={code} then {R}[{RK}[d]]={R}[{RK}[a]] and {R}[{RK}[b]] end')
            elif op == "or":
                parts.append(f'if c=={code} then {R}[{RK}[d]]={R}[{RK}[a]] or {R}[{RK}[b]] end')
            else:
                parts.append(f'if c=={code} then {R}[{RK}[d]]={R}[{RK}[a]]{op}{R}[{RK}[b]] end')
        return " ".join(parts)

    def _gen_unop_dispatch(self, reg_var, rk_var) -> str:
        # P2-2 寄存器虚拟化：R[d] → R[RK[d]]
        R = reg_var
        RK = rk_var
        code_to_op = {c: op for op, c in self.uncode.items()}
        parts = []
        for code in range(len(_PRO_UNOPS)):
            op = code_to_op[code]
            if op == "-":
                parts.append(f'if c=={code} then {R}[{RK}[d]]=-{R}[{RK}[a]] end')
            elif op == "not":
                parts.append(f'if c=={code} then {R}[{RK}[d]]=not {R}[{RK}[a]] end')
            elif op == "#":
                parts.append(f'if c=={code} then {R}[{RK}[d]]=#{R}[{RK}[a]] end')
        return " ".join(parts)

    def _gen_handler_chain(self, op_var, reg_var, consts_var, strs_var,
                           pc_var, inst_var, bin_dispatch, un_dispatch,
                           run_var, rets_var, va_var, uv_var, jt_var, rk_var,
                           secure_opnames):
        # P2-3 解释器分片嵌套：主 dispatcher + 安全 dispatcher 双链
        # 敏感 opcode（CALL/CLOSURE/RET/全局访问等）路由到 secure dispatcher，
        # 其余走 main dispatcher。两条链各自独立随机化 handler 顺序，
        # 分析者必须先理解分类机制，再分别分析两条链。
        def _build_chain(op_names):
            order = list(op_names)
            self.rng.shuffle(order)
            handlers = []
            for op_name in order:
                variants = self.opcode_variants[op_name]
                h = self._gen_handler(op_name, reg_var, consts_var,
                                      strs_var, pc_var, inst_var, bin_dispatch, un_dispatch,
                                      run_var, rets_var, va_var, uv_var, jt_var, rk_var)
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

        main_names = [op for op in self.opcode.keys() if op not in secure_opnames]
        main_chain = _build_chain(main_names)
        secure_chain = _build_chain(secure_opnames)
        # 收集 secure opcode 的所有变体码（运行期 op 可能是任一变体码）
        secure_codes = set()
        for op_name in secure_opnames:
            if op_name in self.opcode_variants:
                for v in self.opcode_variants[op_name]:
                    secure_codes.add(v)
        return main_chain, secure_chain, secure_codes

    def _gen_handler(self, op_name, R, C, S, pc_var, I, bin_d, un_d,
                     RUN, RETS, VA, UV, JT, RK) -> str:
        # P2-2 寄存器虚拟化：所有寄存器访问 R[name] → R[RK[name]]
        # RK 是运行期映射表：寄存器名(字符串) → 随机物理键(整数)
        # 非寄存器字段（常量索引/字符串索引/跳转索引/计数器）保持不变
        # 假 opcode（JUNK1-8）：dispatcher 里有 handler，看起来像真实逻辑
        if op_name.startswith("JUNK"):
            junk_kind = int(op_name[4:])
            if junk_kind == 1:
                return f'local _j={R}[{RK}[{I}[2]]]+{R}[{RK}[{I}[3]]]'
            elif junk_kind == 2:
                return f'local _j={R}[{RK}[{I}[2]]][{I}[3]]'
            elif junk_kind == 3:
                return f'if {R}[{RK}[{I}[2]]] then local _j=1 end'
            elif junk_kind == 4:
                return f'local _j=tostring({R}[{RK}[{I}[2]]])..tostring({R}[{RK}[{I}[3]]])'
            elif junk_kind == 5:
                return f'local _j=#{{}} for _k=1,3 do _j=_j+1 end'
            elif junk_kind == 6:
                return f'local _j=_G[{I}[2]]'
            elif junk_kind == 7:
                return f'local _j=math.floor({R}[{RK}[{I}[2]]])'
            else:
                return f'local _j=function() end'
        if op_name == "LOADK":
            return f'{R}[{RK}[{I}[2]]]={C}[{I}[3]+1]'
        elif op_name == "LOADSTR":
            return f'{R}[{RK}[{I}[2]]]=_dec_str({S}[{I}[3]+1])'
        elif op_name == "LOADBOOL":
            return f'{R}[{RK}[{I}[2]]]=({I}[3]~=0)'
        elif op_name == "LOADNIL":
            return f'{R}[{RK}[{I}[2]]]=nil'
        elif op_name == "MOVR":
            return f'{R}[{RK}[{I}[2]]]={R}[{RK}[{I}[3]]]'
        elif op_name == "BINOP":
            return f'local d,a,b,c={I}[2],{I}[3],{I}[4],{I}[5] {bin_d}'
        elif op_name == "UNOP":
            return f'local d,a,c={I}[2],{I}[3],{I}[4] {un_d}'
        elif op_name == "JMP":
            return f'{pc_var}={JT}[{I}[2]] _jmp=true'
        elif op_name == "CJMP":
            return f'if {R}[{RK}[{I}[2]]] then {pc_var}={JT}[{I}[3]] _jmp=true end'
        elif op_name == "NJMP":
            return f'if not {R}[{RK}[{I}[2]]] then {pc_var}={JT}[{I}[3]] _jmp=true end'
        elif op_name == "CALL":
            # I[4] = 固定参数数；用 table.unpack(_args, 1, I[4]) 显式指定长度，
            # 避免 nil 参数导致 #_args 错误（unpack 默认用 #t 会停在 nil 处）
            return (f'local _fn={R}[{RK}[{I}[3]]] local _args={{}} '
                    f'for _ai=1,{I}[4] do _args[_ai]={R}[{RK}[{I}[4+_ai]]] end '
                    f'{RETS}=table.pack(_fn(table.unpack(_args,1,{I}[4]))) '
                    f'{R}[{RK}[{I}[2]]]={RETS}[1]')
        elif op_name == "CALLV":
            # I[5] = 固定参数数（不含 self）；同样显式指定 unpack 长度
            return (f'local _obj={R}[{RK}[{I}[3]]] local _m=_dec_str({S}[{I}[4]+1]) '
                    f'local _args={{}} '
                    f'for _ai=1,{I}[5] do _args[_ai]={R}[{RK}[{I}[5+_ai]]] end '
                    f'local _fn=_obj[_m] '
                    f'{RETS}=table.pack(_fn(_obj,table.unpack(_args,1,{I}[5]))) '
                    f'{R}[{RK}[{I}[2]]]={RETS}[1]')
        elif op_name == "RET":
            # I[3] = 返回值数；用 table.unpack(_rv, 1, I[3]) 显式指定长度，
            # 避免 nil 返回值导致 #_rv 错误（return nil, 42 会停在 nil 处）
            return (f'if {I}[3] and {I}[3]>0 then '
                    f'local _rv={{}} for _ri=1,{I}[3] do _rv[_ri]={R}[{RK}[{I}[3+_ri]]] end '
                    f'return table.unpack(_rv,1,{I}[3]) end '
                    f'return')
        elif op_name == "RETVA":
            # return ... 或 return a, b, ...
            # I[2] = 固定返回值数（不含 ...）；va_var.n 是 varargs 数量
            # 无固定值（I[2]==0）时直接 return table.unpack(va, 1, va.n)
            # 有固定值时把固定值放前面，vararg 展开放后面
            return (f'if {I}[2] and {I}[2]>0 then '
                    f'local _rv={{}} for _ri=1,{I}[2] do _rv[_ri]={R}[{RK}[{I}[2+_ri]]] end '
                    f'for _vi=1,{VA}.n do _rv[{I}[2]+_vi]={VA}[_vi] end '
                    f'return table.unpack(_rv,1,{I}[2]+{VA}.n) end '
                    f'return table.unpack({VA},1,{VA}.n)')
        elif op_name == "CLOSURE":
            return (f'local _uvc={{}} '
                    f'for _k,_v in pairs({UV}) do _uvc[_k]=_v end '
                    f'for _k,_v in pairs({R}[{RK}[{I}[4]]]) do _uvc[_k]=_v end '
                    f'{R}[{RK}[{I}[2]]]=function(...) return {RUN}({I}[3],_uvc,...) end')
        elif op_name == "PARAMS":
            # va_var 是 table.pack(...) 结果，用 .n 字段保留 nil 参数
            # 直接按索引读取（包括 nil 值）
            return f'for _pi=1,{I}[2] do {R}[{RK}[{I}[2+_pi]]]={VA}[_pi] end'
        elif op_name == "GETRET":
            return f'{R}[{RK}[{I}[2]]]={RETS}[{I}[3]]'
        elif op_name == "NEWTAB":
            return f'{R}[{RK}[{I}[2]]]={{}}'
        elif op_name == "GETTAB":
            return f'{R}[{RK}[{I}[2]]]={R}[{RK}[{I}[3]]][{R}[{RK}[{I}[4]]]]'
        elif op_name == "SETTAB":
            return f'{R}[{RK}[{I}[2]]][{R}[{RK}[{I}[3]]]]={R}[{RK}[{I}[4]]]'
        elif op_name == "GETTABK":
            return f'{R}[{RK}[{I}[2]]]={R}[{RK}[{I}[3]]][_dec_str({S}[{I}[4]+1])]'
        elif op_name == "SETTABK":
            return f'{R}[{RK}[{I}[2]]][_dec_str({S}[{I}[3]+1])]={R}[{RK}[{I}[4]]]'
        elif op_name == "GETGLOB":
            return f'{R}[{RK}[{I}[2]]]=_G[_dec_str({S}[{I}[3]+1])]'
        elif op_name == "SETGLOB":
            return f'_G[_dec_str({S}[{I}[2]+1])]={R}[{RK}[{I}[3]]]'
        elif op_name == "GETUV":
            # box 读：_uv[name] 是单元素 box（{value}），CLOSURE 浅拷贝共享 box 引用
            # box 不存在（读取早于声明/前向引用）→ nil
            return (f'local _b={UV}[_dec_str({S}[{I}[3]+1])] '
                    f'{R}[{RK}[{I}[2]]]=_b and _b[1]')
        elif op_name == "SETUV":
            # box 写：写入既有 box（与外层/兄弟闭包共享该 upvalue）
            # box 不存在（对未声明捕获名的纯赋值）→ 防御性建 box，避免报错
            return (f'local _b={UV}[_dec_str({S}[{I}[2]+1])] '
                    f'if _b then _b[1]={R}[{RK}[{I}[3]]] '
                    f'else {UV}[_dec_str({S}[{I}[2]+1])]={{}} '
                    f'{UV}[_dec_str({S}[{I}[2]+1])][1]={R}[{RK}[{I}[3]]] end')
        elif op_name == "DECLUV":
            # box 声明：新建 box 替换旧引用（局部变量语义——每次函数调用/循环迭代独立）
            return f'{UV}[_dec_str({S}[{I}[2]+1])]={{}} {UV}[_dec_str({S}[{I}[2]+1])][1]={R}[{RK}[{I}[3]]]'
        elif op_name == "FORPREP":
            return (f'{R}[{RK}[{I}[2]]]={R}[{RK}[{I}[3]]] '
                    f'if ({R}[{RK}[{I}[5]]]>0 and {R}[{RK}[{I}[3]]]>{R}[{RK}[{I}[4]]] ) '
                    f'or ({R}[{RK}[{I}[5]]]<0 and {R}[{RK}[{I}[3]]]<{R}[{RK}[{I}[4]]] ) '
                    f'then {pc_var}={JT}[{I}[6]] _jmp=true end')
        elif op_name == "FORLOOP":
            return (f'{R}[{RK}[{I}[2]]]={R}[{RK}[{I}[2]]]+{R}[{RK}[{I}[4]]] '
                    f'if ({R}[{RK}[{I}[4]]]>0 and {R}[{RK}[{I}[2]]]<={R}[{RK}[{I}[3]]] ) '
                    f'or ({R}[{RK}[{I}[4]]]<0 and {R}[{RK}[{I}[2]]]>={R}[{RK}[{I}[3]]] ) '
                    f'then {pc_var}={JT}[{I}[5]] _jmp=true end')
        elif op_name == "BREAK":
            return f'{pc_var}={JT}[{I}[2]]'
        elif op_name == "LOADVA":
            # 加载 vararg 的第一个值（用于 local x = ... 或 (...) 表达式）
            # 注意：local t = {...} 由 _compile_table 单独处理（NEWTAB + APPENDVA），
            # 不会走到这里。这里只处理「单值上下文」的 ... 表达式。
            # va_var 是 table.pack(...) 结果，va_var[1] 是第一个参数（可为 nil）
            return f'{R}[{RK}[{I}[2]]]={VA}[1]'
        elif op_name == "APPENDVA":
            # 将 va_var 全部追加到目标表，从指定索引开始（{a, b, ...}）
            # 用 va_var.n 显式指定长度，避免 nil 截断
            return (f'for _vi=1,{VA}.n do '
                    f'{R}[{RK}[{I}[2]]][{I}[3]+_vi-1]={VA}[_vi] end')
        elif op_name == "CALLVA":
            # 带尾部 vararg 展开的调用：f(a, b, ...)
            # I[2]=dest, I[3]=func, I[4]=fixed_arg_count, I[5..]=固定参数 reg
            # 用 va_var.n 显式指定长度，避免 nil 截断
            return (f'local _fn={R}[{RK}[{I}[3]]] local _args={{}} '
                    f'for _ai=1,{I}[4] do _args[_ai]={R}[{RK}[{I}[4+_ai]]] end '
                    f'for _vi=1,{VA}.n do _args[{I}[4]+_vi]={VA}[_vi] end '
                    f'local _na={I}[4]+{VA}.n '
                    f'{RETS}=table.pack(_fn(table.unpack(_args,1,_na))) '
                    f'{R}[{RK}[{I}[2]]]={RETS}[1]')
        elif op_name == "CALLMR":
            # 带尾部多返回值展开的调用：f(a, b, g()) — g() 的所有返回值作为尾部参数
            # I[2]=dest, I[3]=func, I[4]=fixed_arg_count, I[5..]=固定参数 reg
            # 尾部参数来自上一个 CALL 填充的 _rets 表（table.pack 结果，含 .n）
            # 先保存 _mr=_rets（因为本次 CALL 会覆盖 _rets），再拼接固定参数 + 多返回值
            return (f'local _fn={R}[{RK}[{I}[3]]] local _args={{}} '
                    f'for _ai=1,{I}[4] do _args[_ai]={R}[{RK}[{I}[4+_ai]]] end '
                    f'local _mr={RETS} '
                    f'local _mn=_mr.n or 0 '
                    f'for _mi=1,_mn do _args[{I}[4]+_mi]=_mr[_mi] end '
                    f'local _na={I}[4]+_mn '
                    f'{RETS}=table.pack(_fn(table.unpack(_args,1,_na))) '
                    f'{R}[{RK}[{I}[2]]]={RETS}[1]')
        elif op_name == "TABMR":
            # 表构造器追加多返回值：{a, b, g()} — g() 的所有返回值追加到表末尾
            # I[2]=dest_tab, I[3]=start_idx（追加起始索引，1-based）
            # 尾部元素来自上一个 CALL 填充的 _rets 表
            return (f'local _mr={RETS} '
                    f'local _mn=_mr.n or 0 '
                    f'for _mi=1,_mn do {R}[{RK}[{I}[2]]][{I}[3]+_mi-1]=_mr[_mi] end')
        elif op_name == "RETMR":
            # return a, b, g() — 固定返回值 + g() 的所有返回值作为尾部
            # I[2] = 固定返回值数（不含多返回值部分）；尾部来自 _rets（上一个 CALL）
            # 先保存 _mr=_rets，再拼接固定值 + _mr 展开值
            return (f'if {I}[2] and {I}[2]>0 then '
                    f'local _rv={{}} for _ri=1,{I}[2] do _rv[_ri]={R}[{RK}[{I}[2+_ri]]] end '
                    f'local _mr={RETS} '
                    f'local _mn=_mr.n or 0 '
                    f'for _mi=1,_mn do _rv[{I}[2]+_mi]=_mr[_mi] end '
                    f'return table.unpack(_rv,1,{I}[2]+_mn) end '
                    f'local _mr={RETS} '
                    f'return table.unpack(_mr,1,_mr.n or 0)')
        return f'-- unknown {op_name}'


# =============================================================================
# 三、公开 API
# =============================================================================
def vm_pro_compile(chunk, rng: random.Random, gen,
                   enable_nested_vm: bool = True,
                   enable_register_virt: bool = True,
                   enable_anti_hook: bool = True) -> Optional[str]:
    """尝试用付费级字节码 VM 编译整个 chunk。

    成功返回解释器 Lua 源码字符串，失败返回 None（调用方回退）。

    参数：
        enable_nested_vm:     VM嵌套VM（Dual-VM）。默认开启（最强保护）。
                              开启时将内层VM代码加密后包装在外层解密加载器中，
                              增加逆向深度。无论脚本大小均启用，追求最强保护。
        enable_register_virt: 寄存器虚拟化（P2-2）。默认开启。
                              开启时寄存器访问转为间接寻址查表 RK[name]。
        enable_anti_hook:     反Hook检测（P3-2 API完整性校验）。默认开启。
                              关闭时跳过API签名校验。
    """
    compiler = ProVMCompiler(rng, gen)
    compiler._enable_register_virt = enable_register_virt
    compiler._enable_anti_hook = enable_anti_hook
    code = compiler.compile_chunk(chunk)
    if code is None:
        return None
    # VM嵌套VM：将内层VM代码加密包装在外层解密加载器中
    if enable_nested_vm and code:
        code = _wrap_nested_vm(code, rng, gen)
    return code


def _wrap_nested_vm(inner_code: str, rng: random.Random, gen) -> str:
    """VM嵌套VM包装器：将内层VM代码加密后嵌入外层解密加载器。

    对标用户清单第二类第 1 项「VM嵌套VM (Dual-VM)」。

    策略（安全简化版，非真正的双层字节码解释器）：
    - 将内层VM的Lua源码转为字节序列
    - 用滚动XOR密钥加密（每字节位置相关密钥）
    - 外层加载器：解密 → loadstring → 执行
    - 密钥本身通过多步算术运算派生，增加静态分析难度

    安全性：
    - loadstring 不可用时回退到直接执行内层代码（带 inline 回退）
    - 加密只增加一层间接，不改变语义
    - 产物体积约内层代码的 3-4 倍（字节序列膨胀）
    """
    import random as _rng
    # 加密密钥：多步派生
    k1 = rng.randint(1, 0xFF)
    k2 = rng.randint(1, 0xFFFF)
    k3 = rng.randint(1, 0xFFFFFF)
    salt = rng.randint(0x100, 0xFFFF)

    # 将内层代码转为字节序列
    inner_bytes = inner_code.encode('utf-8', errors='replace')
    # 加密：enc[i] = byte[i] ^ ((k1 + i*k2 + (i*i % k3)) & 0xFF) ^ ((i * 0x9E37 + salt) & 0xFF)
    enc = []
    for i, b in enumerate(inner_bytes):
        key_byte = ((k1 + i * k2 + (i * i % k3)) & 0xFF) ^ ((i * 0x9E37 + salt) & 0xFF)
        enc.append(b ^ key_byte)

    # 生成 Lua 字节数组字面量（\ddd 转义）
    payload_str = '"' + ''.join(f'\\{b:03d}' for b in enc) + '"'

    # 变量名
    payload_var = gen.fresh()
    key1_var = gen.fresh()
    key2_var = gen.fresh()
    key3_var = gen.fresh()
    salt_var = gen.fresh()
    dec_var = gen.fresh()
    i_var = gen.fresh()
    byte_var = gen.fresh()
    key_byte_var = gen.fresh()
    load_var = gen.fresh()
    ok_var = gen.fresh()
    fn_var = gen.fresh()

    # 密钥通过MBA表达式派生（增加静态分析难度）
    # k1 = (a + b) - c, 其中 c = a + b - k1
    a1 = rng.randint(1, 9999)
    b1 = rng.randint(1, 9999)
    c1 = a1 + b1 - k1
    # k2 = (a * b) + r
    a2 = rng.randint(2, 97)
    b2 = rng.randint(2, 97)
    r2 = k2 - a2 * b2
    # k3 = (a - b) + c
    a3 = rng.randint(1, 9999)
    b3 = rng.randint(1, 9999)
    c3 = k3 - a3 + b3
    # salt = (a + b) * c - d
    a4 = rng.randint(1, 50)
    b4 = rng.randint(1, 50)
    c4 = rng.randint(1, 20)
    d4 = (a4 + b4) * c4 - salt

    outer = f'''-- [AI-DETECT] VM嵌套VM外层解密加载器（Dual-VM）
local {payload_var} = {payload_str}
local {key1_var} = ({a1} + {b1}) - {c1}
local {key2_var} = ({a2} * {b2}) + {r2}
local {key3_var} = ({a3} - {b3}) + {c3}
local {salt_var} = ({a4} + {b4}) * {c4} - {d4}
local {dec_var} = {{}}
for {i_var} = 1, #{payload_var} do
    local {byte_var} = string.byte({payload_var}, {i_var})
    local {key_byte_var} = (({key1_var} + ({i_var} - 1) * {key2_var} + (({i_var} - 1) * ({i_var} - 1) % {key3_var})) % 256) ~ (((({i_var} - 1) * 0x9E37 + {salt_var}) % 256))
    {dec_var}[{i_var}] = string.char(({byte_var} ~ {key_byte_var}) % 256)
end
local {load_var} = table.concat({dec_var})
local {ok_var}, {fn_var} = pcall(loadstring, {load_var})
if {ok_var} and {fn_var} then
    {fn_var}()
else
    -- 回退：直接执行内层代码（loadstring 不可用时）
    -- 此分支在 loadstring 被禁用的环境中触发
    assert(load({load_var}))()
end
'''
    return outer
