#!/usr/bin/env python3
"""
完整APK构建流程：
1. 从原始APK提取private.tar
2. 替换main.py和src/*.py为新代码
3. 用Python 3.12重新编译.pyc
4. 重建APK，保持原始压缩方式
5. zipalign 4字节对齐
6. jarsigner签名
"""
import zipfile
import shutil
import os
import tarfile
import tempfile
import subprocess
import struct

ORIGINAL_APK = "/workspace/ultimate_ninja_obfuscator/.buildozer/android/platform/build-arm64-v8a/dists/cangmiobfuscator/build/outputs/apk/debug/cangmiobfuscator-debug.apk"
MAIN_PY = "/workspace/ultimate_ninja_obfuscator/main.py"
SRC_DIR = "/workspace/ultimate_ninja_obfuscator/src"
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
PYTHON312 = "/root/.pyenv/versions/3.12.13/bin/python"
KEYSTORE = "/root/.android/debug.keystore"
ALIGNMENT = 4

work_dir = tempfile.mkdtemp()
print(f"工作目录: {work_dir}")

# ============================================================
# Step 1: 准备新的private.tar
# ============================================================
print("\n=== Step 1: 准备新的private.tar ===")

with zipfile.ZipFile(ORIGINAL_APK, 'r') as z:
    priv_tar_data = z.read('assets/private.tar')

priv_tar_path = os.path.join(work_dir, 'orig_private.tar')
with open(priv_tar_path, 'wb') as f:
    f.write(priv_tar_data)

tar_extract = os.path.join(work_dir, 'private_src')
os.makedirs(tar_extract, exist_ok=True)
with tarfile.open(priv_tar_path) as tf:
    tf.extractall(tar_extract, filter='data')

# 备份sitecustomize.pyc等没有对应.py的文件
backup_pyc = {}
backup_dir = os.path.join(work_dir, '_backup_')
os.makedirs(backup_dir, exist_ok=True)
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.pyc'):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, tar_extract)
            py_rel = rel[:-4] + '.py'
            py_full = os.path.join(tar_extract, py_rel)
            if not os.path.exists(py_full):
                dest = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)
                backup_pyc[rel] = dest
                print(f"  备份: {rel}")

# 复制新代码
shutil.copy2(MAIN_PY, os.path.join(tar_extract, 'main.py'))
for f in os.listdir(SRC_DIR):
    if f.endswith('.py'):
        shutil.copy2(os.path.join(SRC_DIR, f), os.path.join(tar_extract, 'src', f))

# 删除所有.pyc
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))

# 用Python 3.12 -OO编译
print("用Python 3.12编译...")
subprocess.run([PYTHON312, '-OO', '-m', 'compileall', '-b', '-f', tar_extract], check=True)

# 删除.py源文件
for root, dirs, files in os.walk(tar_extract):
    for f in files:
        if f.endswith('.py'):
            os.remove(os.path.join(root, f))

# 恢复备份的.pyc
for rel, src in backup_pyc.items():
    dest = os.path.join(tar_extract, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)

# 重新打包tar
new_priv_tar = os.path.join(work_dir, 'new_private.tar')
with tarfile.open(new_priv_tar, 'w') as tf:
    for item in sorted(os.listdir(tar_extract)):
        full = os.path.join(tar_extract, item)
        tf.add(full, arcname=item)

print(f"新private.tar: {os.path.getsize(new_priv_tar)} bytes")

# 验证.pyc magic
with open(os.path.join(tar_extract, 'main.pyc'), 'rb') as f:
    magic = f.read(4)
    print(f"main.pyc magic: {magic.hex()}")

# ============================================================
# Step 2: 重建APK，保持原始压缩方式
# ============================================================
print("\n=== Step 2: 重建APK ===")
temp_apk = os.path.join(work_dir, 'unsigned.apk')

with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
    with zipfile.ZipFile(temp_apk, 'w') as zout:
        for item in zin.infolist():
            name = item.filename
            
            # 跳过签名文件
            if name.startswith('META-INF/') and (
                name.endswith('.SF') or name.endswith('.RSA') or 
                name.endswith('.DSA') or name.endswith('.EC') or
                name == 'META-INF/MANIFEST.MF'
            ):
                continue
            
            if name == 'assets/private.tar':
                with open(new_priv_tar, 'rb') as f:
                    data = f.read()
                # 使用原始info以保持一致
                zout.writestr(item, data)
            else:
                data = zin.read(name)
                zout.writestr(item, data)

print(f"未签名APK: {os.path.getsize(temp_apk)} bytes")

# ============================================================
# Step 3: zipalign 4字节对齐
# ============================================================
print("\n=== Step 3: zipalign对齐 ===")

aligned_apk = os.path.join(work_dir, 'aligned.apk')

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
        
        if compress_type == zipfile.ZIP_STORED:
            padding_needed = (ALIGNMENT - (data_offset % ALIGNMENT)) % ALIGNMENT
            if padding_needed > 0:
                # zipalign padding: APK_ALIGNMENT_ZIP_EXTRA_FIELD_ID = 0xd935
                # 结构：ID(2) + Length(2) + padding
                if padding_needed >= 4:
                    padding_extra = struct.pack('<HH', 0xd935, padding_needed - 4) + b'\x00' * (padding_needed - 4)
                    extra = extra + padding_extra
                    local_header_size = 30 + len(name_bytes) + len(extra)
                    data_offset = current_offset + local_header_size
                else:
                    # padding_needed < 4, 无法使用4字节对齐extra，不处理
                    pass
        
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

print(f"对齐后APK: {os.path.getsize(aligned_apk)} bytes")

# 验证对齐
print("验证对齐...")
with zipfile.ZipFile(aligned_apk, 'r') as z:
    misaligned = []
    for name in z.namelist():
        info = z.getinfo(name)
        if info.compress_type == 0:
            local_header_size = 30 + len(info.filename.encode('utf-8')) + len(info.extra)
            data_offset = info.header_offset + local_header_size
            if data_offset % 4 != 0:
                misaligned.append((name, data_offset))
    if misaligned:
        print("  未对齐文件:")
        for name, offset in misaligned:
            print(f"    {name}: {offset}")
    else:
        print("  ✓ 所有STORED文件已对齐")

# ============================================================
# Step 4: jarsigner签名
# ============================================================
print("\n=== Step 4: jarsigner签名 ===")
shutil.copy2(aligned_apk, OUTPUT_APK)

result = subprocess.run([
    'jarsigner', '-sigalg', 'SHA256withRSA', '-digestalg', 'SHA-256',
    '-keystore', KEYSTORE, '-storepass', 'android', '-keypass', 'android',
    OUTPUT_APK, 'androiddebugkey'
], capture_output=True, text=True)

print("签名输出:", result.stdout[-300:] if result.stdout else "")
if result.returncode != 0:
    print("签名错误:", result.stderr)
    raise Exception("签名失败")

print(f"\n=== 完成! ===")
print(f"输出: {OUTPUT_APK}")
print(f"大小: {os.path.getsize(OUTPUT_APK)} bytes")
