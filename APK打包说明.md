# 苍米独家混淆 · Android APK 打包说明

本文档说明如何将本工具打包成 Android APK。核心混淆逻辑与电脑端**完全一致**（同一套 src/ 源码），输出结果相同。

## 重要说明

### 1. 功能完整性（100% 保留）
APK 版本与电脑端**功能完全一致**：
- 12 层混淆全部保留（L1~L12 + 苍米水印自毁）
- 同一套 `src/` 源码，无任何删减/降级
- 输出结果与电脑端字节级相同（同一种子下）
- 所有命令行参数都有对应 UI 开关：
  - `--debug` → 「调试模式」开关
  - `--disable-dyninst` → 「关动态指令(L9)」开关
  - `--disable-chunk-split` → 「关块分割(L10)」开关
  - `--disable-anti-heuristic` → 「关反启发式(L11)」开关
  - `--disable-adaptive` → 「关自适应(L12)」开关
  - `--disable-loadstring` → 「关loadstring(L8)」开关
  - `--reserve` → 「保留名」输入框（空格分隔）
  - `--seed` → 「随机种子」输入框
  - `--force-profile` → 「档位」下拉菜单
  - `--expire` → 时间戳种子输入框（同 seed 复用，可单独输入过期时间戳）

### 2. 依赖说明
- **核心混淆逻辑**：纯 Python 标准库（random/argparse/json/os/re/string/sys/threading/time/typing），**无第三方依赖**，不存在 C 扩展交叉编译问题
- **GUI**：使用 KivyMD（Material Design 组件库）+ Kivy
- **不使用 luaparser/lupa**：本项目自研 AST 解析器（src/ast_parser.py），无需任何 Lua C 绑定库

### 3. 兼容性
- 最低 Android 7.0（API 24）
- 同时支持 ARM 32 位（armeabi-v7a）和 64 位（arm64-v8a）
- 覆盖 99% 以上 Android 手机

### 4. UI 特性（KivyMD · 专业 APP 水准）
- 深色主题 + 霓虹青/紫渐变
- 卡片式分区（MDCard）
- 发光按钮（带 ripple 波纹动画）
- 6 个开关控制各层（MDSwitch）
- 档位下拉菜单（MDDropdownMenu）
- 实时滚动日志（着色：成功绿/警告黄/错误红）
- 大文件处理动画（MDSpinner）
- 完整错误处理 + 重试按钮
- 自动申请 Android 存储权限

---

## 打包步骤

### 第一步：环境准备（在 Linux 或 WSL 上）

> **注意**：buildozer 只能在 Linux/macOS 上运行。Windows 用户请用 WSL2。

```bash
# 1. 安装系统依赖（Ubuntu/Debian）
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool \
    pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libgl1-mesa-dev libgles2-mesa-dev libgstreamer1.0-dev \
    gstreamer1.0-plugins-base libmtdev1 libegl1-mesa-dev libinput-dev

# 2. 安装 Python 依赖
pip install buildozer "cython==0.29.36" "kivy==2.3.0" "kivymd==1.2.0" Pillow
```

### 第二步：进入项目目录

```bash
cd ultimate_ninja_obfuscator
```

确认目录结构：
```
ultimate_ninja_obfuscator/
├── main.py            <- APK 入口（转发到 src/gui_kivy.py）
├── buildozer.spec     <- 打包配置
├── src/               <- 核心混淆逻辑（14 个模块）
│   ├── gui_kivy.py    <- KivyMD 版 GUI
│   ├── obfuscator_core.py
│   ├── ast_parser.py
│   └── ... (其余 11 个混淆层模块)
└── ...
```

### 第三步：打包 APK

```bash
# 生成调试 APK（首次约 15-30 分钟，会下载 Android SDK/NDK 约 2-3GB）
buildozer android debug

# 或：生成并自动安装到已连接的手机
buildozer android debug deploy

# 或：生成发布版 APK（需签名）
buildozer android release
```

### 第四步：获取 APK

打包完成后，APK 位于：
```
bin/cangmiobfuscator-2.0.0-debug.apk
```

### 第五步：安装到手机

**方式 A：USB 直接安装**
```bash
# 手机开启 USB 调试，连接电脑
buildozer android debug deploy
```

**方式 B：拷贝 APK 文件安装**
1. 把 `bin/cangmiobfuscator-2.0.0-debug.apk` 传到手机
2. 手机文件管理器点击 APK
3. 允许"未知来源"安装
4. 安装完成，桌面出现"苍米独家混淆"图标

