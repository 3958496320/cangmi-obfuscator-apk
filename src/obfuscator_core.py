# -*- coding: utf-8 -*-
"""
obfuscator_core.py
==================
12 层混淆编排器（Ultimate Ninja Obfuscator 核心）。

按以下顺序编排各层（顺序经严格推导，保证语义等价与全注入器兼容）：

  0. 解析层        parse_source           Luau 源码 -> AST
  12.自适应        select_profile         按行数选档位 + 命令行覆盖
  7. 反自动化(pre) apply_pre_encryption   字符串拆分/API 重定向/AST 扰动
  9. 动态指令      apply_dyninst          _G["<key>"] 运算符函数（须在 L1 前）
  10.块分割        apply_chunk_split      函数体拆分 + 跳转表（须在 CFF 前）
  3. 控制流        apply_control_flow     CFF + VM（处理未被 L10 接管的函数）
  4. 垃圾注入      inject_garbage         死代码
  6. 多态          inject_polymorphism    诱饵状态机
  5. 反调试        apply_anti_debug       debug/getfenv/hookfunction 探测
  11.反启发式      inject_anti_heuristic  时间差/getinfo/pcall 探测
  1. 字符串加密    encrypt_strings        三重加密（最后做，覆盖全部新串）
  8. 运行时保护    inject_runtime_protection  环境检查/loadstring/计数器
  2. 重命名        rename                 作用域感知重命名（最后做，统一映射）
  ∞. 代码生成      generate_code          AST -> Luau 文本

兼容性红线（均满足）：
- 纯文本 Luau 输出，无字节码；
- loadstring ≤1 次（仅 L8）；
- CFF 状态变量 ≤50，嵌套 ≤5；
- 所有可疑调用 pcall 包裹；
- 第 9~12 层均可通过开关单独关闭。
"""

from __future__ import annotations
import random
from typing import Optional, Set, Dict, Any

from ast_parser import parse_source, generate_code, Node
from util import NameGenerator, GLOBAL_LIBS

# 苍米独家混淆 - 版权水印（不可移除）
# 头部块注释 + 内嵌加密版权串，双重防删除/改头换面
_WATERMARK_HEADER = (
    "--[[============================================================\n"
    "  苍米独家混淆 · CangMi Exclusive Obfuscator\n"
    "  12-Layer Ultimate Luau Obfuscator\n"
    "  严禁二次分发 / 改头换面 / 冒充自有作品\n"
    "  Copyright (C) CangMi. All rights reserved.\n"
    "  水印指纹: 0xC4CC-M1-EXCLUSIVE\n"
    "============================================================]]\n"
)
_WATERMARK_STRING = "苍米独家混淆"

# 各层
from string_encryptor import encrypt_strings
from renamer import rename
from control_flow import apply_control_flow
from garbage_injector import inject_garbage
from polymorphism import inject_polymorphism
from anti_deobfuscation import apply_pre_encryption, apply_anti_debug
from runtime_protection import inject_runtime_protection
from dyninst import apply_dyninst
from chunk_split import apply_chunk_split
from anti_heuristic import inject_anti_heuristic
from adaptive_engine import (
    select_profile, apply_overrides, emit_debug_report, make_seed,
)


# 默认保留名集合：Roblox/Luau 全局库 + 注入器常见 API，永不被重命名
_DEFAULT_RESERVE: Set[str] = set(GLOBAL_LIBS)


