# -*- coding: utf-8 -*-
"""
gui.py
======
苍米独家混淆 · Ultimate Ninja Obfuscator —— 现代化暗色图形界面。

特性：
- 自定义暗色主题（深紫黑 + 青色高亮），无系统默认丑陋风格
- 卡片式分区布局，圆角 + 阴影感
- 大号主操作按钮，渐变高亮
- 实时日志区（等宽字体，带时间戳着色）
- 状态栏显示版本/水印/版权
- 双击 启动.bat 或运行 `python src/gui.py` 即可打开
"""

from __future__ import annotations
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

# 确保能 import 同目录下的模块
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from obfuscator_core import obfuscate

# ============================================================================
# 主题配色（暗色系 · 苍米独家）
# ============================================================================
class Theme:
    BG          = "#0F1117"   # 主背景（近黑深蓝）
    BG_CARD     = "#1A1D2A"   # 卡片背景
    BG_INPUT    = "#0A0C12"   # 输入框背景
    BG_HOVER    = "#232736"   # 悬停高亮
    BORDER      = "#2A2F3F"   # 边框
    ACCENT      = "#00E5FF"   # 青色主强调（按钮/标题）
    ACCENT_2    = "#7B61FF"   # 紫色次强调（渐变）
    ACCENT_DIM  = "#00B8CC"   # 暗青
    TEXT        = "#E8EAF0"   # 主文本
    TEXT_DIM    = "#8B92A8"   # 次文本
    TEXT_MUTED  = "#5A6178"   # 弱文本
    OK          = "#4ADE80"   # 成功绿
    WARN        = "#FBBF24"   # 警告黄
    ERR         = "#F87171"   # 错误红
    LOG_INFO    = "#9CA3AF"
    LOG_OK      = "#4ADE80"
    LOG_ERR     = "#F87171"
    LOG_TIME    = "#5A6178"
    LOG_HL      = "#00E5FF"

APP_TITLE = "苍米独家混淆 · Ultimate Ninja Obfuscator"
APP_VERSION = "v2.0 (12-Layer)"


