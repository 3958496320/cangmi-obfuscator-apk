#!/usr/bin/env python3
"""
苍米独家混淆 - Web 版
手机浏览器直接访问，无需安装任何东西。
"""
import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory

# 优先使用 docs/obfuscator_all.py（增强单文件版，含全部提升5-11增强层）。
# 该文件是自包含的，无需 src/ 模块依赖，且始终与最新增强同步。
# src/obfuscator_core.py 为旧版模块化实现，仅作回退。
_BASE = os.path.dirname(os.path.abspath(__file__))
_OBF_ALL = os.path.join(_BASE, 'docs', 'obfuscator_all.py')
if os.path.isfile(_OBF_ALL):
    # 执行单文件增强版，从中获取 obfuscate 函数
    _ns = {'__name__': '_obf_all', '__file__': _OBF_ALL}
    with open(_OBF_ALL, 'r', encoding='utf-8') as _f:
        exec(compile(_f.read(), _OBF_ALL, 'exec'), _ns)
    obfuscate = _ns['obfuscate']
else:
    # 回退到 src/ 模块化版本
    SRC_DIR = os.path.join(_BASE, 'src')
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    from obfuscator_core import obfuscate

app = Flask(__name__, static_folder='web_static')


@app.route('/')
def index():
    return send_from_directory('web_static', 'index.html')


@app.route('/api/obfuscate', methods=['POST'])
def api_obfuscate():
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': '请输入代码'}), 400

        result = obfuscate(code)
        return jsonify({
            'code': result['code'],
            'stats': {
                'seed': result['stats'].get('seed'),
                'lines': result['stats'].get('lines'),
                'output_chars': result['stats'].get('output_chars'),
                'profile': result.get('profile', {}).get('name', 'auto'),
            }
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
