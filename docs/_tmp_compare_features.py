# -*- coding: utf-8 -*-
"""对比各版本产物特征：定时自校验、VM、体积、保护层。"""
import sys, importlib.util
sys.path.insert(0, "/workspace/docs")
SRC = open("/workspace/docs/radar_input.lua").read()

VERSIONS = [
    ("当前优化版", "/workspace/docs/obfuscator_all.py"),
    ("HEAD dc818c8", "/tmp/obf_HEAD_dc818c8.py"),
    ("ca75b7e", "/tmp/obf_ca75b7e.py"),
    ("5f8c350", "/tmp/obf_5f8c350.py"),
    ("7664950", "/tmp/obf_7664950.py"),
    ("ba01255", "/tmp/obf_ba01255.py"),
]

def load(path):
    spec = importlib.util.spec_from_file_location('m'+str(hash(path)), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

for label, path in VERSIONS:
    try:
        mod = load(path)
        if 'ninja_mode' in mod.obfuscate_code.__code__.co_varnames:
            obf = mod.obfuscate_code(SRC, ninja_mode=True)
        else:
            obf = mod.obfuscate_code(SRC)
    except Exception as e:
        print(f"{label}: 加载/混淆失败 {e}")
        continue
    size_kb = len(obf.encode())/1024
    has_timer = "task.wait" in obf and "while true" in obf.lower() if "task" in obf else False
    has_spawn = "spawn" in obf
    has_vm = "_vm_" in obf or "VM_OPCODE" in obf or "_vm_decode" in obf
    has_loadstring = "loadstring" in obf
    # 统计行数和最长行
    lines = obf.split("\n")
    max_line_len = max(len(l) for l in lines) if lines else 0
    print(f"{label:14s} | {size_kb:6.1f}KB | {len(lines):4d}行 | 最长行{max_line_len:5d} | timer={'有' if has_timer else '无'} | spawn={'有' if has_spawn else '无'} | VM={'有' if has_vm else '无'} | loadstring={'有' if has_loadstring else '无'}")
