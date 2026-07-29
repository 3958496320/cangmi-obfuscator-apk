#!/usr/bin/env python3
"""
只生成未签名但格式正确的APK
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
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/unsigned.apk"
PYTHON312 = "/root/.pyenv/versions/3.12.13/bin/python"

work_dir = tempfile.mkdtemp()

with zipfile.ZipFile(ORIGINAL_APK, 'r') as z:
    priv_tar_path = os.path.join(work_dir, 'orig_private.tar')
    with open(priv_tar_path, 'wb') as f:
        f.write(z.read('assets/private.tar'))

extract_dir = os.path.join(work_dir, 'private_src')
os.makedirs(extract_dir, exist_ok=True)
with tarfile.open(priv_tar_path, 'r') as tf:
    tf.extractall(extract_dir, filter='data')

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

shutil.copy2(MAIN_PY, os.path.join(extract_dir, 'main.py'))
for f in os.listdir(SRC_DIR):
    if f.endswith('.py'):
        shutil.copy2(os.path.join(SRC_DIR, f), os.path.join(extract_dir, 'src', f))

for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))

subprocess.run([PYTHON312, '-OO', '-m', 'compileall', '-b', '-f', extract_dir], check=True)

for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if f.endswith('.py'):
            os.remove(os.path.join(root, f))
for rel, src in backup_pyc.items():
    dest = os.path.join(extract_dir, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)

new_tar = os.path.join(work_dir, 'new_private.tar')
with tarfile.open(new_tar, 'w') as tf:
    for item in sorted(os.listdir(extract_dir)):
        full = os.path.join(extract_dir, item)
        tf.add(full, arcname=item)

with open(new_tar, 'rb') as f:
    new_tar_data = f.read()

ALIGNMENT = 4

def align_extra(item, current_offset):
    """返回对齐后的extra字段，zipalign -p 4"""
    name_bytes = item.filename.encode('utf-8')
    extra = item.extra
    if item.compress_type == zipfile.ZIP_STORED:
        local_header_size = 30 + len(name_bytes) + len(extra)
        data_offset = current_offset + local_header_size
        padding_needed = (ALIGNMENT - (data_offset % ALIGNMENT)) % ALIGNMENT
        if padding_needed:
            # zipalign padding extra field: id + size + payload, header占4字节
            # 找到最小total_padding>=4且能使data_offset对齐到ALIGNMENT
            total_padding = padding_needed
            while total_padding < 4 or (data_offset + total_padding) % ALIGNMENT != 0:
                total_padding += ALIGNMENT
            payload_size = total_padding - 4
            padding = struct.pack('<HH', 0xd935, payload_size) + b'\x00' * payload_size
            extra = extra + padding
    return extra

with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
    with zipfile.ZipFile(OUTPUT_APK, 'w') as zout:
        for item in zin.infolist():
            name = item.filename
            if name.startswith('META-INF/') and (
                name.endswith('.SF') or name.endswith('.RSA') or
                name.endswith('.DSA') or name.endswith('.EC') or
                name == 'META-INF/MANIFEST.MF'
            ):
                continue

            if name == 'assets/private.tar':
                new_item = zipfile.ZipInfo(filename=name, date_time=item.date_time)
                new_item.compress_type = item.compress_type
                new_item.extract_version = item.extract_version
                new_item.create_version = item.create_version
                new_item.flag_bits = item.flag_bits
                new_item.extra = align_extra(new_item, zout.fp.tell())
                new_item.comment = item.comment
                new_item.internal_attr = item.internal_attr
                new_item.external_attr = item.external_attr
                zout.writestr(new_item, new_tar_data)
            else:
                data = zin.read(name)
                new_item = zipfile.ZipInfo(filename=name, date_time=item.date_time)
                new_item.compress_type = item.compress_type
                new_item.extract_version = item.extract_version
                new_item.create_version = item.create_version
                new_item.flag_bits = item.flag_bits
                new_item.extra = align_extra(new_item, zout.fp.tell())
                new_item.comment = item.comment
                new_item.internal_attr = item.internal_attr
                new_item.external_attr = item.external_attr
                zout.writestr(new_item, data)

print(f"未签名APK: {OUTPUT_APK}")
with zipfile.ZipFile(OUTPUT_APK, 'r') as z:
    bad = z.testzip()
    print(f"ZIP测试: {bad if bad else 'OK'}")
    data = z.read('assets/private.tar')
    print(f"private.tar: {len(data)} bytes")
