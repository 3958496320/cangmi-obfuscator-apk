#!/usr/bin/env python3
"""
精确替换APK中的assets/private.tar文件，保持APK结构完整
"""
import zipfile
import shutil
import os
import tempfile

# 原始能正常安装的APK
ORIGINAL_APK = "/workspace/ultimate_ninja_obfuscator/.buildozer/android/platform/build-arm64-v8a/dists/cangmiobfuscator/build/outputs/apk/debug/cangmiobfuscator-debug.apk"
# 我们的新private.tar
NEW_TAR = "/tmp/apk_work/new_private.tar"
# 输出APK
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"

print(f"读取原始APK: {ORIGINAL_APK}")
print(f"新private.tar: {NEW_TAR} ({os.path.getsize(NEW_TAR)} bytes)")

# 先读取新文件内容
with open(NEW_TAR, 'rb') as f:
    new_tar_data = f.read()

# 创建临时文件
work_dir = "/workspace/ultimate_ninja_obfuscator/bin"
os.makedirs(work_dir, exist_ok=True)

with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
    temp_path = OUTPUT_APK + ".tmp"
    with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'assets/private.tar':
                print(f"替换: {item.filename}")
                zout.writestr(item, new_tar_data)
            elif item.filename.startswith('META-INF/') and (
                item.filename.endswith('.SF') or 
                item.filename.endswith('.RSA') or 
                item.filename.endswith('.DSA') or
                item.filename.endswith('.EC') or
                item.filename == 'META-INF/MANIFEST.MF'
            ):
                print(f"移除签名文件: {item.filename}")
                continue
            else:
                zout.writestr(item, data)

shutil.move(temp_path, OUTPUT_APK)
print(f"已创建未签名APK: {OUTPUT_APK} ({os.path.getsize(OUTPUT_APK)} bytes)")
