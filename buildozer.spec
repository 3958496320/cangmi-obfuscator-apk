[app]

# ==============================================================================
# 苍米独家混淆 · Android APK 打包配置 (buildozer.spec)
# ==============================================================================

# 用法：
#   buildozer android debug       # 生成调试 APK
#   buildozer android release     # 生成发布 APK（需签名）
#   buildozer android debug deploy # 生成并安装到连接的手机
# ==============================================================================

# 应用标题（显示在手机桌面图标下）
title = 苍米独家混淆

# 包名（Android 包标识，必须符合 Java 包名规范）
package.name = cangmiobfuscator

# 包域名（与 package.name 组成完整包名 com.cangmi.obfuscator）
package.domain = com.cangmi

# 源码目录（Kivy 入口 main.py 所在目录）
source.dir = .

# 包含的源文件（核心混淆逻辑 + Kivy GUI）
# 注意：src/ 目录会被整体打包进 APK
source.include_exts = py,png,jpg,kv,atlas,txt

# 排除的文件/目录（不打包进 APK）
source.exclude_exts = spec,spec.in,md,bat,pyc,pyo,lua
source.exclude_dirs = tests,examples,build,dist,__pycache__,buildozer_dir,bin
source.exclude_patterns = LICENSE,README*,setup.py,build_exe.py,run.bat,启动.bat,build_exe.bat,一键打包.bat

# 版本号
version = 2.0.1

# 应用需求声明（KivyMD 会自动拉取 Kivy）
# 注意：不包含 Pillow/requests，因为 Pillow 的 SDL2_image 依赖 skcms 子模块
#       需从 skia.googlesource.com 克隆，部分网络环境无法访问。
#       本项目核心混淆逻辑是纯 Python 标准库，不需要 Pillow/requests。
requirements = python3,kivy==2.3.0

# Android 配置 -----------------------------------------------------------

# Android NDK API 版本（兼容 Android 7.0+，API 24 = Android 7.0）
android.api = 31

# Android NDK 版本
android.ndk = 25b

# Android SDK 版本
android.sdk = 30

# 最低 Android 版本（Android 7.0 = API 24）
android.minapi = 24

# 目标 Android 版本
android.target = 31

# 架构（只打 64 位 ARM，节省打包时间和空间；现代手机几乎都是 64 位）
android.archs = arm64-v8a

# 构建工具 ---------------------------------------------------------------

# Python 版本（buildozer 会为 Android 交叉编译）
# 注意：用 3.9 避免 3.14 在 Android 上的兼容问题
python.version = 3.12

# Cython 版本（Kivy 编译需要）
android.cython = 0.29.36

# 全屏模式（False = 显示状态栏）
fullscreen = 0

# 屏幕方向（portrait 竖屏 / landscape 横屏 / sensor 自动）
orientation = portrait

# 应用权限（最小权限集）
# WRITE_EXTERNAL_STORAGE: 读写混淆后的 .lua 文件
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 启动时不要复制应用数据到外部存储（避免文件路径混乱）
android.no-copy-libs = 1

# 是否使用 Android 项目模板的较新版本
android.android_entrypoint = org.kivy.android.PythonActivity

# 日志级别（打包时输出详细日志便于排查）
log_level = 2

# 预构建步骤（无需额外处理，Kivy 自动处理）
# pre-build.command =

# 构建后处理（无需）
# post-build.command =

# 高级配置 ---------------------------------------------------------------

# 不要打包 tkinter（Android 不支持）
# （已在 source.exclude 中排除桌面版 gui.py）

# 启用 ccache 加速二次编译
android.release_artifact = apk

# 应用图标（可选，无则用默认 Kivy 图标）
# icon.filename = %(source.dir)s/icon.png

# 应用名称（桌面图标下文字）
launcher_name = 苍米混淆

# 混淆 ProGuard（关闭，避免误删反射调用）
# android.add_compile_options = -dontwarn

# 自动接受 SDK license（避免交互卡住）
android.accept_sdk_license = True

# ==============================================================================
# 构建后自动操作
# ==============================================================================

# 构建完成后拷贝 APK 到项目根目录 bin/
# buildozer 默认会输出到 bin/*.apk

# 调试构建配置
[buildozer]
log_level = 2
# 跳过 root 用户警告（沙箱环境必须以 root 运行）
warn_on_root = 0

