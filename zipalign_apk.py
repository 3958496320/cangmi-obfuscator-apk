#!/usr/bin/env python3
"""
实现 zipalign -p 4 对齐，并重新签名
"""
import zipfile
import struct
import io
import os
import shutil
import subprocess

APK_IN = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
APK_OUT = APK_IN
ALIGNMENT = 4

def zipalign(apk_in, apk_out):
    with zipfile.ZipFile(apk_in, 'r') as zin:
        entries = []
        # 读取所有文件
        for info in zin.infolist():
            entries.append({
                'info': info,
                'data': zin.read(info.filename),
            })
    
    # 构建新的ZIP，保持顺序，对STORED文件对齐
    with open(apk_out, 'wb') as fout:
        current_offset = 0
        central_dir = []
        
        for entry in entries:
            info = entry['info']
            data = entry['data']
            name = info.filename
            name_bytes = name.encode('utf-8')
            extra = info.extra
            compress_type = info.compress_type
            
            # 计算本地文件头大小
            local_header_size = 30 + len(name_bytes) + len(extra)
            data_offset = current_offset + local_header_size
            
            if compress_type == zipfile.ZIP_STORED:
                # 对 STORED 文件做对齐
                padding_needed = (ALIGNMENT - (data_offset % ALIGNMENT)) % ALIGNMENT
                if padding_needed:
                    # 在extra字段后添加zipalign padding
                    # zipalign padding格式: 0xd935 (或 0x0000) + size
                    # 标准zipalign用0xd935 padding
                    padding = struct.pack('<HH', 0xd935, padding_needed) + b'\x00' * (padding_needed - 4)
                    extra = extra + padding
                    local_header_size = 30 + len(name_bytes) + len(extra)
                    data_offset = current_offset + local_header_size
            
            # 写本地文件头
            local_header = struct.pack(
                '<IHHHHHIIIHH',
                0x04034b50,  # local file header signature
                info.extract_version,
                info.flag_bits,
                compress_type,
                0,  # dostime (we don't need accurate time)
                0,  # dosdate
                0,  # crc (will be in data descriptor if needed, but we have it)
                info.compress_size,
                info.file_size,
                len(name_bytes),
                len(extra)
            )
            fout.write(local_header)
            fout.write(name_bytes)
            fout.write(extra)
            
            # 写数据
            data_start = fout.tell()
            assert data_start == data_offset
            fout.write(data)
            
            # 记录central directory信息
            central_dir.append({
                'info': info,
                'name': name_bytes,
                'offset': current_offset,
                'extra': extra,
            })
            
            current_offset = fout.tell()
        
        # 写Central Directory
        cd_start = current_offset
        for entry in central_dir:
            info = entry['info']
            name_bytes = entry['name']
            extra = entry['extra']
            comment = info.comment
            
            central_header = struct.pack(
                '<IHHHHHHIIIHHHHHII',
                0x02014b50,  # central directory signature
                info.create_version,
                info.extract_version,
                info.flag_bits,
                info.compress_type,
                0,  # dostime
                0,  # dosdate
                info.CRC,
                info.compress_size,
                info.file_size,
                len(name_bytes),
                len(extra),
                len(comment),
                0,  # disk number start
                info.internal_attr,
                info.external_attr,
                entry['offset']
            )
            fout.write(central_header)
            fout.write(name_bytes)
            fout.write(extra)
            fout.write(comment)
            current_offset = fout.tell()
        
        cd_end = current_offset
        cd_size = cd_end - cd_start
        
        # 写EOCD
        eocd = struct.pack(
            '<IHHHHIIH',
            0x06054b50,
            0,  # disk number
            0,  # disk with CD
            len(central_dir),
            len(central_dir),
            cd_size,
            cd_start,
            0   # comment length
        )
        fout.write(eocd)

print("对齐APK...")
zipalign(APK_IN, APK_IN + ".aligned")
print(f"对齐后: {os.path.getsize(APK_IN + '.aligned')} bytes")

# 对齐后重新签名（先清除旧签名）
print("重新签名...")
subprocess.run(['jarsigner', '-sigalg', 'SHA256withRSA', '-digestalg', 'SHA-256',
    '-keystore', '/root/.android/debug.keystore', '-storepass', 'android', '-keypass', 'android',
    APK_IN + '.aligned', 'androiddebugkey'], check=True, capture_output=True)

shutil.move(APK_IN + '.aligned', APK_IN)
print(f"完成: {APK_IN}")
print(f"大小: {os.path.getsize(APK_IN)} bytes")

# 验证对齐
print("\n验证对齐...")
with zipfile.ZipFile(APK_IN, 'r') as z:
    for name in z.namelist():
        info = z.getinfo(name)
        if info.compress_type == 0:
            header_offset = info.header_offset
            local_header_size = 30 + len(info.filename.encode('utf-8')) + len(info.extra)
            data_offset = header_offset + local_header_size
            if data_offset % 4 != 0:
                print(f"  未对齐: {name} offset={data_offset}")
            else:
                print(f"  对齐OK: {name}")
