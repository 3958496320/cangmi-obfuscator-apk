# -*- coding: utf-8 -*-
"""
control_flow.py
===============
第 3 层：控制流平坦化（CFF）+ 虚拟机模拟（VM）。

【控制流平坦化】对标 Bill's Lua Obfuscator / ComboSec。
将函数体的顺序语句改写为 `while true + 状态分发器`。关键安全策略：
- 该层在 **renamer 之后** 运行，此时所有局部变量已拥有全局唯一名，
  故「提升局部到函数体顶部」不会捕获任何先前的同名全局引用，语义零改变。
- 仅提升「函数体顶层」的局部（不触碰嵌套块内的 local），嵌套语句原样保留。
- 状态数 ≤ 50，平坦化嵌套深度 = 1（远 ≤ 5）。
- 跳过含顶层 goto/label 的函数体。

【虚拟机模拟】对标 ComboSec。
选取「纯算术、无副作用、无闭包/可变参数/调用」的简单函数，编译为自定义
字节码，由嵌入式微型解释器解释执行。指令编码表每次随机生成。
不满足严格条件的函数保持原样（绝不冒险）。
"""

from __future__ import annotations
import random
from typing import List, Optional, Tuple

from ast_parser import Node, N, parse_source, generate_code
from util import NameGenerator


# ---------------------------------------------------------------------------
# 一、控制流平坦化
# ---------------------------------------------------------------------------

def _body_stmts(func: Node) -> List[Node]:
    """获取函数体的语句列表。"""
    return func.get("body")


def _is_flattenable(stmts: List[Node]) -> bool:
    """判断函数体是否可安全平坦化。"""
    # 至少 4 条顶层语句才有收益
    if len(stmts) < 4:
        return False
    for s in stmts:
        if s.type in ("Goto", "Label"):
            return False
        # 顶层 break/continue 在函数体非法，但防御性跳过
        if s.type in ("Break", "Continue"):
            return False
    return True


def _collect_top_locals(stmts: List[Node]) -> List[str]:
    """收集函数体顶层声明的所有局部名（含 LocalAssign / LocalFunction）。

    运行于 renamer 之后，这些名已是全局唯一，可安全提升。
    """
    names: List[str] = []
    for s in stmts:
        if s.type == "LocalAssign":
            names.extend(s.get("names"))
        elif s.type == "LocalFunction":
            names.append(s.get("name"))
    return names


def _convert_top_locals(stmts: List[Node]) -> List[Node]:
    """将顶层 local 声明转为赋值（保持顺序）。

    - LocalAssign names exprs  ->  Assign(names, exprs)  （若无 exprs 则删除）
    - LocalFunction name func  ->  Assign([name], [func])
    """
    out: List[Node] = []
    for s in stmts:
        if s.type == "LocalAssign":
            if s.get("exprs"):
                out.append(N("Assign", targets=[N("Name", name=n) for n in s.get("names")],
                             exprs=s.get("exprs")))
            # 无初始化的 local 提升后无需保留语句
        elif s.type == "LocalFunction":
            out.append(N("Assign",
                         targets=[N("Name", name=s.get("name"))],
                         exprs=[s.get("func")]))
        else:
            out.append(s)
    return out


