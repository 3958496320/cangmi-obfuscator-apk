#!/usr/bin/env python3
"""
最简APK重建：只替换assets/private.tar，保留所有原始ZipInfo
"""
import zipfile
import tarfile
import shutil
import os
import tempfile
import subprocess
import struct

ORIGINAL_APK = "/workspace/ultimate_ninja_obfuscator/.buildozer/android/platform/build-arm64-v8a/dists/cangmiobfuscator/build/outputs/apk/debug/cangmiobfuscator-debug.apk"
MAIN_PY = "/workspace/ultimate_ninja_obfuscator/main.py"
SRC_DIR = "/workspace/ultimate_ninja_obfuscator/src"
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
PYTHON312 = "/root/.pyenv/versions/3.12.13/bin/python"
KEYSTORE = "/root/.android/debug.keystore"

work_dir = tempfile.mkdtemp()
print(f"工作目录: {work_dir}")

# 1. 提取原始private.tar
print("=== 1. 准备private.tar ===")
with zipfile.ZipFile(ORIGINAL_APK, 'r') as z:
    priv_tar_path = os.path.join(work_dir, 'orig_private.tar')
    with open(priv_tar_path, 'wb') as f:
        f.write(z.read('assets/private.tar'))

# 2. 解压
extract_dir = os.path.join(work_dir, 'private_src')
os.makedirs(extract_dir, exist_ok=True)
with tarfile.open(priv_tar_path, 'r') as tf:
    tf.extractall(extract_dir, filter='data')

# 3. 备份没有对应.py的.pyc
backup_dir = os.path.join(work_dir, 'backup')
os.makedirs(backup_dir, exist_ok=True)
backup_pyc = {}
for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if f.endswith('.pyc'):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, extract_dir)
            py_path = os.path.join(extract_dir, rel[:-4] + '.py')
            if not os.path.exists(py_path):
                dest = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)
                backup_pyc[rel] = dest

# 4. 复制新代码
shutil.copy2(MAIN_PY, os.path.join(extract_dir, 'main.py'))
for f in os.listdir(SRC_DIR):
    if f.endswith('.py'):
        shutil.copy2(os.path.join(SRC_DIR, f), os.path.join(extract_dir, 'src', f))

# 5. 删除所有.pyc
for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))

# 6. 编译
print("编译.pyc...")
subprocess.run([PYTHON312, '-OO', '-m', 'compileall', '-b', '-f', extract_dir], check=True)

# 7. 删除.py，恢复备份
for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if f.endswith('.py'):
            os.remove(os.path.join(root, f))
for rel, src in backup_pyc.items():
    dest = os.path.join(extract_dir, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)

# 8. 重新打包tar
new_tar = os.path.join(work_dir, 'new_private.tar')
with tarfile.open(new_tar, 'w') as tf:
    for item in sorted(os.listdir(extract_dir)):
        full = os.path.join(extract_dir, item)
        tf.add(full, arcname=item)

print(f"新private.tar大小: {os.path.getsize(new_tar)}")

# 9. 读取新的private.tar数据
with open(new_tar, 'rb') as f:
    new_tar_data = f.read()

# 10. 重建APK：完全保留原始ZipInfo，并做zipalign对齐
print("\n=== 2. 重建APK ===")
temp_apk = os.path.join(work_dir, 'unsigned.apk')

# 先创建不对齐的APK
with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
    with zipfile.ZipFile(temp_apk, 'w') as zout:
        for item in zin.infolist():
            name = item.filename
            
            # 跳过旧签名文件
            if name.startswith('META-INF/') and (
                name.endswith('.SF') or name.endswith('.RSA') or 
                name.endswith('.DSA') or name.endswith('.EC') or
                name == 'META-INF/MANIFEST.MF'
            ):
                continue
            
            if name == 'assets/private.tar':
                # 创建新的ZipInfo，复制关键字段，让zipfile自动计算CRC/size
                new_item = zipfile.ZipInfo(filename=name, date_time=item.date_time)
                new_item.compress_type = item.compress_type
                new_item.extract_version = item.extract_version
                new_item.create_version = item.create_version
                new_item.flag_bits = item.flag_bits
                new_item.extra = item.extra
                new_item.comment = item.comment
                new_item.internal_attr = item.internal_attr
                new_item.external_attr = item.external_attr
                zout.writestr(new_item, new_tar_data)
            else:
                data = zin.read(name)
                zout.writestr(item, data)

# 再做zipalign对齐
print("zipalign对齐...")
aligned_apk = os.path.join(work_dir, 'aligned.apk')
ALIGNMENT = 4

