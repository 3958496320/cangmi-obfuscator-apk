# -*- coding: utf-8 -*-
"""
gui_kivy.py - 苍米独家混淆 GUI（纯 Kivy 极简稳定版）
延迟导入混淆核心，避免启动时崩溃
"""
import os, sys, threading

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# === 心跳日志 ===
def _beat(msg):
    try:
        with open("/sdcard/cangmi_heartbeat.log", "a", encoding="utf-8") as f:
            f.write(f"[GUI] {msg}\n")
    except:
        pass

_beat("gui_kivy.py loading")

# === Kivy 配置（必须在导入其他 Kivy 模块前设置）===
try:
    from kivy.config import Config
    Config.set('kivy', 'exit_on_escape', '0')
    Config.set('graphics', 'resizable', '0')
    _beat("Config OK")
except Exception as e:
    _beat(f"Config FAIL: {e}")

# === Kivy 导入（逐个导入，每个都 try/except）===
_beat("Importing Kivy modules...")

try:
    from kivy.app import App
    _beat("App OK")
except Exception as e:
    _beat(f"App FAIL: {e}")

try:
    from kivy.clock import Clock
    _beat("Clock OK")
except Exception as e:
    _beat(f"Clock FAIL: {e}")

try:
    from kivy.core.window import Window
    _beat("Window OK")
except Exception as e:
    _beat(f"Window FAIL: {e}")

try:
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.textinput import TextInput
    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.popup import Popup
    _beat("Basic widgets OK")
except Exception as e:
    _beat(f"Basic widgets FAIL: {e}")

try:
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.togglebutton import ToggleButton
    from kivy.uix.spinner import Spinner
    from kivy.uix.progressbar import ProgressBar
    _beat("Advanced widgets OK")
except Exception as e:
    _beat(f"Advanced widgets FAIL: {e}")

try:
    from kivy.core.clipboard import Clipboard
    _beat("Clipboard OK")
except Exception as e:
    _beat(f"Clipboard FAIL: {e}")

# ============================================================================
# 主题配色
# ============================================================================
BG       = (0.04, 0.055, 0.102, 1)
BG_CARD  = (0.078, 0.094, 0.165, 1)
ACCENT   = (0.0, 0.9, 1.0, 1)
ACCENT_2 = (0.48, 0.38, 1.0, 1)
TEXT     = (0.91, 0.918, 0.941, 1)
TEXT_DIM = (0.545, 0.573, 0.659, 1)
OK       = (0.29, 0.87, 0.5, 1)
ERR      = (0.97, 0.44, 0.44, 1)

APP_TITLE = "苍米独家混淆"
APP_VERSION = "v2.0.1 (12-Layer)"

# 延迟导入混淆核心
_obfuscate = None
_CORE_ERR = ""

def _get_obfuscate():
    global _obfuscate, _CORE_ERR
    if _obfuscate is not None:
        return _obfuscate
    try:
        _beat("Lazy importing obfuscator_core...")
        from obfuscator_core import obfuscate
        _obfuscate = obfuscate
        _beat("obfuscator_core OK")
        return _obfuscate
    except Exception as e:
        import traceback
        _CORE_ERR = traceback.format_exc()
        _beat(f"obfuscator_core FAIL: {e}")
        return None


