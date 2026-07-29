# -*- coding: utf-8 -*-
"""
string_encryptor.py
===================
第 1 层：多态字符串加密。

对标 MoonSec V3。每个字符串字面量使用「XOR 密钥 + 随机偏移 + 位翻转」三重
加密，且每个字符串拥有独立的 key / offset / mask，解密函数使用表缓存 + 闭包。

加密流程（每个字节 b）：
    enc = (((b XOR key) + offset) mod 256) XOR mask

解密流程：
    b   = ((enc XOR mask) - offset) mod 256) XOR key

输出仍为纯 Luau 文本：密文以 \\ddd 十进制转义嵌入普通字符串字面量。
"""

from __future__ import annotations
import random
from typing import Optional

from ast_parser import Node, N, transform
from util import (
    NameGenerator, bytes_to_lua_literal, name_node, number_node,
    string_node, call_node,
)


def _encrypt_bytes(data: bytes, key: int, offset: int, mask: int) -> bytes:
    """对字节序列执行三重加密。"""
    out = bytearray(len(data))
    for i, b in enumerate(data):
        v = (b ^ key) & 0xFF
        v = (v + offset) & 0xFF
        v = (v ^ mask) & 0xFF
        out[i] = v
    return bytes(out)


def _build_decrypt_function(dec_name: str, cache_name: str) -> Node:
    """构造解密函数定义的 AST。

    生成的等价 Luau：
        local <cache> = {}
        local function <dec>(data, key, offset, mask)
            local ck = data .. string.char(key, offset, mask)
            local cached = <cache>[ck]
            if cached then return cached end
            local t, n = {}, #data
            for i = 1, n do
                local b = string.byte(data, i)
                b = ((b ~ mask) - offset) % 256
                b = b ~ key
                t[i] = string.char(b)
            end
            local r = table.concat(t)
            <cache>[ck] = r
            return r
        end

    说明：
    - 使用 string.byte / string.char / table.concat，纯标准库，全注入器兼容。
    - 位运算 `~` 在 Luau 中为按位异或，所有目标注入器均支持。
    - 缓存表 <cache> 闭包捕获，避免重复解密同一字符串。
    - 关键：缓存键 ck = data .. string.char(key, offset, mask)，包含全部四个
      参数。因为每个字符串拥有独立的 key/offset/mask，同一 payload 搭配不同
      参数会解密出不同明文；仅以 data 为键会导致缓存冲突（垃圾代码中恰好
      产生同 payload 不同参数的调用时，会返回错误结果）。追加 3 字节参数后，
      不同 (data, key, offset, mask) 元组必产生不同 ck，无冲突可能。
    """
    # string.byte(data, i)
    byte_call = call_node(
        index_node(name_node("string"), string_node("byte")),
        [name_node("data"), name_node("i")],
    )
    # b = ((b ~ mask) - offset) % 256
    b_xor_mask = N("BinOp", op="~", left=name_node("b"), right=name_node("mask"))
    sub_offset = N("BinOp", op="-", left=N("Paren", expr=b_xor_mask),
                   right=name_node("offset"))
    mod_256 = N("BinOp", op="%", left=N("Paren", expr=sub_offset),
                right=number_node(256))
    b_xor_key = N("BinOp", op="~", left=N("Paren", expr=mod_256),
                  right=name_node("key"))
    # string.char(key, offset, mask) —— 3 字节参数后缀
    char_key_call = call_node(
        index_node(name_node("string"), string_node("char")),
        [name_node("key"), name_node("offset"), name_node("mask")],
    )
    # ck = data .. string.char(key, offset, mask)
    ck_expr = N("BinOp", op="..", left=name_node("data"), right=char_key_call)
    body = [
        N("LocalAssign", names=["ck"], exprs=[ck_expr]),
        N("LocalAssign", names=["cached"],
          exprs=[index_node(name_node(cache_name), name_node("ck"))]),
        N("If",
          cond=name_node("cached"),
          body=[N("Return", exprs=[name_node("cached")])],
          elifs=[], else_body=None),
        N("LocalAssign", names=["t", "n"],
          exprs=[N("Table", fields=[]),
                 call_node(index_node(name_node("string"), string_node("len")),
                           [name_node("data")])]),
        N("NumericFor", var="i", start=number_node(1), limit=name_node("n"),
          step=None, body=[
              N("LocalAssign", names=["b"], exprs=[byte_call]),
              N("Assign", targets=[name_node("b")], exprs=[b_xor_key]),
              N("Assign",
                targets=[index_node(name_node("t"), name_node("i"))],
                exprs=[call_node(
                    index_node(name_node("string"), string_node("char")),
                    [name_node("b")])]),
          ]),
        N("LocalAssign", names=["r"],
          exprs=[call_node(
              index_node(name_node("table"), string_node("concat")),
              [name_node("t")])]),
        N("Assign",
          targets=[index_node(name_node(cache_name), name_node("ck"))],
          exprs=[name_node("r")]),
        N("Return", exprs=[name_node("r")]),
    ]
    func = N("Function", params=["data", "key", "offset", "mask"],
             is_vararg=False, body=body)
    return N("LocalFunction", name=dec_name, func=func)