def _group_states(stmts: List[Node], rng: random.Random,
                  max_states: int = 50) -> List[List[Node]]:
    """将语句序列分组为若干状态块（每组 1~3 条），且总状态数 ≤ max_states。"""
    n = len(stmts)
    # 估算每组大小，确保状态数不超限
    min_group = max(1, (n + max_states - 1) // max_states)
    groups: List[List[Node]] = []
    i = 0
    while i < n:
        # 在 [min_group, min_group+2] 间随机，但不越界
        hi = min(min_group + 2, n - i)
        size = rng.randint(min_group, hi) if hi >= min_group else hi
        size = max(1, size)
        groups.append(stmts[i:i + size])
        i += size
    # 若仍超过 max_states，强制合并
    while len(groups) > max_states:
        last = groups.pop()
        groups[-1].extend(last)
    return groups


def flatten_function_body(func: Node, rng: random.Random,
                          gen: NameGenerator) -> bool:
    """对一个 Function 节点的函数体执行控制流平坦化。

    返回是否实际进行了平坦化。
    """
    stmts = _body_stmts(func)
    if not _is_flattenable(stmts):
        return False

    top_locals = _collect_top_locals(stmts)
    converted = _convert_top_locals(stmts)
    groups = _group_states(converted, rng, max_states=50)
    if len(groups) < 2:
        return False

    # 分配随机状态号（1..N）+ EXIT 哨兵（0）
    state_ids = list(range(1, len(groups) + 1))
    rng.shuffle(state_ids)
    # 保证唯一
    state_ids = state_ids[:len(groups)]
    exit_id = 0

    state_var = gen.fresh()
    # 入口状态 = 第一个分组对应的状态号
    entry = state_ids[0]

    # 构建 elseif 链：if state == id0 then <group0>; state = next elseif ...
    # 最后一组执行后 state = exit
    # 未知 state -> break（安全退出）
    # 注意：Lua 中 return 必须是块的最后一条语句；若某组含顶层 Return，
    # 则截断到该 return 并跳过 state 转移赋值（return 已退出函数，转移不可达）。
    branches: List[Tuple[Node, List[Node]]] = []
    for idx, grp in enumerate(groups):
        sid = state_ids[idx]
        nxt = state_ids[idx + 1] if idx + 1 < len(groups) else exit_id
        body: List[Node] = []
        has_return = False
        for s in grp:
            body.append(s)
            if s.type == "Return":
                has_return = True
                break  # return 之后语句不可达且非法，截断
        if not has_return:
            body.append(N("Assign",
                          targets=[N("Name", name=state_var)],
                          exprs=[N("Number", value=str(nxt))]))
        cond = N("BinOp", op="==",
                 left=N("Name", name=state_var),
                 right=N("Number", value=str(sid)))
        branches.append((cond, body))

    # 第一个分支用 if，其余 elseif，最后 else break
    first_cond, first_body = branches[0]
    elifs = branches[1:]
    else_body = [N("Break")]
    dispatcher = N("While",
                   cond=N("BinOp", op="~=",
                          left=N("Name", name=state_var),
                          right=N("Number", value=str(exit_id))),
                   body=[N("If", cond=first_cond, body=first_body,
                           elifs=elifs, else_body=else_body)])

    # 提升局部声明（无初始化）
    new_body: List[Node] = []
    if top_locals:
        new_body.append(N("LocalAssign", names=top_locals, exprs=[]))
    new_body.append(N("LocalAssign", names=[state_var],
                      exprs=[N("Number", value=str(entry))]))
    new_body.append(dispatcher)
    # 末尾显式 return（与原语义一致：平坦化后 fallthrough 返回 nil）
    new_body.append(N("Return", exprs=[]))

    func.attrs["body"] = new_body
    return True


# ---------------------------------------------------------------------------
# 二、虚拟机模拟（VM）
# ---------------------------------------------------------------------------

# 支持的二元运算符（仅算术，保证纯函数可编译）
_VM_BINOPS = {"+", "-", "*", "/", "%", "^"}


class _VMCompiler:
    """将「纯算术函数」编译为自定义字节码 + 解释器。"""

    def __init__(self, rng: random.Random, gen: NameGenerator):
        self.rng = rng
        self.gen = gen
        # 指令操作码表（每次随机生成）
        ops = ["LOADK", "MOVR", "BINOP", "RET"]
        rng.shuffle(ops)
        self.opcode = {name: i for i, name in enumerate(ops)}
        # 运算符编码表（每次随机生成）
        bin_list = list(_VM_BINOPS)
        rng.shuffle(bin_list)
        self.bincode = {op: i for i, op in enumerate(bin_list)}
        self.prog: List[List] = []      # 指令列表
        self.consts: List[float] = []   # 常量池
        self._reg: dict = {}            # var name -> 寄存器键（字符串）
        self._next_reg = 0

    def _reg_of(self, name: str) -> str:
        if name not in self._reg:
            self._reg[name] = self.gen.fresh()
        return self._reg[name]

    def _new_reg(self) -> str:
        r = self.gen.fresh()
        self._reg[("__tmp__", self._next_reg)] = r
        self._next_reg += 1
        return r

    def _const_index(self, val: float) -> int:
        self.consts.append(val)
        return len(self.consts) - 1

    def _compile_expr(self, expr: Node) -> str:
        """编译表达式，返回存放结果的寄存器键。"""
        t = expr.type
        if t == "Number":
            try:
                val = float(expr.get("value"))
            except ValueError:
                val = 0.0
            dst = self._new_reg()
            self.prog.append([self.opcode["LOADK"], dst, ("K", self._const_index(val))])
            return dst
        if t == "Name":
            return self._reg_of(expr.get("name"))
        if t == "BinOp" and expr.get("op") in _VM_BINOPS:
            a = self._compile_expr(expr.get("left"))
            b = self._compile_expr(expr.get("right"))
            dst = self._new_reg()
            self.prog.append([self.opcode["BINOP"], dst, a, b, self.bincode[expr.get("op")]])
            return dst
        if t == "UnaryOp" and expr.get("op") == "-":
            # -x 编译为 0 - x
            inner = self._compile_expr(expr.get("operand"))
            zero_dst = self._new_reg()
            self.prog.append([self.opcode["LOADK"], zero_dst, ("K", self._const_index(0.0))])
            dst = self._new_reg()
            self.prog.append([self.opcode["BINOP"], dst, zero_dst, inner, self.bincode["-"]])
            return dst
        if t == "Paren":
            return self._compile_expr(expr.get("expr"))
        raise _NotVMable("表达式不可编译")

    def compile(self, func: Node) -> Optional[str]:
        """尝试编译函数。返回等价的 Luau 源码字符串；不可编译返回 None。"""
        if func.get("is_vararg"):
            return None
        params = func.get("params")
        body = func.get("body")
        # 仅允许 LocalAssign + 末尾 Return
        ret_idx = None
        for i, s in enumerate(body):
            if s.type == "LocalAssign":
                if len(s.get("names")) != 1:
                    return None
                if len(s.get("exprs")) != 1:
                    return None
            elif s.type == "Return":
                if ret_idx is not None or i != len(body) - 1:
                    return None
                ret_idx = i
            else:
                return None
        if ret_idx is None:
            return None
        ret_exprs = body[ret_idx].get("exprs")
        if len(ret_exprs) != 1:
            return None

        # 关键正确性检查：拒绝引用 upvalue（自由变量）的函数。
        # VM 编译只把参数和函数体内 LocalAssign 声明的名字装入寄存器；
        # 任何引用外部闭包变量（upvalue）的 Name 都不会有对应寄存器初值，
        # 解释器会返回 nil，导致结果错误。闭包 `function() return count end`
        # （count 为外层 local）就是典型反例。
        # 通过预收集「本函数可见的局部名集合」并校验所有 Name 引用属于该集合
        # 来排除此类函数。全局库（math/string 等）不会出现在纯算术表达式中
        # （Call/Index 已被 _compile_expr 拒绝），故无需特别处理。
        visible_names: set = set(params)
        for s in body[:ret_idx]:
            visible_names.update(s.get("names"))

        def _check_names(expr: Node):
            t = expr.type
            if t == "Name":
                if expr.get("name") not in visible_names:
                    raise _NotVMable("引用 upvalue/全局名")
            elif t == "BinOp":
                _check_names(expr.get("left"))
                _check_names(expr.get("right"))
            elif t == "UnaryOp":
                _check_names(expr.get("operand"))
            elif t == "Paren":
                _check_names(expr.get("expr"))
            # Number / 其它类型不引用名字

        try:
            # 预校验：所有表达式中的 Name 必须可见
            for s in body[:ret_idx]:
                _check_names(s.get("exprs")[0])
            _check_names(ret_exprs[0])

            # 参数寄存器
            for p in params:
                self._reg_of(p)
            # 编译每条 local x = expr
            for s in body[:ret_idx]:
                nm = s.get("names")[0]
                dst = self._reg_of(nm)
                src = self._compile_expr(s.get("exprs")[0])
                self.prog.append([self.opcode["MOVR"], dst, src])
            ret_reg = self._compile_expr(ret_exprs[0])
            self.prog.append([self.opcode["RET"], ret_reg])
        except _NotVMable:
            return None

        return self._emit_source(params)

    def _emit_source(self, params: List[str]) -> str:
        """生成解释器 Luau 源码（含动态操作码映射 + JumpTable 跳转表）。

        【动态操作码映射】
        字节码里存「编译期随机物理码」（self.opcode 生成的随机数），
        解释器启动时用运行时 seed（tick() + 内嵌盐）派生一张置换表
        MAP[物理]→逻辑，再查 JumpTable[逻辑]=handler 分发。
        关键：物理码在字节码里是固定的随机数，但 MAP 每次启动都不同
        （因 tick 变化），逆向者 dump 一次源码拿到物理码后，仍需运行时
        dump MAP 才能知道物理码对应的真实操作；且下次启动 MAP 变了，
        上次的映射失效，无法制作通用反混淆器。

        【JumpTable 跳转表】
        把 if/elseif 链改为函数表 T[逻辑码](ins) 分发。逆向者无法在
        固定行下断点（执行流在函数指针间跳转）。不引入自我篡改
        （那会导致脚本自毁），仅靠动态映射+函数表即可扰乱断点。
        """
        # 常量池表（整数常量输出为整数形式，避免 14.0 之类的浮点显示）
        def fmt_const(c):
            if isinstance(c, float) and c.is_integer():
                return str(int(c))
            return repr(c)
        consts_lua = "{" + ", ".join(fmt_const(c) for c in self.consts) + "}"

        # 程序表：每条指令存「编译期随机物理码」+ 操作数。
        # 物理码 = self.opcode[name]（编译期随机），固定写入字节码。
        # 运行时 MAP[物理]=逻辑 把物理码翻译成 0/1/2/3 再查 JumpTable。
        # 逆向者 dump 源码看到物理码（如 2,0,3,1），但不知哪个是 LOADK；
        # 必须运行时 dump MAP，而 MAP 每次 tick 变化都不同。
        prog_lines = []
        for ins in self.prog:
            parts = []
            for idx, p in enumerate(ins):
                if isinstance(p, tuple) and p and p[0] == "K":
                    parts.append(f'{{"K",{p[1]}}}')
                elif isinstance(p, str):
                    parts.append(f'"{p}"')
                elif isinstance(p, (int, float)):
                    parts.append(str(p))
                else:
                    parts.append('""')
            prog_lines.append("{" + ",".join(parts) + "}")
        prog_lua = "{" + ",".join(prog_lines) + "}"

        # 参数寄存器映射：params -> reg keys
        param_regs = [self._reg_of(p) for p in params]
        param_str = ", ".join(params) if params else ""

        # binop 分发（按编码顺序生成）—— 编码仍用编译期随机表
        # d/a/b/c 是 h_binop 内的局部；R 是寄存器表的引用（实际为 r_var）
        # 但此处生成时尚不知 r_var 名，故用占位符 __R__ 后替换
        code_to_op = {c: op for op, c in self.bincode.items()}
        op_dispatch = []
        for code in range(len(_VM_BINOPS)):
            op = code_to_op[code]
            op_dispatch.append(f'if c=={code} then __R__[d]=__R__[a]{op}__R__[b] end')
        op_disp_str = " ".join(op_dispatch)

        # 运行时盐：每次混淆生成不同的盐值，增强 seed 不可预测性
        salt = self.rng.randint(1, 0x7FFFFFFF)
        # 编译期物理码（写入运行时 MAP 初始化，建立 物理->逻辑 映射）
        P_LOADK = self.opcode["LOADK"]
        P_MOVR = self.opcode["MOVR"]
        P_BINOP = self.opcode["BINOP"]
        P_RET = self.opcode["RET"]
        # 解释器函数名 + 内部变量名（避免与用户变量冲突）
        fn_name = self.gen.fresh()
        map_var = self.gen.fresh()
        seed_var = self.gen.fresh()
        jt_var = self.gen.fresh()
        i_var = self.gen.fresh()
        ins_var = self.gen.fresh()
        op_var = self.gen.fresh()
        r_var = self.gen.fresh()
        d_var = self.gen.fresh()
        a_var = self.gen.fresh()
        b_var = self.gen.fresh()
        c_var = self.gen.fresh()
        k_var = self.gen.fresh()

        # JumpTable 的四个处理函数名
        h_loadk = self.gen.fresh()
        h_movr = self.gen.fresh()
        h_binop = self.gen.fresh()
        h_ret = self.gen.fresh()

        src = f'''
local function {fn_name}({param_str})
    local {r_var} = {{}}
    local _C = {consts_lua}
'''
        # 参数装入寄存器
        for p, rk in zip(params, param_regs):
            src += f'    {r_var}["{rk}"] = {p}\n'
        # 动态操作码映射：运行时用 tick()+盐 派生置换表
        # 设计要点：
        #   - 字节码存「编译期物理码」P = [P_LOADK, P_MOVR, P_BINOP, P_RET]（固定）
        #   - 运行时生成随机置换 perm（4 元素排列，每次启动不同）
        #   - MAP[P[i]] = perm[i]  （物理码 → 本次启动的逻辑码）
        #   - JumpTable[perm[i]] = handler[i]  （逻辑码 → 对应 handler）
        #   - handler[i] 按 [LOADK, MOVR, BINOP, RET] 固定顺序定义
        #   - 执行时：logical = MAP[ins[1]]；JumpTable[logical](ins)
        # 因 perm 每次启动随机，MAP 和 JumpTable 填充都随之变化，
        # 逆向者 dump 一次源码拿到物理码后，仍需运行时 dump MAP 才能知道
        # 物理码对应的真实操作；下次启动 perm 变化，映射失效。
        src += f'''    local {seed_var} = (math.floor((tick() or 0) * 1000) ~ {salt}) % 2147483647
    math.randomseed({seed_var})
    local _phys = {{{P_LOADK}, {P_MOVR}, {P_BINOP}, {P_RET}}}
    local _perm = {{0, 1, 2, 3}}
    for _j = #_perm, 2, -1 do
        local _q = math.random(1, _j)
        _perm[_j], _perm[_q] = _perm[_q], _perm[_j]
    end
    local {map_var} = {{}}
    {map_var}[_phys[1]] = _perm[1]
    {map_var}[_phys[2]] = _perm[2]
    {map_var}[_phys[3]] = _perm[3]
    {map_var}[_phys[4]] = _perm[4]
    local {jt_var} = {{}}
    local function {h_loadk}(_ins)
        local {k_var} = _ins[3]; {r_var}[_ins[2]] = _C[{k_var}[2] + 1]
    end
    local function {h_movr}(_ins)
        {r_var}[_ins[2]] = {r_var}[_ins[3]]
    end
    local function {h_binop}(_ins)
        local d, a, b, c = _ins[2], _ins[3], _ins[4], _ins[5]
        {op_disp_str.replace("__R__", r_var)}
    end
    local function {h_ret}(_ins)
        return {r_var}[_ins[2]]
    end
    -- JumpTable[逻辑码] = 处理函数。逻辑码 = _perm[i]，handler 按
    -- [LOADK,MOVR,BINOP,RET] 顺序对应 _phys 顺序，故填 _perm[i] 槽位。
    {jt_var}[_perm[1]] = {h_loadk}
    {jt_var}[_perm[2]] = {h_movr}
    {jt_var}[_perm[3]] = {h_binop}
    {jt_var}[_perm[4]] = {h_ret}
    local _P = {prog_lua}
    for {i_var} = 1, #_P do
        local {ins_var} = _P[{i_var}]
        local {op_var} = {map_var}[{ins_var}[1]]
        if {op_var} ~= nil then
            local _h = {jt_var}[{op_var}]
            if _h then
                local _r = _h({ins_var})
                if _r ~= nil then return _r end
            end
        end
    end
end
'''
        # 注意：上面生成了一个 local function <name>(...) ... end
        # 调用方需替换原函数为该函数引用
        return src


class _NotVMable(Exception):
    pass


def vm_compile_function(func: Node, rng: random.Random,
                        gen: NameGenerator) -> Optional[Node]:
    """尝试将函数编译为 VM 字节码 + 解释器。

    成功则返回一个新的 Function 节点（解释器主体），失败返回 None。
    为保持简单与安全：返回的 Function 主体是「内联解释器循环」，
    参数与原函数一致，返回值与原函数一致。
    """
    compiler = _VMCompiler(rng, gen)
    src = compiler.compile(func)
    if src is None:
        return None
    # 解析生成的源码，取其 local function 的 Function 节点
    try:
        wrapper = parse_source(src)
    except Exception:
        return None
    body = wrapper.get("body")
    if not body or body[0].type != "LocalFunction":
        return None
    new_func = body[0].get("func")
    # 保留原参数信息
    new_func.attrs["params"] = list(func.get("params"))
    new_func.attrs["is_vararg"] = False
    return new_func


# ---------------------------------------------------------------------------
# 三、应用入口
# ---------------------------------------------------------------------------

def apply_control_flow(chunk: Node, rng: random.Random,
                       enable_vm: bool = True) -> dict:
    """遍历 AST，对函数体应用 CFF（及可选 VM）。

    返回统计信息 {cff_count, vm_count}。
    """
    gen = NameGenerator(rng)
    stats = {"cff_count": 0, "vm_count": 0}

    def visit(node: Node):
        if not isinstance(node, Node):
            return
        # 仅在「Function 节点本身」处处理一次（避免 LocalFunction.func 被重复处理）。
        # LocalFunction / FunctionDecl 的 func 子节点会经由下方通用递归到达此处。
        if node.type == "Function" and not node.attrs.get("_no_flatten") \
                and not node.attrs.get("_cff_done"):
            node.attrs["_cff_done"] = True
            handled = False
            if enable_vm:
                vm = vm_compile_function(node, rng, gen)
                if vm is not None:
                    node.attrs["body"] = vm.get("body")
                    node.attrs["params"] = vm.get("params")
                    node.attrs["is_vararg"] = vm.get("is_vararg")
                    node.attrs["_no_flatten"] = True  # VM 产物不再平坦化
                    stats["vm_count"] += 1
                    handled = True
            if not handled:
                if flatten_function_body(node, rng, gen):
                    stats["cff_count"] += 1
        # 递归子节点（含刚被改写的函数体，以处理其中的嵌套函数）
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
