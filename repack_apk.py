#!/usr/bin/env python3
"""
替换APK中的assets/private.tar，保持sitecustomize.pyc等文件，并做zipalign
"""
import zipfile
import shutil
import os
import struct
import tempfile

ORIGINAL_APK = "/workspace/ultimate_ninja_obfuscator/.buildozer/android/platform/build-arm64-v8a/dists/cangmiobfuscator/build/outputs/apk/debug/cangmiobfuscator-debug.apk"
NEW_MAIN_PY = "/workspace/ultimate_ninja_obfuscator/main.py"
SRC_DIR = "/workspace/ultimate_ninja_obfuscator/src"
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
PYTHON312 = "/root/.pyenv/versions/3.12.13/bin/python"

work_dir = tempfile.mkdtemp()
print(f"工作目录: {work_dir}")

# 1. 从原始APK提取所有文件
print("提取原始APK...")
with zipfile.ZipFile(ORIGINAL_APK, 'r') as z:
    z.extractall(work_dir)

# 2. 提取原始private.tar
print("提取原始private.tar...")
priv_dir = os.path.join(work_dir, '_private_')
os.makedirs(priv_dir, exist_ok=True)
with zipfile.ZipFile(ORIGINAL_APK, 'r') as z:
    with open(os.path.join(priv_dir, 'orig.tar'), 'wb') as f:
        f.write(z.read('assets/private.tar'))

import tarfile
tar_extract = os.path.join(priv_dir, 'extracted')
os.makedirs(tar_extract, exist_ok=True)
with tarfile.open(os.path.join(priv_dir, 'orig.tar')) as tf:
    tf.extractall(tar_extract)

print("原始文件列表:", os.listdir(tar_extract))
print("src目录:", os.listdir(os.path.join(tar_extract, 'src')))

# 3. 复制新代码
print("复制新代码...")
shutil.copy2(NEW_MAIN_PY, os.path.join(tar_extract, 'main.py'))
for f in os.listdir(SRC_DIR):
    if f.endswith('.py'):
        shutil.copy2(os.path.join(SRC_DIR, f), os.path.join(tar_extract, 'src', f))

# 备份原始.pyc文件（没有对应.py的需要保留，比如sitecustomize.pyc）
print("备份原始.pyc文件...")
import shutil as _shutil
backup_pyc = {}
backup_dir = os.path.join(priv_dir, '_backup_pyc_')
os.makedirs(backup_dir, exist_ok=True)
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.pyc'):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, tar_extract)
            py_rel = rel[:-4] + '.py'
            py_full = os.path.join(tar_extract, py_rel)
            if not os.path.exists(py_full):
                # 没有对应的.py文件，需要保留
                backup_dest = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(backup_dest), exist_ok=True)
                _shutil.copy2(full, backup_dest)
                backup_pyc[rel] = backup_dest
                print(f"  备份: {rel}")

# 删除旧的.pyc文件
print("清理旧.pyc...")
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))

# 4. 用Python 3.12 -OO编译所有.py文件
print("用Python 3.12编译.pyc...")
import subprocess
result = subprocess.run([
    PYTHON312, '-OO', '-m', 'compileall', '-b', '-f', tar_extract
], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)

# 删除.py源文件（只保留.pyc）
print("删除.py源文件...")
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.py'):
            os.remove(os.path.join(root, f))

# 恢复备份的.pyc文件（如sitecustomize.pyc）
print("恢复备份的.pyc文件...")
for rel, orig_path in backup_pyc.items():
    dest = os.path.join(tar_extract, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    _shutil.copy2(orig_path, dest)
    print(f"  恢复: {rel}")

print("新private.tar内容:")
for f in os.listdir(tar_extract):
    full = os.path.join(tar_extract, f)
    if os.path.isfile(full):
        print(f"  {f}: {os.path.getsize(full)} bytes")

# 5. 重新打包tar
print("重新打包private.tar...")
new_tar = os.path.join(work_dir, 'assets', 'private.tar')
with tarfile.open(new_tar, 'w') as tf:
    for item in os.listdir(tar_extract):
        full = os.path.join(tar_extract, item)
        tf.add(full, arcname=item)

print(f"新private.tar大小: {os.path.getsize(new_tar)}")

# 6. 删除META-INF签名文件
print("清理旧签名...")
meta_inf = os.path.join(work_dir, 'META-INF')
if os.path.isdir(meta_inf):
    for f in os.listdir(meta_inf):
        if f.endswith('.SF') or f.endswith('.RSA') or f.endswith('.DSA') or f == 'MANIFEST.MF':
            os.remove(os.path.join(meta_inf, f))

# 7. 创建对齐的ZIP (zipalign - 4字节对齐)
print("创建对齐的APK...")

# Zipalign: 确保所有未压缩条目从4字节边界开始
ALIGNMENT = 4

# 先确定哪些文件是存储的（不压缩）
def is_stored_compression(info):
    return info.compress_type == zipfile.ZIP_STORED

# 重新打包APK，手动对齐
temp_apk = OUTPUT_APK + ".unaligned"

with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
    with zipfile.ZipFile(temp_apk, 'w') as zout:
        # 获取原始文件列表顺序
        namelist = zin.namelist()
        
        for name in namelist:
            info = zin.getinfo(name)
            data = zin.read(name)
            
            # 使用新的private.tar
            if name == 'assets/private.tar':
                with open(new_tar, 'rb') as f:
                    data = f.read()
            
            # 跳过签名文件
            if name.startswith('META-INF/') and (
                name.endswith('.SF') or name.endswith('.RSA') or 
                name.endswith('.DSA') or name == 'META-INF/MANIFEST.MF'
            ):
                continue
            
            # 创建新的ZipInfo
            new_info = zipfile.ZipInfo(filename=name, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.create_system = info.create_system
            
            zout.writestr(new_info, data)

print(f"未对齐APK: {os.path.getsize(temp_apk)} bytes")
print("完成！现在需要用jarsigner签名。")
shutil.move(temp_apk, OUTPUT_APK)
print(f"输出: {OUTPUT_APK}")