def index_node(obj: Node, key: Node) -> Node:
    """局部快捷构造（避免与 util.index_node 循环导入，此处复刻）。"""
    return N("Index", obj=obj, key=key)


def encrypt_strings(chunk: Node, rng: random.Random,
                    dec_name: Optional[str] = None,
                    reserve_names: Optional[set] = None,
                    skip_min_len: int = 0) -> str:
    """对整棵 AST 的字符串字面量做三重加密。

    参数：
        chunk:       顶层 Chunk 节点（会被原地修改）。
        rng:         随机数发生器（多态层注入）。
        dec_name:    解密函数名；为空则随机生成。
        reserve_names: 需保留原名的名称集合（如用户 --reserve）。
        skip_min_len: 长度 < 该值的字符串跳过（默认 0，全部加密）。

    返回：实际使用的解密函数名（供后续层引用）。
    """
    gen = NameGenerator(rng)
    if dec_name:
        gen.reserve(dec_name)
    dec_name = dec_name or gen.fresh()
    cache_name = gen.fresh()
    reserve_names = reserve_names or set()

    # 是否已注入解密函数标记
    injected = {"v": False}

    def visit(node: Node) -> Node:
        # 跳过标记为不可加密的字符串（如函数声明字段名，gen_funcname 需原值）
        if node.type == "String" and node.attrs.get("_no_encrypt"):
            return node
        # 首次遇到需加密的字符串时，在 Chunk 顶部注入解密函数与缓存表
        if node.type == "String" and not node.attrs.get("_enc_payload"):
            value = node.get("value")
            # 跳过过短字符串（可选）
            if len(value) < skip_min_len:
                return node
            # 跳过被保留的“方法名”类字符串？此处统一加密以最大化混淆。
            data = value.encode("utf-8", errors="surrogatepass")
            key = rng.randint(1, 255)
            offset = rng.randint(1, 255)
            mask = rng.randint(1, 255)
            enc = _encrypt_bytes(data, key, offset, mask)
            payload_literal = bytes_to_lua_literal(enc)
            payload_node = string_node(payload_literal)
            payload_node.attrs["_enc_payload"] = True  # 防止再次加密
            payload_node.attrs["_verbatim"] = True     # 已是完整字面量，禁止二次转义
            # _S(payload, key, offset, mask)
            new_node = call_node(
                name_node(dec_name),
                [payload_node, number_node(key),
                 number_node(offset), number_node(mask)],
            )
            return new_node
        return node

    # 后序变换：在变换过程中，新生成的 payload 字符串不会被再次访问
    transform(chunk, visit)

    # 在 Chunk 顶部插入缓存表与解密函数定义
    body = chunk.get("body")
    cache_decl = N("LocalAssign", names=[cache_name],
                   exprs=[N("Table", fields=[])])
    dec_func = _build_decrypt_function(dec_name, cache_name)
    body.insert(0, dec_func)
    body.insert(0, cache_decl)

    return dec_name
