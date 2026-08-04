#!/usr/bin/env python3
"""
测试：直接复制原始APK，不做任何修改，看是否能生成有效APK
"""
import zipfile
import struct
import os

ORIGINAL_APK = "/workspace/ultimate_ninja_obfuscator/.buildozer/android/platform/build-arm64-v8a/dists/cangmiobfuscator/build/outputs/apk/debug/cangmiobfuscator-debug.apk"
OUTPUT_APK = "/workspace/ultimate_ninja_obfuscator/bin/test_copy.apk"
ALIGNMENT = 4

with open(ORIGINAL_APK, 'rb') as fin:
    with zipfile.ZipFile(ORIGINAL_APK, 'r') as zin:
        entries = []
        for info in zin.infolist():
            name = info.filename
            # 跳过签名
            if name.startswith('META-INF/') and (
                name.endswith('.SF') or name.endswith('.RSA') or 
                name.endswith('.DSA') or name.endswith('.EC') or
                name == 'META-INF/MANIFEST.MF'
            ):
                continue
            
            name_len = len(info.filename.encode('utf-8'))
            extra_len = len(info.extra)
            local_header_size = 30 + name_len + extra_len
            data_offset_in_file = info.header_offset + local_header_size
            
            fin.seek(data_offset_in_file)
            data = fin.read(info.compress_size)
            
            entries.append({
                'info': info,
                'data': data,
            })

with open(OUTPUT_APK, 'wb') as fout:
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

print(f"输出: {OUTPUT_APK}")
with zipfile.ZipFile(OUTPUT_APK, 'r') as z:
    bad = z.testzip()
    print(f"ZIP测试: {bad if bad else 'OK'}")