def obfuscate(src: str,
              seed: Optional[int] = None,
              debug: bool = False,
              reserve_names: Optional[Set[str]] = None,
              expire_ts: Optional[int] = None,
              disable_dyninst: bool = False,
              disable_chunk_split: bool = False,
              disable_anti_heuristic: bool = False,
              disable_adaptive: bool = False,
              force_profile: Optional[str] = None,
              disable_loadstring: bool = False) -> Dict[str, Any]:
    """对 Luau 源码执行 12 层混淆。

    参数：
        src:                    原始 Luau 源码。
        seed:                   随机种子（None = 随机；指定则可复现）。
        debug:                  调试模式（注入隐蔽日志 + stderr 报告）。
        reserve_names:          用户自定义保留名（不被重命名/加密）。
        expire_ts:              时间炸弹过期时间戳（None = 不启用）。
        disable_dyninst:        关闭第 9 层。
        disable_chunk_split:    关闭第 10 层。
        disable_anti_heuristic: 关闭第 11 层。
        disable_adaptive:       关闭第 12 层自适应（强制全开）。
        force_profile:          强制档位 'small'/'medium'/'large'（调试用）。
        disable_loadstring:     关闭第 8 层的 loadstring（仍保留其余保护）。

    返回：{"code": 混淆后源码, "stats": 各层统计, "profile": 档位信息}
    """
    # 0. 随机种子
    if seed is None:
        seed = make_seed()
    rng = random.Random(seed)

    # 12. 自适应档位选择
    profile = select_profile(src)
    profile = apply_overrides(
        profile,
        disable_dyninst=disable_dyninst,
        disable_chunk_split=disable_chunk_split,
        disable_anti_heuristic=disable_anti_heuristic,
        disable_adaptive=disable_adaptive,
        force_profile=force_profile,
    )

    # 保留名集合：默认全局库 + 用户自定义
    reserve: Set[str] = set(_DEFAULT_RESERVE)
    if reserve_names:
        reserve.update(reserve_names)

    stats: Dict[str, Any] = {"seed": seed}

    # 0. 解析
    chunk: Node = parse_source(src)
    stats["lines"] = profile.get("lines")

    # 苍米独家混淆 - 内嵌水印：local <rand> = "苍米独家混淆"
    # 字符串交由 L1 三重加密，变量名交由 L2 重命名，语句可能被 L3/L10 打散
    # 删除头部注释后，加密水印串仍埋伏在代码内部，反编译可见版权归属
    _wm_var = NameGenerator(rng).fresh()
    chunk.attrs["body"].insert(0, Node(
        "LocalAssign",
        names=[_wm_var],
        exprs=[Node("String", value=_WATERMARK_STRING)],
    ))
    stats["L0_watermark"] = {"var": _wm_var, "embedded": True}

    # 7. 反自动化（pre-encryption）：字符串拆分 / API 重定向 / AST 扰动
    #    须在字符串加密之前，产生的新串会被 L1 加密
    stats["L7_pre_encryption"] = apply_pre_encryption(chunk, rng)

    # 9. 动态指令替换（须在 L1 前，_G["<key>"] 字符串交由 L1 加密）
    if profile["dyninst_points"] > 0:
        stats["L9_dyninst"] = apply_dyninst(
            chunk, rng, max_points=profile["dyninst_points"])
    else:
        stats["L9_dyninst"] = {"points": 0, "funcs": 0, "skipped": True}

    # 10. 代码块分割（须在 CFF 前；标记 _cff_done 防止 CFF 再处理）
    if profile["chunk_split_max_order"] > 0:
        stats["L10_chunk_split"] = apply_chunk_split(
            chunk, rng, max_order=profile["chunk_split_max_order"])
    else:
        stats["L10_chunk_split"] = {"split_count": 0, "skipped": True}

    # 3. 控制流平坦化 + VM（处理未被 L10 接管的函数）
    stats["L3_control_flow"] = apply_control_flow(
        chunk, rng, enable_vm=profile["vm_enable"])

    # 4. 垃圾代码注入
    stats["L4_garbage"] = inject_garbage(
        chunk, rng, bloat_ratio=profile["garbage_ratio"])

    # 6. 多态诱饵
    inject_polymorphism(chunk, rng)
    stats["L6_polymorphism"] = "injected"

    # 5. 反调试 / 反篡改
    flag_ad = apply_anti_debug(chunk, rng)
    stats["L5_anti_debug"] = {"flag": flag_ad}

    # 11. 反启发式探测
    if profile["anti_heuristic"]:
        stats["L11_anti_heuristic"] = inject_anti_heuristic(
            chunk, rng, debug=debug)
    else:
        stats["L11_anti_heuristic"] = {"probes": 0, "skipped": True}

    # 1. 字符串三重加密（最后做，覆盖 L7/L9/L10/L3 等产生的新串）
    dec_name = encrypt_strings(
        chunk, rng, reserve_names=reserve)
    stats["L1_string_encryptor"] = {"dec_name": dec_name}

    # 8. 运行时保护（依赖 dec_name）
    #    传入 wm_var 启用苍米独家混淆水印自毁验证
    stats["L8_runtime_protection"] = inject_runtime_protection(
        chunk, rng, dec_name=dec_name,
        expire_ts=expire_ts,
        enable_loadstring=(profile["loadstring_enable"]
                           and not disable_loadstring),
        debug=debug,
        wm_var=_wm_var)

    # 2. 作用域感知重命名（最后做，统一映射所有名称）
    rename_map = rename(chunk, rng, reserve_names=reserve)
    stats["L2_renamer"] = {"renamed": len(rename_map)}

    # ∞. 代码生成
    code = generate_code(chunk)
    # 苍米独家混淆 - 头部版权水印（内嵌加密串已在代码中，双重防删除）
    code = _WATERMARK_HEADER + code
    stats["output_chars"] = len(code)

    # 调试报告
    if debug:
        emit_debug_report(profile, stats)

    return {"code": code, "stats": stats, "profile": profile}
