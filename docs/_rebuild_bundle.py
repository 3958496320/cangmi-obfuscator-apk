# -*- coding: utf-8 -*-
"""
重新合并 src/ 各模块生成 docs/obfuscator_all.py（bundle 单文件版）。

合并规则：
1. 跳过 gui.py / gui_kivy.py / main.py
2. 按依赖顺序拼接，模块间用分界标记分隔
3. 去掉每个模块开头的 from __future__ / import / from xxx import
   （bundle 头部已有统一 import，跨模块导入在单文件内不需要）
4. adaptive_engine 置于 polymorphism 之后（覆盖 make_seed）
5. 保留 obfuscator_all.py 原头部（统一 import 段）
"""
import os
import re

SRC_DIR = "/workspace/src"
BUNDLE_PATH = "/workspace/docs/obfuscator_all.py"

# 合并顺序（与 obfuscator_all.py 原顺序一致）
MODULE_ORDER = [
    "ast_parser.py",
    "util.py",
    "string_encryptor.py",
    "renamer.py",
    "control_flow.py",
    "garbage_injector.py",
    "polymorphism.py",
    "anti_deobfuscation.py",
    "runtime_protection.py",
    "dyninst.py",
    "chunk_split.py",
    "anti_heuristic.py",
    "adaptive_engine.py",
    "obfuscator_core.py",
]

# 跳过的模块
SKIP = {"gui.py", "gui_kivy.py", "main.py"}


def strip_module_header(src: str) -> str:
    """去掉模块开头的 from __future__ / import / from xxx import 行。

    保留：
    - # -*- coding -*- 文件编码声明（保留，无害）
    - 模块 docstring
    - 顶层常量、类、函数定义

    去掉：
    - from __future__ import ...
    - import xxx
    - from xxx import yyy
      （但保留 from typing import ... 等标准库导入？不，bundle 头部已有）
    """
    lines = src.split("\n")
    out = []
    skip_imports = True
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 文件编码声明保留
        if stripped.startswith("# -*- coding"):
            out.append(line)
            continue
        # 模块 docstring 起始（"""）—— 遇到就停止跳过导入
        if stripped.startswith('"""') or stripped.startswith("'''"):
            skip_imports = False
            out.append(line)
            continue
        # 跳过 import 区
        if skip_imports:
            if stripped == "" or stripped.startswith("#"):
                # 注释和空行：保留（可能是文件头注释）
                # 但如果是纯粹的 import 区间的注释，也跳过
                # 简单规则：在遇到 docstring 前的注释保留，import 跳过
                if re.match(r"^(from\s+\S+\s+import|import\s+\S+)", stripped):
                    continue
                # from __future__
                if stripped.startswith("from __future__"):
                    continue
                out.append(line)
                continue
            else:
                # 非空非注释非 import —— 遇到第一个实际代码，停止跳过
                # 但要先检查是不是 import
                if re.match(r"^(from\s+\S+\s+import\s|import\s+\S+)", stripped):
                    continue
                if stripped.startswith("from __future__"):
                    continue
                skip_imports = False
                out.append(line)
                continue
        else:
            out.append(line)
    return "\n".join(out)


def build_bundle():
    # 读取原 bundle 头部（到第一个模块分界标记之前）
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    # 头部 = 第一个 "# === ast_parser.py ===" 之前的内容
    header_end = original.find("# === ast_parser.py ===")
    if header_end == -1:
        raise RuntimeError("找不到 ast_parser.py 分界标记")
    # 往前找分界标记前的注释行（# ===）
    header_end = original.rfind("# ===", 0, header_end)
    header = original[:header_end].rstrip() + "\n"

    # 拼接各模块
    parts = [header]
    for mod_name in MODULE_ORDER:
        if mod_name in SKIP:
            continue
        mod_path = os.path.join(SRC_DIR, mod_name)
        if not os.path.isfile(mod_path):
            print(f"警告: {mod_path} 不存在，跳过")
            continue
        with open(mod_path, "r", encoding="utf-8") as f:
            mod_src = f.read()
        mod_body = strip_module_header(mod_src)
        # 模块分界标记
        parts.append(f"\n# =============================================================================
# === {mod_name} ===
# =============================================================================")
        parts.append(mod_body.rstrip())

    bundle = "\n".join(parts) + "\n"

    with open(BUNDLE_PATH, "w", encoding="utf-8") as f:
        f.write(bundle)

    # 统计
    line_count = bundle.count("\n")
    print(f"已生成 {BUNDLE_PATH}")
    print(f"  总行数: {line_count}")
    print(f"  模块数: {len(MODULE_ORDER)}")
    # 验证关键修复
    for kw in ["_mark_table_field_keys", "_perm", "JumpTable", "TableField"]:
        cnt = bundle.count(kw)
        print(f"  {kw}: {cnt} 处")


if __name__ == "__main__":
    build_bundle()
