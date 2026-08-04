#!/usr/bin/env python3
"""
清除APK中的旧签名文件，保留其他所有内容
"""
import zipfile
import shutil
import os
import tempfile

APK_IN = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
APK_OUT = APK_IN + ".nosig"

with zipfile.ZipFile(APK_IN, 'r') as zin:
    with zipfile.ZipFile(APK_OUT, 'w') as zout:
        for item in zin.infolist():
            # 移除所有签名文件
            if item.filename.startswith('META-INF/') and (
                item.filename.endswith('.SF') or 
                item.filename.endswith('.RSA') or 
                item.filename.endswith('.DSA') or
                item.filename.endswith('.EC') or
                item.filename == 'META-INF/MANIFEST.MF'
            ):
                print(f"移除签名文件: {item.filename}")
                continue
            data = zin.read(item.filename)
            zout.writestr(item, data)

shutil.move(APK_OUT, APK_IN)
print(f"已清除签名: {APK_IN} ({os.path.getsize(APK_IN)} bytes)")