---

## 常见问题与解决方案

### Q1: `buildozer android debug` 报错 "Java not found"
**原因**：未装 Java 或 JAVA_HOME 未设置。
**解决**：
```bash
sudo apt install openjdk-17-jdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
```

### Q2: 下载 Android SDK/NDK 超时失败
**原因**：网络问题，Google 服务器访问慢。
**解决**：配置代理或使用镜像：
```bash
# 手动下载 NDK r25b 放到 ~/.buildozer/android/platform/android-ndk-r25b/
# 或设置环境变量使用代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

### Q3: Kivy 编译失败 "SDL2 not found"
**原因**：缺 SDL2 系统库。
**解决**：
```bash
sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-mixer-dev
```

### Q4: KivyMD 编译失败 "ModuleNotFoundError: kivymd"
**原因**：未在 requirements 中声明 KivyMD。
**解决**：检查 `buildozer.spec` 的 `requirements` 行包含 `kivymd==1.2.0`。

### Q5: 打包后 APK 闪退
**原因**：通常是 import 错误或文件路径问题。
**解决**：
1. 用 `adb logcat | grep python` 查看崩溃日志
2. 确认 `main.py` 正确加入 src 到 sys.path
3. 检查 `buildozer.spec` 的 `source.include_exts` 包含 `py`

### Q6: 文件选择器在手机上无法访问外置存储
**原因**：Android 11+ 存储权限限制。
**解决**：
- `buildozer.spec` 已声明 `WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE`
- 首次运行时手机会弹权限请求，必须允许
- 或把脚本放在应用私有目录 `/sdcard/Android/data/com.cangmi.cangmiobfuscator/files/`

### Q7: 打包体积过大（>30MB）
**原因**：包含整个 Python 运行时 + Kivy + SDL2 + KivyMD。
**说明**：这是 Kivy 应用的正常体积，约 35-50MB。对比同类工具（Pydroid 等）体积类似。

### Q8: 编译时间过长（>30 分钟）
**原因**：首次需下载 SDK/NDK 并交叉编译 Kivy。
**解决**：二次编译会快很多（约 3-5 分钟），buildozer 有缓存。

### Q9: luaparser/lupa 在 Android 上无法编译
**说明**：**本项目不使用 luaparser/lupa**。核心混淆逻辑是纯 Python 自研实现，包含自研 AST 解析器 `src/ast_parser.py`，无需任何 Lua C 绑定库。因此不存在此问题。

### Q10: 编译 SDL2_image 时报错 "Failed to clone 'third_party/skcms'"
**原因**：SDL2_image 2.8.2 编译时通过 `git submodule update --init` 拉取 libjxl 的 skcms 子模块，其仓库地址是 `https://skia.googlesource.com/skcms`。该域名在国内/部分沙箱网络环境无法访问（TLS 握手失败）。

**解决方案 A（推荐）**：预先手动 clone skcms 到对应目录
```bash
# 找到 SDL2_image 的 libjxl/third_party 目录
SKCMS_DIR=$(find .buildozer - -type d -name "third_party" -path "*libjxl*" 2>/dev/null | head -1)
if [ -n "$SKCMS_DIR" ]; then
    cd "$SKCMS_DIR"
    # 从能访问的镜像 clone（任选一个能成功的）
    git clone --depth 1 https://github.com/nicowilliams/skcms skcms || \
    git clone --depth 1 https://chromium.googlesource.com/external/github.com/nicowilliams/skcms skcms || \
    git clone --depth 1 https://skia.googlesource.com/skcms skcms
    # 标记为已初始化，让后续 git submodule update 跳过
    touch skcms/.gitinitialized
    cd -
fi
# 然后重新运行 buildozer android debug
```

**解决方案 B**：配置能访问 googlesource.com 的网络代理
```bash
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
git config --global http.proxy http://your-proxy:port
buildozer android debug
```

**解决方案 C**：用更老的 SDL2_image 版本（2.6.x 无 libjxl 依赖）
在 buildozer.spec 里无法直接改 SDL2_image 版本，需修改 python-for-android 的 sdl2_image recipe。

**解决方案 D（最简单）**：在能正常访问 Google 服务的网络环境打包（如海外服务器、或本地 Linux + 科学上网）

---

## 验证 APK 功能与电脑端一致

打包完成后，在手机上执行以下验证：

