#!/usr/bin/env python3
"""
苍米独家混淆 - Web 版
手机浏览器直接访问，无需安装任何东西。
"""
import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory

# 添加 src 目录到 path
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
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
