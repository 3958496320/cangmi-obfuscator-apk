#!/usr/bin/env python3
"""
为已有 v1 签名的 APK 追加 v2 签名块。

实现 Android APK Signature Scheme v2 (API 24+ 推荐，Android 11+ 必需)。
"""
import zipfile
import struct
import hashlib
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography import x509

SIGNED_V1_APK = "/workspace/ultimate_ninja_obfuscator/bin/cangmiobfuscator-debug-2.0.1.apk"
OUTPUT_APK = SIGNED_V1_APK
KEY_PEM = "/tmp/debug_key.pem"

# v2 签名常量
SIG_V2_BLOCK_ID = 0x7109871a
STRIPPING_PROTECTION_ATTR_ID = 0x0101

# 摘要算法：content digest 用 SHA-256 (id 0x01)
CONTENT_DIGEST_ALG_ID = 0x01
CONTENT_DIGEST_HASH = hashes.SHA256()

# 签名算法：SHA256withRSA (id 0x0101)
SIG_ALG_ID = 0x0101
SIG_PADDING = asym_padding.PKCS1v15()
SIG_HASH = hashes.SHA256()

CHUNK_SIZE = 1024 * 1024  # 1 MB


def load_key_and_cert():
    with open(KEY_PEM, 'rb') as f:
        data = f.read()
    key = serialization.load_pem_private_key(data, password=None)
    cert = x509.load_pem_x509_certificate(data)
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    pub_key_der = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return key, cert_der, pub_key_der


def uint32_bytes(val: int) -> bytes:
    return struct.pack('<I', val)


def uint64_bytes(val: int) -> bytes:
    return struct.pack('<Q', val)


def length_prefixed(data: bytes) -> bytes:
    return uint32_bytes(len(data)) + data


def compute_content_digest(zip_content: bytes, cd_eocd: bytes) -> bytes:
    """
    计算 v2 content digest。
    格式：SHA256( len(zip_content) || chunks_digest(zip_content) || len(cd_eocd) || chunks_digest(cd_eocd) )
    """
    def chunks_digest(data: bytes) -> bytes:
        h = hashlib.sha256()
        for i in range(0, len(data), CHUNK_SIZE):
            chunk = data[i:i + CHUNK_SIZE]
            h.update(hashlib.sha256(chunk).digest())
        return h.digest()

    digest_data = (
        uint64_bytes(len(zip_content)) +
        chunks_digest(zip_content) +
        uint64_bytes(len(cd_eocd)) +
        chunks_digest(cd_eocd)
    )
    return hashlib.sha256(digest_data).digest()


def build_signed_data(content_digest: bytes, cert_der: bytes) -> bytes:
    """构建 signer 的 signed data 部分"""
    # digests
    digest_entry = (
        uint32_bytes(CONTENT_DIGEST_ALG_ID) +
        length_prefixed(content_digest)
    )
    digests = length_prefixed(digest_entry)

    # certificates
    certificates = length_prefixed(cert_der)

    # attributes: min/max SDK version stripping protection (API 28+)
    # attribute value: minSdk(uint32) + maxSdk(uint32)
    attr_value = uint32_bytes(24) + uint32_bytes(0x7FFFFFFF)
    attribute = uint32_bytes(STRIPPING_PROTECTION_ATTR_ID) + length_prefixed(attr_value)
    attributes = length_prefixed(attribute)

    signed_data = (
        length_prefixed(digests) +
        length_prefixed(certificates) +
        length_prefixed(attributes)
    )
    return signed_data


def build_signer(signed_data: bytes, signature: bytes, pub_key_der: bytes) -> bytes:
    """构建一个 signer 块"""
    signatures = (
        uint32_bytes(SIG_ALG_ID) +
        length_prefixed(signature)
    )
    signatures = length_prefixed(signatures)

    signer = (
        length_prefixed(signed_data) +
        length_prefixed(signatures) +
        length_prefixed(pub_key_der)
    )
    return length_prefixed(signer)


def build_apk_signing_block(signers: bytes) -> bytes:
    """构建完整的 APK Signing Block"""
    # v2 id-value pair
    v2_value = length_prefixed(signers)
    id_value = uint32_bytes(SIG_V2_BLOCK_ID) + v2_value
    id_value_with_len = length_prefixed(id_value)

    # size 字段 = 两个 size 字段之间的字节数 = id-value pairs 长度 + 第二个 size 字段长度
    size_field = len(id_value_with_len) + 8
    return (
        uint64_bytes(size_field) +
        id_value_with_len +
        uint64_bytes(size_field) +
        b'APK Sig Block 42'
    )


def sign_apk_v2():
    key, cert_der, pub_key_der = load_key_and_cert()

    with open(SIGNED_V1_APK, 'rb') as f:
        apk_data = f.read()

    # 找到 EOCD
    eocd_offset = apk_data.rfind(b'PK\x05\x06')
    if eocd_offset == -1:
        raise ValueError("EOCD not found")

    eocd = apk_data[eocd_offset:]
    if len(eocd) < 22:
        raise ValueError("Invalid EOCD")

    cd_start = struct.unpack('<I', eocd[16:20])[0]
    zip_content = apk_data[:cd_start]
    cd_eocd = apk_data[cd_start:]

    # 计算 content digest
    content_digest = compute_content_digest(zip_content, cd_eocd)

    # 构建 signed data 并签名
    signed_data = build_signed_data(content_digest, cert_der)
    signature = key.sign(signed_data, SIG_PADDING, SIG_HASH)

    # 构建 signer
    signer = build_signer(signed_data, signature, pub_key_der)
    signers = length_prefixed(signer)

    # 构建 signing block
    signing_block = build_apk_signing_block(signers)

    # 更新 EOCD 中的 central directory 偏移
    new_cd_start = len(zip_content) + len(signing_block)
    new_eocd = eocd[:16] + struct.pack('<I', new_cd_start) + eocd[20:]

    # 组装新 APK
    new_apk = zip_content + signing_block + cd_eocd[:-len(eocd)] + new_eocd

    with open(OUTPUT_APK, 'wb') as f:
        f.write(new_apk)

    print(f"v2 签名完成: {OUTPUT_APK}")
    print(f"大小: {len(new_apk)} bytes")
    print(f"签名块大小: {len(signing_block)} bytes")


if __name__ == '__main__':
    sign_apk_v2()
