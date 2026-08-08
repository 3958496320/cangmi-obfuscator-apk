# -*- coding: utf-8 -*-
"""
runtime_protection.py
=====================
第 8 层：运行时动态保护。

包含：
- 环境完整性检查：检测 game/workspace/print 等是否被篡改（pcall 包裹）。
- 自修改计数器：全局表计数器，关键点自增，校验是否被跳过。
- 反内存扫描：生成大量无意义局部（包裹在 do-block，不污染 _G）。
- 行为伪装：执行前加入有界无用循环。
- 递归自检：关键函数检查栈深度异常（pcall 包裹）。
- 时间炸弹：可选过期时间戳（--expire）。
- 动态代码生成：通过 loadstring 动态加载一个加密的小工具函数（全工具 ≤1 次
  loadstring），带 inline 回退，保证 loadstring 不可用时仍正确。

所有可能失败的探测均 pcall 包裹；计数器/标志仅用于误导模式，绝不影响真实逻辑。
"""

from __future__ import annotations
import random
from typing import Optional

from ast_parser import Node, N
from util import NameGenerator
from string_encryptor import _encrypt_bytes
from util import bytes_to_lua_literal, name_node, number_node, string_node, call_node

# 苍米独家混淆 - 水印自毁验证目标串（运行时与解密后水印比对，不符即自毁）
_WATERMARK_PLAINTEXT = "苍米独家混淆"


def _pcall(expr: Node) -> Node:
    """把表达式包成 pcall(expr)。"""
    return call_node(name_node("pcall"), [expr])


def _type_is(val_expr: Node, type_str: str) -> Node:
    """type(val) == "type_str" 表达式。"""
    return N("BinOp", op="==",
             left=call_node(name_node("type"), [val_expr]),
             right=string_node(type_str))


