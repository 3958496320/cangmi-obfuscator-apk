# -*- coding: utf-8 -*-
"""
苍米独家混淆 - Android APK 入口
v2.0.1 - 极简稳定版
"""
import sys
import os

# 最基础配置
os.environ['KIVY_NO_CONSOLELOG'] = '0'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
import threading

Window.clearcolor = (0.04, 0.055, 0.102, 1)

APP_TITLE = "苍米独家混淆"
APP_VERSION = "v2.0.1"

# 延迟导入
_obfuscate = None
_core_error = ""

def get_obfuscate():
    global _obfuscate, _core_error
    if _obfuscate is not None:
        return _obfuscate
    try:
        src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
        if os.path.isdir(src_dir) and src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from obfuscator_core import obfuscate
        _obfuscate = obfuscate
        return _obfuscate
    except Exception as e:
        import traceback
        _core_error = traceback.format_exc()
        return None


class CangMiApp(App):
    def build(self):
        self.title = f"{APP_TITLE} {APP_VERSION}"
        self._running = False
        
        root = BoxLayout(orientation='vertical', padding=10, spacing=8)
        
        # 标题
        root.add_widget(Label(
            text=APP_TITLE,
            font_size='22sp', bold=True,
            color=(0, 0.9, 1, 1),
            size_hint_y=None, height=50
        ))
        root.add_widget(Label(
            text=APP_VERSION + " - 12层混淆保护",
            font_size='12sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None, height=25
        ))
        
        # 输入区
        root.add_widget(Label(
            text="输入 Luau 脚本",
            font_size='13sp', bold=True,
            color=(0.5, 0.4, 1, 1),
            size_hint_y=None, height=30,
            halign='left'
        ))
        self.input_text = TextInput(
            hint_text="在此粘贴要混淆的代码...",
            multiline=True,
            size_hint_y=0.3,
            font_size='13sp'
        )
        root.add_widget(self.input_text)
        
        # 按钮行
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=8)
        self.btn_clear = Button(text="清空", font_size='14sp')
        self.btn_clear.bind(on_release=lambda x: setattr(self.input_text, 'text', ''))
        self.btn_run = Button(
            text="开始混淆",
            font_size='16sp', bold=True,
            background_color=(0, 0.9, 1, 1),
            color=(0, 0, 0, 1)
        )
        self.btn_run.bind(on_release=self.do_obfuscate)
        btn_row.add_widget(self.btn_clear)
        btn_row.add_widget(self.btn_run)
        root.add_widget(btn_row)
        
        # 输出区
        root.add_widget(Label(
            text="输出结果",
            font_size='13sp', bold=True,
            color=(0.5, 0.4, 1, 1),
            size_hint_y=None, height=30,
            halign='left'
        ))
        self.output_text = TextInput(
            hint_text="混淆后的代码将显示在这里...",
            multiline=True, readonly=True,
            size_hint_y=0.35,
            font_size='12sp'
        )
        root.add_widget(self.output_text)
        
        # 复制按钮
        self.btn_copy = Button(
            text="复制结果",
            size_hint_y=None, height=45,
            font_size='14sp',
            background_color=(0.3, 0.8, 0.5, 1),
            color=(0, 0, 0, 1)
        )
        self.btn_copy.bind(on_release=self.copy_result)
        root.add_widget(self.btn_copy)
        
        # 状态栏
        self.status = Label(
            text="就绪",
            font_size='11sp',
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None, height=25
        )
        root.add_widget(self.status)
        
        return root
    
    def do_obfuscate(self, instance):
        if self._running:
            return
        obf = get_obfuscate()
        if obf is None:
            self.output_text.text = "核心加载失败:\n" + _core_error
            self.status.text = "错误"
            return
        
        code = self.input_text.text.strip()
        if not code:
            self.status.text = "请先输入代码"
            return
        
        self._running = True
        self.btn_run.disabled = True
        self.btn_run.text = "混淆中..."
        self.status.text = "正在处理..."
        
        def task():
            try:
                result = obf(code)
                Clock.schedule_once(lambda dt: self.on_done(result), 0)
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                Clock.schedule_once(lambda dt: self.on_error(err), 0)
        
        threading.Thread(target=task, daemon=True).start()
    
    def on_done(self, result):
        self._running = False
        self.btn_run.disabled = False
        self.btn_run.text = "开始混淆"
        if isinstance(result, dict):
            self.output_text.text = result.get('code', str(result))
        else:
            self.output_text.text = str(result)
        self.status.text = "混淆完成"
    
    def on_error(self, err):
        self._running = False
        self.btn_run.disabled = False
        self.btn_run.text = "开始混淆"
        self.output_text.text = "混淆失败:\n" + err
        self.status.text = "失败"
    
    def copy_result(self, instance):
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.output_text.text)
            self.status.text = "已复制到剪贴板"
        except Exception as e:
            self.status.text = f"复制失败: {e}"


if __name__ == '__main__':
    CangMiApp().run()