class CangMiApp(App):
    def build(self):
        _beat("CangMiApp.build() called")
        try:
            Window.clearcolor = BG
            self.title = f"{APP_TITLE} {APP_VERSION}"
            self._running = False
            return self._build_ui()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            _beat(f"build() FAIL: {err}")
            return self._error_ui(err)

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=8, spacing=6)

        # 标题
        title = Label(
            text=f"[b]{APP_TITLE}[/b]",
            markup=True, color=ACCENT,
            font_size='20sp', bold=True,
            size_hint_y=None, height=44
        )
        root.add_widget(title)

        subtitle = Label(
            text=f"{APP_VERSION}",
            color=TEXT_DIM, font_size='10sp',
            size_hint_y=None, height=18
        )
        root.add_widget(subtitle)

        # 输入区
        in_label = Label(
            text="输入 Luau 脚本",
            color=ACCENT_2, font_size='12sp', bold=True,
            size_hint_y=None, height=24,
            halign='left'
        )
        in_label.bind(size=in_label.setter('text_size'))
        root.add_widget(in_label)

        self.input_text = TextInput(
            hint_text="在此粘贴要混淆的代码...",
            multiline=True,
            size_hint_y=0.35,
            font_size='12sp',
            background_color=BG_CARD,
            foreground_color=TEXT,
            cursor_color=ACCENT
        )
        root.add_widget(self.input_text)

        # 按钮行
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None,
                            height=38, spacing=5)
        self.btn_file = Button(
            text="选择文件",
            size_hint_x=0.5,
            background_color=ACCENT_2,
            color=(0, 0, 0, 1)
        )
        self.btn_file.bind(on_release=self._choose_file)
        btn_row.add_widget(self.btn_file)

        self.btn_clear = Button(
            text="清空",
            size_hint_x=0.5,
            background_color=(0.3, 0.3, 0.35, 1),
            color=TEXT
        )
        self.btn_clear.bind(on_release=lambda x: setattr(self.input_text, 'text', ''))
        btn_row.add_widget(self.btn_clear)
        root.add_widget(btn_row)

        # 选项区
        opt_label = Label(
            text="混淆选项",
            color=ACCENT_2, font_size='12sp', bold=True,
            size_hint_y=None, height=24,
            halign='left'
        )
        opt_label.bind(size=opt_label.setter('text_size'))
        root.add_widget(opt_label)

        opt_grid = GridLayout(cols=3, size_hint_y=None, height=50, spacing=2)
        self.opts = {}
        for name in ["调试模式", "禁用动态指令", "禁用分块",
                     "禁用反启发", "禁用自适应", "保留水印"]:
            tb = ToggleButton(
                text=name, font_size='9sp',
                color=TEXT,
                background_color=BG_CARD
            )
            if name == "保留水印":
                tb.state = 'down'
            self.opts[name] = tb
            opt_grid.add_widget(tb)
        root.add_widget(opt_grid)

        # 混淆按钮
        self.btn_run = Button(
            text="开始混淆（12 层）",
            size_hint_y=None, height=50,
            background_color=ACCENT,
            color=(0, 0, 0, 1),
            font_size='15sp', bold=True
        )
        self.btn_run.bind(on_release=self._on_run)
        root.add_widget(self.btn_run)

        # 进度条
        self.progress = ProgressBar(
            size_hint_y=None, height=12,
            color=ACCENT
        )
        root.add_widget(self.progress)

        # 输出区
        out_label = Label(
            text="输出结果",
            color=ACCENT_2, font_size='12sp', bold=True,
            size_hint_y=None, height=24,
            halign='left'
        )
        out_label.bind(size=out_label.setter('text_size'))
        root.add_widget(out_label)

        self.output_text = TextInput(
            hint_text="混淆后的代码将显示在这里...",
            multiline=True, readonly=True,
            size_hint_y=0.3,
            font_size='11sp',
            background_color=BG_CARD,
            foreground_color=OK
        )
        root.add_widget(self.output_text)

        # 操作按钮
        act_row = BoxLayout(orientation='horizontal', size_hint_y=None,
                            height=38, spacing=5)
        self.btn_copy = Button(
            text="复制",
            size_hint_x=0.5,
            background_color=ACCENT_2,
            color=(0, 0, 0, 1)
        )
        self.btn_copy.bind(on_release=self._copy_result)
        act_row.add_widget(self.btn_copy)

        self.btn_save = Button(
            text="保存",
            size_hint_x=0.5,
            background_color=(0.2, 0.7, 0.4, 1),
            color=(0, 0, 0, 1)
        )
        self.btn_save.bind(on_release=self._save_result)
        act_row.add_widget(self.btn_save)
        root.add_widget(act_row)

        # 状态
        self.status = Label(
            text="就绪",
            color=TEXT_DIM, font_size='10sp',
            size_hint_y=None, height=18
        )
        root.add_widget(self.status)

        _beat("_build_ui() done")
        return root

    def _error_ui(self, err):
        root = BoxLayout(orientation='vertical', padding=20)
        sv = ScrollView(size_hint=(1, 1))
        lbl = Label(
            text=f"[b]启动失败[/b]\n\n{err}",
            markup=True, size_hint_y=None, valign='top',
            font_size='11sp', color=ERR
        )
        lbl.bind(texture_size=lbl.setter('size'))
        sv.add_widget(lbl)
        root.add_widget(sv)
        return root

    def _choose_file(self, _):
        try:
            from kivy.uix.filechooser import FileChooserListView
            content = BoxLayout(orientation='vertical')
            fc = FileChooserListView(path='/sdcard', filters=['*.lua', '*.txt'])
            content.add_widget(fc)

            btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=46)
            btn_ok = Button(text="确定", background_color=ACCENT, color=(0, 0, 0, 1))
            btn_cancel = Button(text="取消", background_color=ERR, color=(0, 0, 0, 1))
            btn_box.add_widget(btn_ok)
            btn_box.add_widget(btn_cancel)
            content.add_widget(btn_box)

            popup = Popup(title="选择文件", content=content, size_hint=(0.95, 0.9))
            btn_ok.bind(on_release=lambda x: self._load_file(fc.path, popup))
            btn_cancel.bind(on_release=popup.dismiss)
            popup.open()
        except Exception as e:
            self.status.text = f"文件选择失败: {e}"

    def _load_file(self, path, popup):
        try:
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.input_text.text = f.read()
                self.status.text = f"已加载: {os.path.basename(path)}"
        except Exception as e:
            self.status.text = f"加载失败: {e}"
        popup.dismiss()

    def _on_run(self, _):
        obf = _get_obfuscate()
        if obf is None:
            self.output_text.text = f"核心引擎加载失败:\n{_CORE_ERR}"
            return

        code = self.input_text.text.strip()
        if not code:
            self.status.text = "请先输入代码"
            return

        if self._running:
            return
        self._running = True
        self.btn_run.disabled = True
        self.btn_run.text = "混淆中..."
        self.status.text = "正在执行 12 层混淆..."
        self.progress.value = 30

        def _task():
            try:
                kwargs = {
                    'debug': self.opts['调试模式'].state == 'down',
                    'disable_dyninst': self.opts['禁用动态指令'].state == 'down',
                    'disable_chunksplit': self.opts['禁用分块'].state == 'down',
                    'disable_antiheur': self.opts['禁用反启发'].state == 'down',
                    'disable_adaptive': self.opts['禁用自适应'].state == 'down',
                    'keep_watermark': self.opts['保留水印'].state == 'down',
                }
                result = obf(code, **kwargs)
                Clock.schedule_once(lambda dt: self._on_done(result), 0)
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                Clock.schedule_once(lambda dt: self._on_error(err), 0)

        threading.Thread(target=_task, daemon=True).start()

    def _on_done(self, result):
        self._running = False
        self.btn_run.disabled = False
        self.btn_run.text = "开始混淆（12 层）"
        self.progress.value = 100
        self.output_text.text = result
        self.status.text = "混淆完成"

    def _on_error(self, err):
        self._running = False
        self.btn_run.disabled = False
        self.btn_run.text = "开始混淆（12 层）"
        self.progress.value = 0
        self.output_text.text = f"混淆失败:\n{err}"
        self.status.text = "混淆失败"

    def _copy_result(self, _):
        try:
            Clipboard.copy(self.output_text.text)
            self.status.text = "已复制到剪贴板"
        except Exception as e:
            self.status.text = f"复制失败: {e}"

    def _save_result(self, _):
        try:
            out_path = "/sdcard/cangmi_obfuscated.lua"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(self.output_text.text)
            self.status.text = f"已保存: {out_path}"
        except Exception as e:
            self.status.text = f"保存失败: {e}"


def main():
    _beat("gui_kivy.main() called")
    app = CangMiApp()
    _beat("CangMiApp created, calling run()...")
    app.run()


if __name__ == "__main__":
    main()