def _build_watermark_selfdestruct(gen: NameGenerator, rng: random.Random,
                                  dec_name: str, wm_var: str) -> Node:
    """构造「苍米独家混淆」水印自毁验证块。

    运行时逻辑（等价 Luau）：
        local __exp = <dec_name>(<加密的"苍米独家混淆">, k, o, m)  -- 期望值
        local __got = <wm_var>                                     -- 实际水印（L0 注入，L1 已加密）
        local __ok = (type(__got) == "string") and (#__got == #__exp)
                          and (__got == __exp)
        if not __ok then
            -- 自毁：删除自身文件 + 清空全局环境 + 单次 error 终止
            pcall(function()
                local info = debug and debug.getinfo and debug.getinfo(2, "S")
                local src = info and info.source or ""
                if src:sub(1,1) == "@" then
                    local p = src:sub(2)
                    if os and os.remove then pcall(os.remove, p) end
                    if delfile then pcall(delfile, p) end
                    if writefile then pcall(writefile, p, "") end
                end
            end)
            pcall(function()
                if _G then for k in pairs(_G) do _G[k] = nil end end
            end)
            error("watermark broken")
        end

    防篡改机理：
    1. 删除头部注释 → 内嵌水印仍在，__got 仍等于 __exp，正常运行（不误伤）。
    2. 删除/篡改内嵌水印串 → __got 为 nil 或不等于 __exp → 自毁。
    3. 删除本验证块 → 攻击者需读懂 L1/L2/L3 重命名后的代码，成本极高。
    4. 期望值 __exp 同样经 L1 加密，攻击者无法静态搜索明文绕过。
    """
    # 期望值：用与 L1 相同算法加密 _WATERMARK_PLAINTEXT
    key = rng.randint(1, 255)
    offset = rng.randint(1, 255)
    mask = rng.randint(1, 255)
    enc = _encrypt_bytes(_WATERMARK_PLAINTEXT.encode("utf-8"), key, offset, mask)
    payload_literal = bytes_to_lua_literal(enc)
    payload_node = string_node(payload_literal)
    payload_node.attrs["_verbatim"] = True

    exp_var = gen.fresh()
    got_var = gen.fresh()   # 仅作别名，便于阅读；直接引用 wm_var 亦可
    ok_var = gen.fresh()

    # __exp = <dec_name>(payload, k, o, m)
    exp_assign = N("LocalAssign", names=[exp_var], exprs=[
        call_node(name_node(dec_name),
                  [payload_node, number_node(key), number_node(offset),
                   number_node(mask)])
    ])
    # __got = <wm_var>
    got_assign = N("LocalAssign", names=[got_var], exprs=[name_node(wm_var)])

    # type(__got) == "string"
    cond_type = _type_is(name_node(got_var), "string")
    # #__got == #__exp
    cond_len = N("BinOp", op="==",
                 left=N("UnaryOp", op="#", operand=name_node(got_var)),
                 right=N("UnaryOp", op="#", operand=name_node(exp_var)))
    # __got == __exp
    cond_eq = N("BinOp", op="==",
                left=name_node(got_var), right=name_node(exp_var))
    # ok = cond_type and cond_len and cond_eq
    ok_expr = N("BinOp", op="and",
                left=N("Paren", expr=N("BinOp", op="and",
                                       left=cond_type, right=cond_len)),
                right=N("Paren", expr=cond_eq))
    ok_assign = N("LocalAssign", names=[ok_var], exprs=[ok_expr])

    # 自毁函数体
    # local info = debug and debug.getinfo and debug.getinfo(2, "S")
    info_var = gen.fresh()
    src_var = gen.fresh()
    debug_getinfo = N("BinOp", op="and",
        left=N("BinOp", op="and",
               left=name_node("debug"),
               right=N("Index", obj=name_node("debug"), key=string_node("getinfo"))),
        right=call_node(
            N("Index", obj=name_node("debug"), key=string_node("getinfo")),
            [number_node(2), string_node("S")]))
    info_assign = N("LocalAssign", names=[info_var], exprs=[debug_getinfo])
    # src = info and info.source or ""
    src_assign = N("LocalAssign", names=[src_var], exprs=[
        N("BinOp", op="or",
          left=N("BinOp", op="and",
                 left=name_node(info_var),
                 right=N("Index", obj=name_node(info_var), key=string_node("source"))),
          right=string_node(""))
    ])

    # 删除自身文件分支
    selfdel_body = []
    # if src:sub(1,1) == "@" then
    selfdel_cond = N("BinOp", op="==",
        left=call_node(
            N("Index", obj=name_node(src_var), key=string_node("sub")),
            [number_node(1), number_node(1)]),
        right=string_node("@"))
    p_var = gen.fresh()
    p_assign = N("LocalAssign", names=[p_var], exprs=[
        call_node(
            N("Index", obj=name_node(src_var), key=string_node("sub")),
            [number_node(2)])
    ])
    del_calls = []
    # if os and os.remove then pcall(os.remove, p) end
    del_calls.append(N("If",
        cond=N("BinOp", op="and",
               left=name_node("os"),
               right=N("Index", obj=name_node("os"), key=string_node("remove"))),
        body=[N("CallStatement", expr=call_node(name_node("pcall"),
                [N("Index", obj=name_node("os"), key=string_node("remove")),
                 name_node(p_var)]))],
        elifs=[], else_body=None))
    # if delfile then pcall(delfile, p) end
    del_calls.append(N("If",
        cond=name_node("delfile"),
        body=[N("CallStatement", expr=call_node(name_node("pcall"),
                [name_node("delfile"), name_node(p_var)]))],
        elifs=[], else_body=None))
    # if writefile then pcall(writefile, p, "") end
    del_calls.append(N("If",
        cond=name_node("writefile"),
        body=[N("CallStatement", expr=call_node(name_node("pcall"),
                [name_node("writefile"), name_node(p_var), string_node("")]))],
        elifs=[], else_body=None))
    selfdel_body.append(N("If", cond=selfdel_cond,
                          body=[p_assign] + del_calls,
                          elifs=[], else_body=None))

    # 清空 _G 环境
    clearg_body = [N("If",
        cond=name_node("_G"),
        body=[N("GenericFor", names=["k"],
                exprs=[call_node(name_node("pairs"), [name_node("_G")])],
                body=[N("Assign",
                        targets=[N("Index", obj=name_node("_G"),
                                   key=name_node("k"))],
                        exprs=[N("Nil")])])],
        elifs=[], else_body=None)]

    # 自毁函数：pcall 包裹文件删除 + pcall 包裹清空环境 + 单次 error 终止
    # 注意：用单次 error 而非 while true do error() end（无限循环），
    # 无限循环会让注入器卡死/无响应，单次 error 更安全且同样终止脚本。
    selfdestruct_fn = N("Function", params=[], is_vararg=False, body=[
        info_assign, src_assign,
        N("CallStatement", expr=call_node(name_node("pcall"),
            [N("Paren", expr=N("Function", params=[], is_vararg=False,
                              body=selfdel_body))])),
        N("CallStatement", expr=call_node(name_node("pcall"),
            [N("Paren", expr=N("Function", params=[], is_vararg=False,
                              body=clearg_body))])),
        N("CallStatement", expr=call_node(name_node("error"),
                [string_node("watermark broken")])),
    ])

    # if not __ok then <selfdestruct_fn>() end
    verify = N("If",
        cond=N("UnaryOp", op="not", operand=name_node(ok_var)),
        body=[N("CallStatement", expr=call_node(
            N("Paren", expr=selfdestruct_fn), []))],
        elifs=[], else_body=None)

    return N("Do", body=[exp_assign, got_assign, ok_assign, verify])