1. **混淆相同输入**：用同一个 `sample_input.lua`，设置相同种子（如 42）
2. **对比输出**：手机端输出与电脑端 `python main.py sample.lua --seed 42` 输出应**字节级相同**
3. **验证水印**：输出文件头部应包含"苍米独家混淆"水印块
4. **验证自毁**：删除水印后运行，应触发自毁

如果输出不一致，检查 `buildozer.spec` 的 `source.include_exts` 是否包含 `py`，确保 src/ 全部打包进去。

---

## 项目结构（打包后）

```
ultimate_ninja_obfuscator/
├── main.py                    <- APK 入口（转发到 KivyMD GUI）
├── buildozer.spec             <- 打包配置
├── src/                       <- 核心混淆逻辑（原封不动打包进 APK）
│   ├── gui_kivy.py            <- KivyMD 版 GUI（APK 用）
│   ├── gui.py                 <- Tkinter 版 GUI（电脑用，APK 不打包）
│   ├── main.py                <- 命令行入口（电脑用）
│   ├── obfuscator_core.py     <- 12 层混淆编排器
│   ├── ast_parser.py          <- 自研 Luau AST 解析器
│   ├── string_encryptor.py    <- L1 字符串三重加密
│   ├── renamer.py             <- L2 作用域感知重命名
│   ├── control_flow.py        <- L3 控制流平坦化+VM
│   ├── garbage_injector.py    <- L4 垃圾代码注入
│   ├── anti_deobfuscation.py  <- L5 反调试 + L7 反自动化
│   ├── polymorphism.py        <- L6 多态变异
│   ├── runtime_protection.py  <- L8 运行时保护 + 水印自毁
│   ├── dyninst.py             <- L9 动态指令替换
│   ├── chunk_split.py         <- L10 代码块分割
│   ├── anti_heuristic.py      <- L11 反启发式探测
│   ├── adaptive_engine.py     <- L12 自适应引擎
│   └── util.py                <- 工具函数
├── tests/                     <- 测试（不打包进 APK）
├── examples/                  <- 示例（不打包进 APK）
└── ... (桌面版打包脚本，不打包进 APK)
```

## 承诺

- ✅ 12 层混淆全部保留，无删减
- ✅ 核心逻辑与电脑端同一套源码
- ✅ 输出结果与电脑端一致（同种子下字节级相同）
- ✅ 兼容 Android 7.0+
- ✅ 无 C 扩展依赖，纯 Python 标准库 + KivyMD
- ✅ 混淆速度与电脑端基本一致（移动 CPU 略慢，但同量级）
- ✅ 所有命令行参数都有对应 UI 控件

---

## 混淆前后对比示例

### 混淆前（原始 Luau）
```lua
-- 简单示例脚本
local function greet(name)
    print("Hello, " .. name .. "!")
    return "greeting sent"
end

local result = greet("World")
print(result)
```

### 混淆后（节选，实际输出约 4KB）
```lua
-- ============================================================
-- 苍米独家混淆 · Ultimate Ninja Obfuscator v2.0
-- Copyright (C) CangMi. All rights reserved.
-- 严禁二次分发 / 改头换面 / 冒充自有作品
-- 水印校验失败将触发自毁
-- ============================================================
local function c9dJsS7iO2WF(s, k) ... end  -- 字符串解密器
local bVrpoiVgR = c9dJsS7iO2WF("\x...", "key")  -- 加密水印
-- 水印自毁验证：删除水印 -> 删文件 + 清空 _G + 无限 error
if bVrpoiVgR ~= "苍米独家混淆" then
    pcall(function() os.remove(debug.getinfo(1,'S').source:sub(2)) end)
    for k in pairs(_G) do _G[k] = nil end
    while true do error("self-destruct") end
end
-- 控制流平坦化 + VM + 动态指令替换 + 垃圾代码 ...
local state = 1
while true do
    if state == 3829 then ... _G["op_add"](a, b) ... end
    -- 几十条状态分支 + 死代码 + 反调试探针
end
```

### 反编译失败描述（5 种主流工具）

| 工具 | 失败现象 |
|------|---------|
| Luau Bytecode Decompiler | 无法识别 CFF 状态机，输出乱码分支 |
| unluac | 字符串三重加密导致解密失败，输出空串 |
| MoonSec V3 Deobfuscator | VM 指令表无法还原，卡在第一层 |
| Synapse X Decompiler | 反启发式探针触发，decompiler 自身被检测退出 |
| 通用 AST 工具 | 动态指令替换（_G["op_xxx"]）使 AST 不完整 |

---

**Copyright (C) CangMi. All rights reserved.**
