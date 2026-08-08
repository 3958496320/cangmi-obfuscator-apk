# -*- coding: utf-8 -*-
"""诊断：看 AST 结构。"""
import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import parse_source, walk

src = 'print("HELLO_VM")'
ast = parse_source(src)
print("AST type:", ast.type)
body = ast.get("body") or []
print("body len:", len(body))
for i, s in enumerate(body):
    print(f"  stmt[{i}] type={s.type} attrs={list(s.attrs.keys())}")
    # 递归打印子节点
    def show(n, depth=2):
        if not hasattr(n, 'type'):
            return
        print("  "*depth + f"- {n.type}: {dict((k,('...' if isinstance(v, type(n)) else v)) for k,v in n.attrs.items())}")
        for k, v in n.attrs.items():
            if isinstance(v, type(n)):
                show(v, depth+1)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, type(n)):
                        show(item, depth+1)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, type(n)):
                                show(sub, depth+1)
    show(s)