def inject_runtime_protection(chunk: Node, rng: random.Random,
                              dec_name: str,
                              expire_ts: Optional[int] = None,
                              enable_loadstring: bool = True,
                              debug: bool = False,
                              wm_var: Optional[str] = None) -> dict:
    """在 Chunk 顶部注入运行时保护代码。

    参数：
        dec_name:          第 1 层字符串解密函数名（用于 loadstring 加密源）。
        expire_ts:         过期时间戳（秒）；None 表示不启用时间炸弹。
        enable_loadstring: 是否启用 loadstring 动态加载（默认 True）。
        debug:             调试模式，注入隐蔽错误日志。
        wm_var:            苍米独家混淆水印变量名（L0 注入）。提供时启用自毁验证。

    返回统计信息。
    """
    gen = NameGenerator(rng)
    stats = {"checks": 0, "loadstring": 0, "noise": 0, "watermark": False}
    body = chunk.get("body")
    prelude: list = []

    # 1) 全局保护标志 + 计数器表
    flag = gen.fresh()
    counter = gen.fresh()
    prelude.append(N("LocalAssign", names=[flag], exprs=[N("False")]))
    prelude.append(N("LocalAssign", names=[counter],
                     exprs=[N("Table", fields=[])]))

    # 2) 环境完整性检查（pcall 包裹）
    def env_check(global_name: str, expected_type: str):
        # local ok, v = pcall(function() return <global_name> end)
        fn = N("Function", params=[], is_vararg=False, body=[
            N("Return", exprs=[name_node(global_name)])
        ])
        chk = [
            N("LocalAssign", names=["ok", "v"], exprs=[_pcall(N("Paren", expr=fn))]),
            N("If",
              cond=N("BinOp", op="and",
                     left=name_node("ok"),
                     right=N("UnaryOp", op="not",
                             operand=_type_is(name_node("v"), expected_type))),
              body=[N("Assign", targets=[name_node(flag)], exprs=[N("True")])],
              elifs=[], else_body=None),
        ]
        return N("Do", body=chk)

    env_block = N("Do", body=[
        env_check("game", "userdata"),
        env_check("workspace", "userdata"),
        env_check("print", "function"),
    ])
    prelude.append(env_block)
    stats["checks"] += 3

    # 3) 自修改计数器：注入若干检查点（自增 + 末尾校验）
    checkpoints = ["c1", "c2", "c3", "c4"]
    cp_names = [gen.fresh() for _ in checkpoints]
    cp_block_body = []
    for cp in cp_names:
        # <counter>[<cp>] = (<counter>[<cp>] or 0) + 1
        cp_block_body.append(N("Assign",
            targets=[N("Index", obj=name_node(counter), key=string_node(cp))],
            exprs=[N("BinOp", op="+",
                     left=N("Paren", expr=N("BinOp", op="or",
                                            left=N("Index", obj=name_node(counter),
                                                   key=string_node(cp)),
                                            right=number_node(0))),
                     right=number_node(1))]))
    prelude.append(N("Do", body=cp_block_body))

    # 4) 反内存扫描：大量无意义局部（do-block 隔离）
    noise_count = rng.randint(8, 16)
    noise_body = []
    for _ in range(noise_count):
        nm = gen.fresh()
        noise_body.append(N("LocalAssign", names=[nm],
                            exprs=[N("Number", value=str(rng.randint(0, 1 << 30)))]))
        noise_body.append(N("Assign", targets=[name_node(nm)],
                            exprs=[N("BinOp", op="~",
                                     left=name_node(nm),
                                     right=number_node(rng.randint(1, 255)))]))
    prelude.append(N("Do", body=noise_body))
    stats["noise"] = noise_count

    # 5) 行为伪装：有界无用循环
    camo_iters = rng.randint(50, 300)
    camo_var = gen.fresh()
    prelude.append(N("Do", body=[
        N("LocalAssign", names=[camo_var], exprs=[number_node(0)]),
        N("NumericFor", var=gen.fresh(), start=number_node(1),
          limit=number_node(camo_iters), step=None,
          body=[N("Assign", targets=[name_node(camo_var)],
                  exprs=[N("BinOp", op="+", left=name_node(camo_var),
                           right=number_node(1))])]),
    ]))

    # 6) 递归自检：栈深度检测（pcall 包裹 debug.getinfo）
    stack_fn = N("Function", params=[], is_vararg=False, body=[
        N("Return", exprs=[N("Call",
            func=N("Index", obj=name_node("debug"), key=string_node("getinfo")),
            args=[number_node(1)])])
    ])
    stack_chk = N("Do", body=[
        N("LocalAssign", names=["sok", "info"], exprs=[_pcall(N("Paren", expr=stack_fn))]),
        N("If",
          cond=N("BinOp", op="and",
                 left=N("BinOp", op="and",
                        left=name_node("sok"),
                        right=name_node("info")),
                 right=N("Index", obj=name_node("info"), key=string_node("what"))),
          body=[  # 仅做计数，不阻断
              N("Assign",
                targets=[N("Index", obj=name_node(counter), key=string_node("stack"))],
                exprs=[number_node(1)])
          ],
          elifs=[], else_body=None),
    ])
    prelude.append(stack_chk)
    stats["checks"] += 1

    # 7) 时间炸弹（可选）
    if expire_ts is not None:
        tb_fn = N("Function", params=[], is_vararg=False, body=[
            N("Return", exprs=[N("Call",
                func=N("Index", obj=name_node("os"), key=string_node("time")),
                args=[])])
        ])
        prelude.append(N("Do", body=[
            N("LocalAssign", names=["tok", "now"], exprs=[
                _pcall(N("Paren", expr=tb_fn))
            ]),
            N("If",
              cond=N("BinOp", op="and",
                     left=name_node("tok"),
                     right=N("BinOp", op=">",
                             left=N("Paren",
                                    expr=N("BinOp", op="or",
                                           left=name_node("now"),
                                           right=number_node(0))),
                             right=number_node(int(expire_ts)))),
              body=[N("Assign", targets=[name_node(flag)], exprs=[N("True")])],
              elifs=[], else_body=None),
        ]))
        stats["checks"] += 1

    # 8) 动态代码生成（loadstring，≤1 次，带 inline 回退）
    if enable_loadstring:
        loader = _build_loadstring_loader(gen, rng, dec_name, debug)
        if loader is not None:
            prelude.append(loader)
            stats["loadstring"] = 1

    # 8.5) 苍米独家混淆 - 水印自毁验证
    #     依赖 dec_name（L1 已注入并会被 L2 重命名统一处理）。
    #     必须在 loadstring 之后，使 dec_name 已定义；在主逻辑之前。
    if wm_var is not None:
        prelude.append(_build_watermark_selfdestruct(gen, rng, dec_name, wm_var))
        stats["watermark"] = True

    # 9) 调试模式：隐蔽错误日志（pcall 包裹 print，绝不抛错）
    #    注意：须用 pcall(print, dbg_var) 形式（把 print 作为函数值传入），
    #    而非 pcall(print(dbg_var))——后者会先调用 print 返回 nil 再 pcall(nil)，
    #    触发 "bad argument #1 to 'pcall' (value expected)"。
    if debug:
        dbg_var = gen.fresh()
        prelude.append(N("LocalAssign", names=[dbg_var],
                         exprs=[N("Call", func=N("Paren", expr=N("Function",
                             params=[], is_vararg=False, body=[
                                 N("Return", exprs=[string_node("[obf] runtime-protection armed")])
                             ])), args=[])]))
        prelude.append(N("Do", body=[
            N("LocalAssign", names=["dok"], exprs=[
                call_node(name_node("pcall"),
                          [name_node("print"), name_node(dbg_var)])
            ]),
        ]))

    # 把 prelude 插到最前
    for i, stmt in enumerate(prelude):
        body.insert(i, stmt)
    return stats