class ObfuscatorGUI:
    """现代化暗色图形界面主类。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x720")
        self.root.minsize(820, 660)
        self.root.configure(bg=Theme.BG)

        # 状态变量
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.seed_var = tk.StringVar()
        self.reserve_var = tk.StringVar()
        self.debug_var = tk.BooleanVar(value=False)
        self.profile_var = tk.StringVar(value="自动")
        self.disable_dyninst_var = tk.BooleanVar(value=False)
        self.disable_chunksplit_var = tk.BooleanVar(value=False)
        self.disable_antiheur_var = tk.BooleanVar(value=False)
        self.disable_loadstring_var = tk.BooleanVar(value=False)
        self.result_code = ""
        self._running = False

        self._setup_window()
        self._build_ui()

    # ------------------------------------------------------------------
    # 窗口设置
    # ------------------------------------------------------------------
    def _setup_window(self):
        # 居中显示
        self.root.update_idletasks()
        w, h = 900, 720
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # 尝试设置任务栏图标（Windows）
        try:
            if sys.platform.startswith("win"):
                self.root.iconbitmap(default="")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ===== 顶部标题栏 =====
        header = tk.Frame(self.root, bg=Theme.BG, height=70)
        header.pack(fill=tk.X, padx=20, pady=(16, 8))
        header.pack_propagate(False)

        # 标题
        title_frame = tk.Frame(header, bg=Theme.BG)
        title_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(title_frame, text="⚡", font=("Segoe UI", 22),
                 bg=Theme.BG, fg=Theme.ACCENT).pack(side=tk.LEFT)
        tk.Label(title_frame, text="苍米独家混淆",
                 font=("Segoe UI Semibold", 20, "bold"),
                 bg=Theme.BG, fg=Theme.TEXT).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(title_frame, text="Ultimate Ninja Obfuscator",
                 font=("Segoe UI", 11), bg=Theme.BG,
                 fg=Theme.TEXT_DIM).pack(side=tk.LEFT, padx=(0, 12))

        # 版本徽章
        ver_bg = tk.Frame(title_frame, bg=Theme.ACCENT, height=22)
        ver_bg.pack(side=tk.LEFT, pady=10)
        tk.Label(ver_bg, text=f" {APP_VERSION} ",
                 font=("Segoe UI", 9, "bold"), bg=Theme.ACCENT,
                 fg=Theme.BG).pack(pady=1, padx=2)

        # 右侧水印
        wm_frame = tk.Frame(header, bg=Theme.BG)
        wm_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(wm_frame, text="苍米独家混淆", font=("Segoe UI", 10, "bold"),
                 bg=Theme.BG, fg=Theme.ACCENT_2).pack(side=tk.RIGHT)
        tk.Label(wm_frame, text="Copyright © CangMi",
                 font=("Segoe UI", 8), bg=Theme.BG,
                 fg=Theme.TEXT_MUTED).pack(side=tk.RIGHT, pady=(0, 2))

        # 主滚动容器
        main = tk.Frame(self.root, bg=Theme.BG)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # ===== ① 输入卡片 =====
        in_card = self._card(main, "①  选择输入文件")
        in_row = tk.Frame(in_card, bg=Theme.BG_CARD)
        in_row.pack(fill=tk.X, padx=14, pady=(6, 12))
        self._entry(in_row, self.input_path)
        self._btn(in_row, "浏览…", self._browse_input, side=tk.RIGHT, padx=(8, 0))

        # ===== ② 输出卡片 =====
        out_card = self._card(main, "②  选择输出位置（留空则自动命名）")
        out_row = tk.Frame(out_card, bg=Theme.BG_CARD)
        out_row.pack(fill=tk.X, padx=14, pady=(6, 12))
        self._entry(out_row, self.output_path)
        self._btn(out_row, "浏览…", self._browse_output, side=tk.RIGHT, padx=(8, 0))

        # ===== ③ 选项卡片 =====
        opt_card = self._card(main, "③  混淆选项（可选）")
        opt_body = tk.Frame(opt_card, bg=Theme.BG_CARD)
        opt_body.pack(fill=tk.X, padx=14, pady=(6, 12))

        # 第一行：种子 + 保留名
        row1 = tk.Frame(opt_body, bg=Theme.BG_CARD)
        row1.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row1, text="随机种子", font=("Segoe UI", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(side=tk.LEFT)
        self._entry(row1, self.seed_var, width=10, padx=(6, 18))
        tk.Label(row1, text="保留名(空格分隔)", font=("Segoe UI", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(side=tk.LEFT)
        self._entry(row1, self.reserve_var, expand=True, padx=(6, 0))

        # 第二行：档位 + 复选框
        row2 = tk.Frame(opt_body, bg=Theme.BG_CARD)
        row2.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row2, text="档位", font=("Segoe UI", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(side=tk.LEFT)
        self._combo(row2, padx=(6, 18))
        self._check(row2, "调试模式", self.debug_var)
        self._check(row2, "关动态指令", self.disable_dyninst_var)
        self._check(row2, "关块分割", self.disable_chunksplit_var)
        self._check(row2, "关反启发式", self.disable_antiheur_var)
        self._check(row2, "关loadstring", self.disable_loadstring_var)

        # ===== ④ 操作区 =====
        action_card = self._card(main, "④  执行混淆")
        action_body = tk.Frame(action_card, bg=Theme.BG_CARD)
        action_body.pack(fill=tk.X, padx=14, pady=(6, 12))

        # 大号主按钮
        self.btn_run = tk.Button(
            action_body, text="▶  开始混淆",
            font=("Segoe UI Semibold", 13, "bold"),
            bg=Theme.ACCENT, fg=Theme.BG, activebackground=Theme.ACCENT_DIM,
            activeforeground=Theme.BG, relief=tk.FLAT, cursor="hand2",
            bd=0, height=2, command=self._run_obfuscate)
        self.btn_run.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        # 次要按钮
        self._btn(action_body, "复制结果", self._copy_result,
                  side=tk.LEFT, padx=(0, 8), accent=False)
        self._btn(action_body, "打开输出", self._open_output,
                  side=tk.LEFT, accent=False)

        # 进度条（自定义细条）
        self.progress = tk.Frame(action_body, bg=Theme.BORDER, height=2)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._progress_fill = tk.Frame(self.progress, bg=Theme.ACCENT, width=0)
        self._progress_fill.pack(side=tk.LEFT, fill=tk.Y)
        self._progress_animating = False

        # ===== ⑤ 日志区 =====
        log_card = self._card(main, "⑤  混淆结果 / 日志")
        log_body = tk.Frame(log_card, bg=Theme.BG_INPUT)
        log_body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 12))

        self.log_text = tk.Text(
            log_body, wrap=tk.NONE, font=("Consolas", 10),
            bg=Theme.BG_INPUT, fg=Theme.LOG_INFO, relief=tk.FLAT, bd=0,
            insertbackground=Theme.ACCENT, selectbackground=Theme.ACCENT_2,
            padx=10, pady=10, state=tk.DISABLED)
        log_scroll_y = tk.Scrollbar(log_body, command=self.log_text.yview,
                                    bg=Theme.BG_CARD, troughcolor=Theme.BG_INPUT,
                                    bd=0, width=10)
        log_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(yscrollcommand=log_scroll_y.set)

        # 日志着色 tag
        self.log_text.tag_config("time", foreground=Theme.LOG_TIME)
        self.log_text.tag_config("info", foreground=Theme.LOG_INFO)
        self.log_text.tag_config("ok", foreground=Theme.LOG_OK)
        self.log_text.tag_config("err", foreground=Theme.LOG_ERR)
        self.log_text.tag_config("hl", foreground=Theme.LOG_HL)

        # 底部状态栏
        status = tk.Frame(self.root, bg=Theme.BG_CARD, height=26)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        status.pack_propagate(False)
        tk.Label(status, text=f"  {APP_VERSION}",
                 font=("Segoe UI", 9), bg=Theme.BG_CARD,
                 fg=Theme.TEXT_MUTED).pack(side=tk.LEFT, pady=3)
        tk.Label(status, text="苍米独家混淆 · 严禁二次分发 · Copyright © CangMi",
                 font=("Segoe UI", 9), bg=Theme.BG_CARD,
                 fg=Theme.ACCENT_2).pack(side=tk.RIGHT, pady=3, padx=12)

        # 欢迎日志
        self._log("欢迎使用 苍米独家混淆 · Ultimate Ninja Obfuscator", tag="hl")
        self._log(f"版本 {APP_VERSION} · 12 层混淆 · 含水印自毁保护", tag="info")
        self._log("操作：选择输入 → 设置输出 → 点击「开始混淆」", tag="info")
        self._log("")

    # ------------------------------------------------------------------
    # UI 组件工厂
    # ------------------------------------------------------------------
    def _card(self, parent, title):
        """带标题的圆角卡片容器。"""
        wrap = tk.Frame(parent, bg=Theme.BORDER, bd=0)
        wrap.pack(fill=tk.X, pady=(0, 10))
        card = tk.Frame(wrap, bg=Theme.BG_CARD, bd=0)
        card.pack(fill=tk.X, padx=1, pady=1)
        tk.Label(card, text=title, font=("Segoe UI Semibold", 11, "bold"),
                 bg=Theme.BG_CARD, fg=Theme.ACCENT,
                 anchor=tk.W).pack(fill=tk.X, padx=14, pady=(10, 0))
        # 分隔细线
        tk.Frame(card, bg=Theme.BORDER, height=1).pack(
            fill=tk.X, padx=14, pady=(6, 0))
        return card

    def _entry(self, parent, var, width=None, expand=False, padx=0):
        """暗色输入框。"""
        e = tk.Entry(parent, textvariable=var,
                     font=("Segoe UI", 10), bg=Theme.BG_INPUT,
                     fg=Theme.TEXT, insertbackground=Theme.ACCENT,
                     relief=tk.FLAT, bd=0, highlightthickness=1,
                     highlightbackground=Theme.BORDER,
                     highlightcolor=Theme.ACCENT)
        if width:
            e.config(width=width)
            e.pack(side=tk.LEFT, padx=padx, ipady=6)
        else:
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=padx, ipady=6)
        return e

    def _btn(self, parent, text, cmd, side=tk.LEFT, padx=0, accent=False):
        """按钮。accent=True 用青色填充，否则用边框样式。"""
        if accent:
            bg, fg, abg = Theme.ACCENT, Theme.BG, Theme.ACCENT_DIM
        else:
            bg, fg, abg = Theme.BG_CARD, Theme.TEXT, Theme.BG_HOVER
        b = tk.Button(parent, text=text, font=("Segoe UI", 10),
                      bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
                      relief=tk.FLAT, cursor="hand2", bd=0,
                      padx=14, pady=6, command=cmd)
        b.pack(side=side, padx=padx)
        return b

    def _combo(self, parent, padx=0):
        """档位下拉框。"""
        c = tk.OptionMenu(parent, self.profile_var,
                          "自动", "small", "medium", "large")
        c.config(font=("Segoe UI", 10), bg=Theme.BG_INPUT, fg=Theme.TEXT,
                 activebackground=Theme.BG_HOVER, activeforeground=Theme.TEXT,
                 relief=tk.FLAT, bd=0, highlightthickness=1,
                 highlightbackground=Theme.BORDER, highlightcolor=Theme.ACCENT,
                 padx=8, pady=4, cursor="hand2")
        c["menu"].config(bg=Theme.BG_INPUT, fg=Theme.TEXT,
                         activebackground=Theme.ACCENT, activeforeground=Theme.BG,
                         bd=0)
        c.pack(side=tk.LEFT, padx=padx)
        return c

    def _check(self, parent, text, var):
        """复选框。"""
        cb = tk.Checkbutton(parent, text=text, variable=var,
                            font=("Segoe UI", 10), bg=Theme.BG_CARD,
                            fg=Theme.TEXT_DIM, selectcolor=Theme.BG_INPUT,
                            activebackground=Theme.BG_CARD,
                            activeforeground=Theme.ACCENT,
                            bd=0, cursor="hand2", padx=6, pady=2)
        cb.pack(side=tk.LEFT, padx=(0, 8))
        return cb

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _log(self, msg: str, tag: str = "info"):
        self.log_text.config(state=tk.NORMAL)
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] ", tag="time")
        self.log_text.insert(tk.END, str(msg) + "\n", tag=tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    # ------------------------------------------------------------------
    # 文件浏览
    # ------------------------------------------------------------------
    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="选择 Luau 脚本",
            filetypes=[("Lua 文件", "*.lua *.luau"), ("所有文件", "*.*")],
        )
        if path:
            self.input_path.set(path)
            if not self.output_path.get():
                base, _ = os.path.splitext(path)
                self.output_path.set(base + "_obf.lua")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="保存混淆后文件",
            defaultextension=".lua",
            filetypes=[("Lua 文件", "*.lua *.luau"), ("所有文件", "*.*")],
        )
        if path:
            self.output_path.set(path)

    # ------------------------------------------------------------------
    # 结果操作
    # ------------------------------------------------------------------
    def _copy_result(self):
        if not self.result_code:
            messagebox.showinfo("提示", "还没有混淆结果，请先点击「开始混淆」")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.result_code)
        self._log("结果已复制到剪贴板", tag="ok")

    def _open_output(self):
        out = self.output_path.get()
        if not out or not os.path.exists(out):
            messagebox.showinfo("提示", "输出文件不存在，请先混淆")
            return
        import subprocess
        try:
            if sys.platform.startswith("win"):
                os.startfile(out)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out])
            else:
                subprocess.Popen(["xdg-open", out])
        except Exception as e:
            self._log(f"无法打开文件: {e}", tag="err")

    # ------------------------------------------------------------------
    # 进度条动画
    # ------------------------------------------------------------------
    def _start_progress(self):
        self._progress_animating = True
        self._animate_progress()

    def _stop_progress(self):
        self._progress_animating = False
        self._progress_fill.config(width=0)

    def _animate_progress(self):
        if not self._progress_animating:
            return
        cur = self._progress_fill.winfo_width()
        total = self.progress.winfo_width()
        if total <= 1:
            total = 400
        step = max(4, total // 30)
        nxt = cur + step
        if nxt >= total:
            nxt = 0
        self._progress_fill.config(width=nxt)
        self.root.after(40, self._animate_progress)

    # ------------------------------------------------------------------
    # 执行混淆
    # ------------------------------------------------------------------
    def _run_obfuscate(self):
        if self._running:
            return
        in_path = self.input_path.get().strip()
        if not in_path or not os.path.isfile(in_path):
            messagebox.showerror("错误", "请先选择有效的输入文件")
            return

        self._running = True
        self.btn_run.config(state=tk.DISABLED, bg=Theme.TEXT_MUTED,
                            text="混淆中…")
        self._start_progress()
        self._log("")
        self._log("=" * 64, tag="hl")
        self._log(f"开始混淆: {in_path}", tag="info")

        t = threading.Thread(target=self._worker, args=(in_path,), daemon=True)
        t.start()

    def _worker(self, in_path: str):
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                src = f.read()
            self._log(f"输入: {len(src)} 字节, {src.count(chr(10)) + 1} 行",
                      tag="info")

            seed_str = self.seed_var.get().strip()
            seed = int(seed_str) if seed_str.isdigit() else None
            reserve_str = self.reserve_var.get().strip()
            reserve_names = set(reserve_str.split()) if reserve_str else None
            profile = self.profile_var.get()
            force_profile = profile if profile != "自动" else None

            result = obfuscate(
                src=src, seed=seed, debug=self.debug_var.get(),
                reserve_names=reserve_names,
                disable_dyninst=self.disable_dyninst_var.get(),
                disable_chunk_split=self.disable_chunksplit_var.get(),
                disable_anti_heuristic=self.disable_antiheur_var.get(),
                disable_loadstring=self.disable_loadstring_var.get(),
                force_profile=force_profile,
            )

            code = result["code"]
            self.result_code = code

            out_path = self.output_path.get().strip()
            if not out_path:
                base, _ = os.path.splitext(in_path)
                out_path = base + "_obf.lua"
                self.output_path.set(out_path)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)

            ratio = len(code) / max(len(src), 1)
            self._log("混淆成功！", tag="ok")
            self._log(f"输出: {out_path}", tag="ok")
            self._log(f"大小: {len(code)} 字节 (约 {ratio:.1f}x 膨胀)", tag="ok")
            self._log(f"档位: {result['profile'].get('name')}", tag="ok")
            self._log(f"种子: {result['stats'].get('seed')}", tag="ok")
            stats = result["stats"]
            wm = stats.get("L0_watermark", {})
            if wm.get("embedded"):
                self._log("苍米独家水印: 已嵌入 (运行时自毁保护已启用)", tag="hl")
            rp = stats.get("L8_runtime_protection", {})
            if rp.get("watermark"):
                self._log("水印自毁验证: 已激活 (删水印=自毁)", tag="hl")
            if self.debug_var.get():
                self._log(f"[debug] L1 字符串加密: {stats.get('L1_string_encryptor', {})}", tag="info")
                self._log(f"[debug] L2 重命名: {stats.get('L2_renamer', {})}", tag="info")
                self._log(f"[debug] L3 控制流: {stats.get('L3_control_flow', {})}", tag="info")
                self._log(f"[debug] L4 垃圾注入: {stats.get('L4_garbage', {})}", tag="info")
                self._log(f"[debug] L9 动态指令: {stats.get('L9_dyninst', {})}", tag="info")
                self._log(f"[debug] L10 块分割: {stats.get('L10_chunk_split', {})}", tag="info")
                self._log(f"[debug] L11 反启发式: {stats.get('L11_anti_heuristic', {})}", tag="info")

            self._log("")
            self._log("混淆完成！可点击「复制结果」直接粘贴到注入器使用。", tag="ok")

        except Exception as e:
            import traceback
            self._log(f"混淆失败: {e}", tag="err")
            self._log(traceback.format_exc(), tag="err")
        finally:
            self.root.after(0, self._finish)

    def _finish(self):
        self._running = False
        self._stop_progress()
        self.btn_run.config(state=tk.NORMAL, bg=Theme.ACCENT,
                            text="▶  开始混淆")


def main():
    root = tk.Tk()
    app = ObfuscatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
