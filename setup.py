# -*- coding: utf-8 -*-
"""setup.py — Ultimate Ninja Obfuscator 安装脚本。"""
from setuptools import setup

setup(
    name="ultimate-ninja-obfuscator",
    version="1.0.0",
    description="终极·极限·兼容·自适应 Roblox Luau 脚本混淆工具（12 层）",
    long_description=(
        "12-layer Luau script obfuscator targeting 100% compatibility with "
        "Ninja Injector and all mainstream PC/mobile injectors. "
        "Pure-text Luau output (no bytecode/binary blocks). "
        "Pure Python standard library, no third-party dependencies."
    ),
    long_description_content_type="text/markdown",
    python_requires=">=3.7",
    package_dir={"": "src"},
    py_modules=[
        "ast_parser", "util", "string_encryptor", "renamer",
        "control_flow", "garbage_injector", "polymorphism",
        "anti_deobfuscation", "runtime_protection", "dyninst",
        "chunk_split", "anti_heuristic", "adaptive_engine",
        "obfuscator_core", "main",
    ],
    entry_points={
        "console_scripts": [
            "ninja-obf=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Build Tools",
        "Operating System :: OS Independent",
    ],
)