def _build_loadstring_loader(gen: NameGenerator, rng: random.Random,
                            dec_name: str, debug: bool) -> Optional[Node]:
    """构造 loadstring 动态加载器（带 inline 回退）。

    生成等价逻辑：
        local <util>
        local <ok>, <err> = pcall(function()
            local src = <dec_name>(<encrypted "return function(x) return (x ~ K) + 1 end">, ...)
            local fn = loadstring(src)
            if fn then <util> = fn() end
        end)
        if not (<ok> and <util>) then
            <util> = function(x) return (x ~ K) + 1 end   -- inline 回退
        end
        <counter>["util"] = <util>(<seed>)   -- 仅作计数噪声，不影响正确性

    说明：加密源与回退函数等价；loadstring 不可用时回退保证 <util> 可用。
    """
    util_name = gen.fresh()
    key = rng.randint(1, 255)
    offset = rng.randint(1, 255)
    mask = rng.randint(1, 255)
    seed = rng.randint(1, 1 << 24)
    # 动态加载的源码：一个简单的工具函数
    src_code = f"return function(x) return (x ~ {key}) + 1 end"
    data = src_code.encode("utf-8")
    enc = _encrypt_bytes(data, key, offset, mask)
    payload_literal = bytes_to_lua_literal(enc)
    payload_node = string_node(payload_literal)
    payload_node.attrs["_verbatim"] = True

    # src = <dec_name>(payload, key, offset, mask)
    src_assign = N("LocalAssign", names=["src"], exprs=[
        call_node(name_node(dec_name),
                  [payload_node, number_node(key), number_node(offset),
                   number_node(mask)])
    ])
    # local fn = loadstring(src)
    fn_assign = N("LocalAssign", names=["fn"], exprs=[
        call_node(name_node("loadstring"), [name_node("src")])
    ])
    # if fn then <util> = fn() end
    set_util = N("If", cond=name_node("fn"),
                 body=[N("Assign", targets=[name_node(util_name)],
                         exprs=[call_node(name_node("fn"), [])])],
                 elifs=[], else_body=None)

    loader_fn = N("Function", params=[], is_vararg=False, body=[
        src_assign, fn_assign, set_util,
    ])

    # local <ok>, <err> = pcall(<loader_fn>)
    pcall_decl = N("LocalAssign", names=["lok", "ler"], exprs=[
        _pcall(N("Paren", expr=loader_fn))
    ])
    # <util> 预声明
    util_decl = N("LocalAssign", names=[util_name], exprs=[N("Nil")])
    # if not (lok and <util>) then <util> = function(x) return (x ~ key)+1 end end
    fallback = N("If",
        cond=N("UnaryOp", op="not",
               operand=N("Paren", expr=N("BinOp", op="and",
                     left=name_node("lok"),
                     right=name_node(util_name)))),
        body=[N("Assign", targets=[name_node(util_name)],
               exprs=[N("Function", params=["x"], is_vararg=False, body=[
                   N("Return", exprs=[
                       N("BinOp", op="+",
                         left=N("Paren", expr=N("BinOp", op="~",
                                left=name_node("x"),
                                right=number_node(key))),
                         right=number_node(1))
                   ])
               ])])],
        elifs=[], else_body=None)

    # 噪声使用：<counter> 已由调用方在 prelude 中声明——此处用独立 do 块存计数
    noise = N("Do", body=[
        N("LocalAssign", names=["ures"], exprs=[
            call_node(name_node(util_name), [number_node(seed)])
        ]),
    ])

    return N("Do", body=[util_decl, pcall_decl, fallback, noise])
