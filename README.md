# Ultimate Ninja Obfuscator

**终极·极限·兼容·自适应** Roblox Luau 脚本混淆工具（12 层）。

- 纯 Python 标准库实现，**零第三方依赖**（Python 3.7+）。
- 输出为**纯 Luau 文本源码**，不含字节码或二进制块。
- 目标 100% 兼容最新版忍者注入器及 PC/手机端主流注入器。
- 对标并超越 MoonSec V3、Synapse X、ComboSec、Prometheus 等主流混淆工具。

## 快速开始

```bash
# 基本用法
python src/main.py input.lua -o output.lua

# 指定随机种子（可复现）
python src/main.py input.lua -o output.lua --seed 12345

# 调试模式（注入隐蔽日志 + 统计报告到 stderr）
python src/main.py input.lua -o output.lua --debug

# 保留指定名称不被重命名/加密
python src/main.py input.lua -o output.lua --reserve Foo Bar _G

# 时间炸弹（过期后触发误导模式）
python src/main.py input.lua -o output.lua --expire 1735689600

# 单独关闭某层
python src/main.py input.lua -o output.lua --disable-dyninst --disable-chunk-split
```

## 12 层混淆架构

| 层 | 名称 | 对标 | 说明 |
|----|------|------|------|
| L1 | 多态字符串加密 | MoonSec V3 | XOR+偏移+位翻转三重加密，表缓存解密 |
| L2 | 作用域感知重命名 | Synapse X | 词法作用域分析，局部变量/函数/全局名彻底重命名 |
| L3 | 控制流平坦化 + VM | ComboSec | while-true 状态分发器 + 微型字节码解释器 |
| L4 | 死代码注入 | Bill's Obfuscator | 语法正确、语义无害的 do-block 垃圾代码 |
| L5 | 反调试/反篡改 | Synapse X | debug/getfenv/hookfunction 探测，全 pcall 包裹 |
| L6 | 多态诱饵 | — | 诱饵状态机，每次输出不同 |
| L7 | 反自动化反混淆 | — | AST 扰动+字符串拆分+API 动态索引 |
| L8 | 运行时保护 | — | 环境检查+自修改计数器+loadstring 动态加载 |
| L9 | 动态指令替换 | VMProtect | 运算符→`_G["key"]` 函数调用 |
| L10 | 代码块分割重组 | Prometheus | 函数体拆分为匿名块+跳转表分发 |
| L11 | 反启发式探测 | — | 时间差/getinfo/pcall 异常检测 |
| L12 | 自适应引擎 | — | 按脚本行数自动调档，`--debug` 调试模式 |

### 自适应档位

| 档位 | 行数 | VM | DynInst | ChunkSplit | 说明 |
|------|------|----|---------|------------|------|
| small | < 200 | 开 | 20 点 | 20 | 全层拉满 |
| medium | 200-500 | 开 | 10 点 | 10 | 轻度模式 |
| large | > 500 | 关 | 0 | 8 | 性能优先 |

## 兼容性红线

- 纯文本 Luau 输出，无字节码。
- `loadstring` 全工具最多 1 次（L8，带 inline 回退）。
- CFF 状态数 ≤ 50，嵌套深度 = 1。
- 所有可疑调用均 `pcall` 包裹。
- `game`/`workspace` 等环境全局保持直接访问。
- 第 9~12 层均可通过命令行开关单独关闭。

## 项目结构

```
ultimate_ninja_obfuscator/
├── src/
│   ├── main.py              # CLI 入口
│   ├── obfuscator_core.py   # 12 层编排器
│   ├── ast_parser.py        # Luau 词法+语法分析+代码生成
│   ├── util.py              # 公共工具（NameGenerator 等）
│   ├── string_encryptor.py  # L1 多态字符串加密
│   ├── renamer.py           # L2 作用域感知重命名
│   ├── control_flow.py      # L3 控制流平坦化 + VM
│   ├── garbage_injector.py  # L4 死代码注入
│   ├── polymorphism.py      # L6 多态诱饵
│   ├── anti_deobfuscation.py# L5 反调试 + L7 反自动化
│   ├── runtime_protection.py# L8 运行时保护
│   ├── dyninst.py           # L9 动态指令替换
│   ├── chunk_split.py       # L10 代码块分割
│   ├── anti_heuristic.py    # L11 反启发式探测
│   └── adaptive_engine.py   # L12 自适应引擎
├── tests/
│   ├── sample_input.lua     # 基础测试脚本
│   ├── stress_input.lua     # 压力测试脚本
│   ├── run_regression.py    # 基础回归测试
│   └── run_stress.py        # 压力回归测试
├── setup.py
├── requirements.txt
└── README.md
```

## 测试

```bash
# 基础回归（30 seeds）
python tests/run_regression.py --lua lua --seeds 30

# 压力回归（200 seeds，覆盖闭包/OOP/vararg/复杂控制流）
python tests/run_stress.py --lua lua --seeds 200
```

测试策略：对测试脚本用多组 seed 混淆，再用 Lua 5.3 执行，校验输出与原始脚本完全一致。

## 编程接口

```python
import sys; sys.path.insert(0, "src")
from obfuscator_core import obfuscate

result = obfuscate(
    src=source_code,
    seed=42,                    # 可复现
    debug=False,
    reserve_names={"Foo"},      # 保留名
    expire_ts=None,             # 时间炸弹
    disable_dyninst=False,
    disable_chunk_split=False,
    disable_anti_heuristic=False,
    disable_adaptive=False,
    force_profile=None,         # "small"/"medium"/"large"
    disable_loadstring=False,
)

print(result["code"])           # 混淆后 Luau 源码
print(result["stats"])          # 各层统计
print(result["profile"])        # 自适应档位
```
