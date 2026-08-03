# -*- coding: utf-8 -*-
"""
大脚本混淆测试工具
用法：
    python3 test_huge.py 你的脚本.lua
"""
import sys
import os
import time
import traceback

# 加载混淆引擎
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open('obfuscator_all.py').read())

def test_huge(path):
    if not os.path.exists(path):
        print(f'文件不存在: {path}')
        return

    print(f'读取: {path}')
    with open(path, 'r', encoding='utf-8', errors='surrogatepass') as f:
        src = f.read()

    src_lines = src.count('\n') + 1
    src_chars = len(src)
    print(f'原始: {src_lines} 行 / {src_chars} 字符 / {src_chars/1024:.1f} KB')
    print()

    # 估算档位
    prof = select_profile(src)
    print(f'将使用档位: {prof["name"]}')
    print(f'  dyninst_points: {prof["dyninst_points"]}')
    print(f'  garbage_ratio:  {prof["garbage_ratio"]}')
    print(f'  cff_max_states:  {prof["cff_max_states"]}')
    print(f'  vm_enable:       {prof["vm_enable"]}')
    print(f'  chunk_split:     {prof["chunk_split_max_order"]}')
    print()

    print('开始混淆...')
    t0 = time.time()
    try:
        result = obfuscate(src)
    except Exception as e:
        print('混淆失败:')
        traceback.print_exc()
        return
    elapsed = time.time() - t0

    code = result['code']
    stats = result['stats']
    out_lines = code.count('\n') + 1
    out_chars = len(code)

    print(f'耗时: {elapsed:.1f} 秒')
    print(f'输出: {out_lines} 行 / {out_chars} 字符 / {out_chars/1024:.1f} KB')
    print(f'膨胀倍数: {out_chars/src_chars:.1f}x 行 / {out_lines/src_lines:.1f}x 字符')
    print()
    print('=== 各层统计 ===')
    print(f'L1 字符串加密: {stats.get("L1_string_encryptor")}')
    print(f'L2 重命名:     {stats.get("L2_renamer")}')
    print(f'L3 控制流:     {stats.get("L3_control_flow")}')
    print(f'L4 垃圾注入:   {stats.get("L4_garbage")} 块')
    print(f'L5 反调试:     {stats.get("L5_anti_debug")}')
    print(f'L7 反自动化:   {stats.get("L7_pre_encryption")}')
    print(f'L8 运行时保护: {stats.get("L8_runtime_protection")}')
    print(f'L9 动态指令:   {stats.get("L9_dyninst")}')
    print(f'L10 块分割:    {stats.get("L10_chunk_split")}')
    print(f'L11 反启发式:   {stats.get("L11_anti_heuristic")}')
    print()

    # 保存输出
    out_path = path + '.obfuscated.lua'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f'已保存: {out_path}')
    print()

    # 风险评估
    print('=== 风险评估 ===')
    risk = []
    if out_chars > 5_000_000:
        risk.append(f'⚠️ 输出 {out_chars/1024/1024:.1f} MB 过大，注入器可能加载失败')
    if out_chars > 10_000_000:
        risk.append(f'🔴 输出 {out_chars/1024/1024:.1f} MB 严重过大，几乎肯定失败')
    if elapsed > 60:
        risk.append(f'⚠️ 耗时 {elapsed:.0f}s 较长，浏览器端可能超时')
    if stats.get('L3_control_flow', {}).get('vm_count', 0) > 0:
        risk.append(f'⚠️ 启用了 VM，大脚本输出膨胀严重')
    if not risk:
        print('✅ 看起来正常，可以尝试在网页端运行')
    else:
        for r in risk:
            print(r)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python3 test_huge.py 你的脚本.lua')
        sys.exit(1)
    test_huge(sys.argv[1])