with zipfile.ZipFile(temp_apk, 'r') as zin:
    entries = []
    for info in zin.infolist():
        entries.append({'info': info, 'data': zin.read(info.filename)})

with open(aligned_apk, 'wb') as fout:
    current_offset = 0
    central_dir = []
    
    for entry in entries:
        info = entry['info']
        data = entry['data']
        name = info.filename
        name_bytes = name.encode('utf-8')
        extra = info.extra
        compress_type = info.compress_type
        
        local_header_size = 30 + len(name_bytes) + len(extra)
        data_offset = current_offset + local_header_size
        
        # 对STORED文件做4字节对齐
        if compress_type == zipfile.ZIP_STORED:
            padding_needed = (ALIGNMENT - (data_offset % ALIGNMENT)) % ALIGNMENT
            if padding_needed > 0:
                extra = extra + b'\x00' * padding_needed
                local_header_size = 30 + len(name_bytes) + len(extra)
                data_offset = current_offset + local_header_size
        
        local_header = struct.pack(
            '<IHHHHHIIIHH',
            0x04034b50,
            info.extract_version,
            info.flag_bits,
            compress_type,
            0, 0,
            info.CRC,
            info.compress_size,
            info.file_size,
            len(name_bytes),
            len(extra)
        )
        fout.write(local_header)
        fout.write(name_bytes)
        fout.write(extra)
        
        assert fout.tell() == data_offset
        fout.write(data)
        
        central_dir.append({
            'info': info,
            'name': name_bytes,
            'offset': current_offset,
            'extra': extra,
        })
        current_offset = fout.tell()
    
    cd_start = current_offset
    for entry in central_dir:
        info = entry['info']
        name_bytes = entry['name']
        extra = entry['extra']
        comment = info.comment
        
        central_header = struct.pack(
            '<IHHHHHHIIIHHHHHII',
            0x02014b50,
            info.create_version,
            info.extract_version,
            info.flag_bits,
            info.compress_type,
            0, 0,
            info.CRC,
            info.compress_size,
            info.file_size,
            len(name_bytes),
            len(extra),
            len(comment),
            0,
            info.internal_attr,
            info.external_attr,
            entry['offset']
        )
        fout.write(central_header)
        fout.write(name_bytes)
        fout.write(extra)
        fout.write(comment)
        current_offset = fout.tell()
    
    cd_size = current_offset - cd_start
    eocd = struct.pack(
        '<IHHHHIIH',
        0x06054b50,
        0, 0,
        len(central_dir),
        len(central_dir),
        cd_size,
        cd_start,
        0
    )
    fout.write(eocd)

shutil.move(aligned_apk, temp_apk)

# 测试未签名APK
print("测试未签名APK...")
with zipfile.ZipFile(temp_apk, 'r') as z:
    bad = z.testzip()
    if bad:
        print(f"ZIP测试失败: {bad}")
    else:
        print("ZIP测试OK")
    # 解压private.tar测试
    data = z.read('assets/private.tar')
    print(f"private.tar读取成功: {len(data)} bytes")

# 验证对齐
print("验证对齐...")
with zipfile.ZipFile(temp_apk, 'r') as z:
    misaligned = []
    for name in z.namelist():
        info = z.getinfo(name)
        if info.compress_type == 0:
            local_header_size = 30 + len(info.filename.encode('utf-8')) + len(info.extra)
            data_offset = info.header_offset + local_header_size
            if data_offset % 4 != 0:
                misaligned.append((name, data_offset))
    if misaligned:
        print('未对齐文件:')
        for name, offset in misaligned:
            print(f'  {name}: {offset}')
    else:
        print('✓ 所有STORED文件已4字节对齐')

# 11. 签名
shutil.copy2(temp_apk, OUTPUT_APK)
print("\n=== 3. 签名 ===")
result = subprocess.run([
    'jarsigner', '-sigalg', 'SHA256withRSA', '-digestalg', 'SHA-256',
    '-keystore', KEYSTORE, '-storepass', 'android', '-keypass', 'android',
    OUTPUT_APK, 'androiddebugkey'
], capture_output=True, text=True)
print(result.stdout[-500:] if result.stdout else "")
if result.returncode != 0:
    print("签名错误:", result.stderr)
    raise Exception("签名失败")

print(f"\n完成: {OUTPUT_APK} ({os.path.getsize(OUTPUT_APK)} bytes)")

# 12. 最终测试
print("\n最终测试...")
with zipfile.ZipFile(OUTPUT_APK, 'r') as z:
    bad = z.testzip()
    print(f"ZIP测试: {bad if bad else 'OK'}")
