# -*- coding: utf-8 -*-
"""
adaptive_engine.py
==================
第 12 层：自适应混淆引擎 + 调试模式。

根据输入脚本的行数自动调整混淆强度，同时提供 `--debug` 调试模式。

强度档位（按行数）：
- 小脚本（< 200 行）：全部 11 层全开，强度拉满；
- 中脚本（200~500 行）：第 9、10 层降为「轻度模式」
  （DynInst 操作点 ≤10，Chunk Split 跳转表长度 ≤10）；
- 大脚本（> 500 行）：自动关闭第 9 层，降低第 10 层强度，
  确保 PC/手机端注入器不超时（手机端尤其敏感）。

调试模式（debug=True）：
- 在各层注入隐蔽错误日志（pcall 包裹，绝不抛错）；
- 输出最终混淆统计 JSON 到 stderr（不影响脚本输出）；
- 在产物顶部插入注释标记（可选，默认关闭以避免特征）。

自定义保留列表（reserve_names）：
- 用户通过 --reserve 指定的名称集合，会被透传给 renamer / string_encryptor，
  保证这些名称不被重命名/字符串不被加密。
"""

from __future__ import annotations
import json
import sys
import random
from typing import Optional, Set, Dict, Any

from util import count_lines


# 各档位的参数配置
# 字段含义：
#   dyninst_points:        第 9 层最大操作点数（0 = 关闭）
#   chunk_split_max_order: 第 10 层跳转表最大长度（0 = 关闭）
#   anti_heuristic:        第 11 层是否启用
#   garbage_ratio:         第 4 层垃圾注入比例
#   cff_max_states:        第 3 层 CFF 状态数上限
#   vm_enable:             第 3 层是否启用 VM 编译
#   loadstring_enable:     第 8 层是否启用 loadstring（全工具 ≤1 次）
_PROFILE_SMALL = {
    "name": "small",
    "dyninst_points": 20,
    "chunk_split_max_order": 20,
    "anti_heuristic": True,
    "garbage_ratio": 0.75,
    "cff_max_states": 50,
    "vm_enable": True,
    "loadstring_enable": True,
}

_PROFILE_MEDIUM = {
    "name": "medium",
    "dyninst_points": 10,
    "chunk_split_max_order": 10,
    "anti_heuristic": True,
    "garbage_ratio": 0.5,
    "cff_max_states": 40,
    "vm_enable": True,
    "loadstring_enable": True,
}

_PROFILE_LARGE = {
    "name": "large",
    "dyninst_points": 0,         # 关闭第 9 层
    "chunk_split_max_order": 8,
    "anti_heuristic": True,
    "garbage_ratio": 0.35,
    "cff_max_states": 30,
    "vm_enable": False,          # 大脚本关闭 VM，避免性能损耗
    "loadstring_enable": True,
}


def select_profile(src: str) -> Dict[str, Any]:
    """根据源码行数选择自适应档位。

    返回对应的 _PROFILE_* 字典（拷贝）。
    """
    lines = count_lines(src)
    if lines < 200:
        prof = dict(_PROFILE_SMALL)
    elif lines <= 500:
        prof = dict(_PROFILE_MEDIUM)
    else:
        prof = dict(_PROFILE_LARGE)
    prof["lines"] = lines
    return prof


def apply_overrides(profile: Dict[str, Any],
                    disable_dyninst: bool = False,
                    disable_chunk_split: bool = False,
                    disable_anti_heuristic: bool = False,
                    disable_adaptive: bool = False,
                    force_profile: Optional[str] = None) -> Dict[str, Any]:
    """应用命令行开关覆盖。

    - disable_adaptive=True 时，强制采用 small 档（全开），忽略行数；
    - disable_dyninst / disable_chunk_split / disable_anti_heuristic
      将对应字段置零/False；
    - force_profile 可强制指定 'small'/'medium'/'large'（调试用）。
    """
    if force_profile:
        if force_profile == "small":
            profile = dict(_PROFILE_SMALL)
        elif force_profile == "medium":
            profile = dict(_PROFILE_MEDIUM)
        elif force_profile == "large":
            profile = dict(_PROFILE_LARGE)
        else:
            raise ValueError(f"未知 profile: {force_profile}")

    if disable_adaptive:
        # 关闭自适应 = 强制全开
        profile = dict(_PROFILE_SMALL)
        profile["name"] = "forced-full"

    if disable_dyninst:
        profile["dyninst_points"] = 0
    if disable_chunk_split:
        profile["chunk_split_max_order"] = 0
    if disable_anti_heuristic:
        profile["anti_heuristic"] = False

    return profile


def emit_debug_report(profile: Dict[str, Any],
                      stats: Dict[str, Any],
                      stream=None) -> None:
    """将自适应档位与各层统计输出到 stderr（调试模式专用）。

    不影响脚本产物，仅供排查兼容性问题。
    """
    stream = stream or sys.stderr
    report = {
        "profile": profile.get("name"),
        "lines": profile.get("lines"),
        "config": {k: v for k, v in profile.items()
                   if k not in ("name", "lines")},
        "stats": stats,
    }
    try:
        stream.write("=== Ultimate Ninja Obfuscator (debug) ===\n")
        stream.write(json.dumps(report, indent=2, ensure_ascii=False,
                                default=str))
        stream.write("\n")
    except Exception:
        # 调试输出绝不能影响主流程
        pass


def make_seed(rng: Optional[random.Random] = None) -> int:
    """生成一个 32 位随机种子（供多态层使用）。"""
    r = rng or random.Random()
    return r.randint(0, 0xFFFFFFFF)


def should_debug_log(debug: bool) -> bool:
    """供各层判断是否注入隐蔽日志。"""
    return bool(debug)
