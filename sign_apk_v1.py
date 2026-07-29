#!/usr/bin/env python3
"""
用debug keystore对zipalign后的unsigned APK做v1签名，并保持zipalign对齐。
"""
import zipfile
import struct
import os
import base64
import hashlib
import shutil
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs7

UNSIGNED_APK = "/workspace/ultimate_ninja_obfuscator/bin/unsigned.apk"
SIGNED_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
KEY_PEM = "/tmp/debug_key.pem"
ALIGNMENT = 4


def load_key_and_cert():
    with open(KEY_PEM, 'rb') as f:
        data = f.read()
    key = serialization.load_pem_private_key(data, password=None)
    cert = x509.load_pem_x509_certificate(data)
    return key, cert


def align_extra(item, current_offset):
    """返回使STORED文件data_offset对齐的extra字段"""
    name_bytes = item.filename.encode('utf-8')
    extra = item.extra
    if item.compress_type == zipfile.ZIP_STORED:
        local_header_size = 30 + len(name_bytes) + len(extra)
        data_offset = current_offset + local_header_size
        padding_needed = (ALIGNMENT - (data_offset % ALIGNMENT)) % ALIGNMENT
        if padding_needed:
            total_padding = padding_needed
            while total_padding < 4 or (data_offset + total_padding) % ALIGNMENT != 0:
                total_padding += ALIGNMENT
            payload_size = total_padding - 4
            padding = struct.pack('<HH', 0xd935, payload_size) + b'\x00' * payload_size
            extra = extra + padding
    return extra


def digest_base64(data):
    return base64.b64encode(hashlib.sha256(data).digest()).decode('ascii')


def line_wrap(s, width=70):
    return '\r\n'.join(s[i:i + width] for i in range(0, len(s), width))


def build_manifest(zin):
    lines = [
        'Manifest-Version: 1.0',
        'Built-By: Generated-by-ADT',
        'Created-By: Android Gradle 8.1.0',
        '',
    ]
    for info in zin.infolist():
        name = info.filename
        if name.startswith('META-INF/'):
            continue
        data = zin.read(name)
        lines.append(f'Name: {name}')
        lines.append(f'SHA-256-Digest: {digest_base64(data)}')
        lines.append('')
    return '\r\n'.join(lines).encode('utf-8')


def build_cert_sf(manifest_data, zin):
    """生成CERT.SF，内容与jarsigner一致"""
    # 主摘要
    main_digest = digest_base64(manifest_data)
    lines = [
        'Signature-Version: 1.0',
        'Created-By: 1.0 (Android)',
        f'SHA-256-Digest-Manifest: {main_digest}',
        '',
    ]
    # 每个条目的摘要（对Manifest.MF中对应条目做摘要）
    entries = []
    current = []
    for line in manifest_data.decode('utf-8').split('\r\n'):
        if line == '' and current:
            # 一个条目结束
            block = '\r\n'.join(current) + '\r\n\r\n'
            entries.append(block)
            current = []
        elif line.startswith('Name: '):
            name = line[6:]
            current.append(line)
        elif current:
            current.append(line)

    for block in entries:
        # 找到Name
        name = None
        for line in block.split('\r\n'):
            if line.startswith('Name: '):
                name = line[6:]
                break
        if name:
            lines.append(f'Name: {name}')
            lines.append(f'SHA-256-Digest: {digest_base64(block.encode("utf-8"))}')
            lines.append('')
    return '\r\n'.join(lines).encode('utf-8')


def build_cert_rsa(cert_sf_data, key, cert):
    """生成PKCS#7 detached signature"""
    builder = pkcs7.PKCS7SignatureBuilder().set_data(cert_sf_data).add_signer(cert, key, hashes.SHA256())
    return builder.sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])


def sign_apk():
    key, cert = load_key_and_cert()

    # 先复制unsigned APK，然后追加签名文件
    shutil.copy(UNSIGNED_APK, SIGNED_APK)

    with zipfile.ZipFile(SIGNED_APK, 'a') as zout:
        pass  # 确认文件可写

    # 重新打开以精确控制写入
    # 读取现有entry并重新构建
    with zipfile.ZipFile(UNSIGNED_APK, 'r') as zin:
        manifest_data = build_manifest(zin)
        cert_sf_data = build_cert_sf(manifest_data, zin)
        cert_rsa_data = build_cert_rsa(cert_sf_data, key, cert)

    with zipfile.ZipFile(SIGNED_APK, 'w') as zout:
        def write_sig_file(name, data):
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.extract_version = 20
            info.create_version = 20
            info.flag_bits = 0
            info.extra = align_extra(info, zout.fp.tell())
            info.CRC = zipfile.crc32(data)
            info.file_size = len(data)
            info.compress_size = len(data)
            zout.writestr(info, data)

        # 1. 先写入所有签名文件（JarInputStream 要求签名块在前）
        write_sig_file('META-INF/MANIFEST.MF', manifest_data)
        write_sig_file('META-INF/CERT.SF', cert_sf_data)
        write_sig_file('META-INF/CERT.RSA', cert_rsa_data)

        # 2. 写入原始文件并保持对齐
        with zipfile.ZipFile(UNSIGNED_APK, 'r') as zin:
            for item in zin.infolist():
                new_item = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
                new_item.compress_type = item.compress_type
                new_item.extract_version = item.extract_version
                new_item.create_version = item.create_version
                new_item.flag_bits = item.flag_bits
                new_item.extra = align_extra(new_item, zout.fp.tell())
                new_item.comment = item.comment
                new_item.internal_attr = item.internal_attr
                new_item.external_attr = item.external_attr
                data = zin.read(item.filename)
                zout.writestr(new_item, data)

    print(f"已签名APK: {SIGNED_APK}")
    print(f"大小: {os.path.getsize(SIGNED_APK)} bytes")


if __name__ == '__main__':
    sign_apk()
