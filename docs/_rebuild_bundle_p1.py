# -*- coding: utf-8 -*-
"""
重建 docs/obfuscator_all.py（网页版单文件 bundle），纳入 vm_pro P1 三件套。

当前 src/ 已合并为单文件 obfuscator_core.py（含全部子模块）+ vm_pro.py。
本脚本：
  1. 保留原 bundle 头部（统一 import 段）
  2. 追加 src/obfuscator_core.py 主体（剥离与头部重复的 stdlib import）
  3. 追加 src/vm_pro.py 主体（保留 typing / Node 导入，剥离重复的 random/future）
vm_pro 的导入在 obfuscate() 内做了 bundle 兼容（ImportError → 同文件名）。
"""
import os
import re

SRC_DIR = "/workspace/src"
BUNDLE_PATH = "/workspace/docs/obfuscator_all.py"

# bundle 头部已提供的导入（这些在追加模块时剥离，避免重复）
HEADER_IMPORTS = {
    "from __future__", "import json", "import os", "import random",
    "import re", "import string", "import sys", "import time",
}


def strip_header_imports(src: str) -> str:
    """剥离模块顶部的 coding 声明、docstring、from __future__、
    以及与 bundle 头部重复的 stdlib import。
    保留 typing / Node 等非重复导入与所有实际代码。"""
    lines = src.split("\n")
    out = []
    in_docstring = False
    docstring_quote = None
    # 头部区：持续跳过 import / docstring / coding / 空行 / 纯注释，
    # 直到遇到第一行「实际代码」（def/class/常量赋值/非 import 语句）
    in_header = True
    for line in lines:
        stripped = line.strip()

        # docstring 处理
        if in_docstring:
            out.append(line)
            if docstring_quote in stripped:
                in_docstring = False
            continue

        if in_header:
            # coding 声明：跳过
            if stripped.startswith("# -*- coding"):
                continue
            # 空行 / 纯注释：在头部跳过（避免重复头部注释）
            if stripped == "" or stripped.startswith("#"):
                # 但如果是模块功能性注释（非头部说明），保守起见保留
                # 这里简单跳过头部注释行
                continue
            # docstring 起始
            if stripped.startswith('"""') or stripped.startswith("'''"):
                q = '"""' if stripped.startswith('"""') else "'''"
                docstring_quote = q
                in_docstring = True
                out.append(line)
                # 单行 docstring
                if stripped.count(q) >= 2 and len(stripped) > 3:
                    in_docstring = False
                continue
            # from __future__
            if stripped.startswith("from __future__"):
                continue
            # 与 bundle 头部重复的 stdlib import
            if _is_dup_import(stripped):
                continue
            # 到达实际代码：停止头部剥离
            in_header = False
            out.append(line)
        else:
            out.append(line)
    return "\n".join(out).strip() + "\n"


def _is_dup_import(stripped: str) -> bool:
    """判断是否为与 bundle 头部重复的 stdlib import。"""
    # import random / import json / ...
    m = re.match(r"^(import\s+(\w+))", stripped)
    if m and m.group(2) in {"json", "os", "random", "re", "string", "sys", "time"}:
        return True
    # import string as _string
    m = re.match(r"^import\s+string\s+as\s+\w+", stripped)
    if m:
        return True
    # from __future__
    if stripped.startswith("from __future__"):
        return True
    return False


def build_bundle():
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    # 头部 = 第一个 "# === " 段分界标记之前的内容（幂等：支持重复重建）
    m = re.search(r"\n# === ", original)
    if m is None:
        # 没有分界标记：整个文件当头部，从零重建
        header = original.rstrip() + "\n\n"
    else:
        header = original[:m.start()].rstrip() + "\n\n"

    parts = [header]

    # 1) obfuscator_core.py（单文件 monolith，含全部子模块）
    with open(os.path.join(SRC_DIR, "obfuscator_core.py"), "r", encoding="utf-8") as f:
        oc_body = strip_header_imports(f.read())
    parts.append("# =============================================================================\n"
                 "# === obfuscator_core.py (monolith: ast_parser..adaptive_engine..core) ===\n"
                 "# =============================================================================\n")
    parts.append(oc_body)

    # 2) vm_pro.py（P0+P1 三件套：花指令/自修改dispatcher/字符串加密/反trace/控制流平坦化/CRC32防篡改）
    with open(os.path.join(SRC_DIR, "vm_pro.py"), "r", encoding="utf-8") as f:
        vp_body = strip_header_imports(f.read())
    parts.append("\n# =============================================================================\n"
                 "# === vm_pro.py (P0+P1 付费级字节码 VM) ===\n"
                 "# =============================================================================\n")
    parts.append(vp_body)

    bundle = "\n".join(parts) + "\n"
    with open(BUNDLE_PATH, "w", encoding="utf-8") as f:
        f.write(bundle)

    line_count = bundle.count("\n")
    print(f"已生成 {BUNDLE_PATH}")
    print(f"  总行数: {line_count}")
    # 关键标记校验
    for kw in ["vm_pro_compile", "_vm_pro_compile", "_CRC32_TABLE", "ProVMCompiler",
               "jump_targets", "crc", "P1-3"]:
        cnt = bundle.count(kw)
        print(f"  {kw}: {cnt} 处")


if __name__ == "__main__":
    build_bundle()
