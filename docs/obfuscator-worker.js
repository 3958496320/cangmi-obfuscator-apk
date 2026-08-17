// obfuscator-worker.js
// Pyodide 混淆引擎 Worker：在独立线程运行，避免大脚本混淆时阻塞主线程导致页面闪退/重启。
let pyodide = null;
let doObfuscate = null;
let loading = false;

self.onmessage = async (e) => {
    const { type, payload } = e.data;
    if (type === 'init') {
        if (loading || pyodide) {
            // 已在加载或已就绪，避免重复初始化
            if (pyodide && doObfuscate) self.postMessage({ type: 'ready' });
            return;
        }
        loading = true;
        try {
            // CDN 列表（与主页面一致）
            const VERSION = '0.26.2';
            const CDNS = [
                `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/`,
                `https://unpkg.com/pyodide@${VERSION}/full/`,
                `https://fastly.jsdelivr.net/pyodide/v${VERSION}/full/`,
            ];
            let lastErr = null;
            for (let i = 0; i < CDNS.length; i++) {
                const cdn = CDNS[i];
                try {
                    self.postMessage({ type: 'progress', pct: 10 + i * 10, msg: `[${i+1}/${CDNS.length}] 下载 Python 引擎...` });
                    // Worker 中需用 importScripts 加载 pyodide.js
                    importScripts(cdn + 'pyodide.js');
                    self.postMessage({ type: 'progress', pct: 40, msg: '初始化 Python 引擎...' });
                    pyodide = await loadPyodide({ indexURL: cdn });
                    self.postMessage({ type: 'progress', pct: 60, msg: '加载混淆引擎...' });
                    // 引擎文件位于同目录
                    const resp = await fetch('obfuscator_all.py');
                    if (!resp.ok) throw new Error('引擎文件下载失败: HTTP ' + resp.status);
                    const pyCode = await resp.text();
                    pyodide.runPython(pyCode);
                    self.postMessage({ type: 'progress', pct: 90, msg: '编译入口...' });
                    doObfuscate = pyodide.runPython(`
from pyodide.ffi import create_proxy
def _do(code, ninja=False):
    try:
        return obfuscate_code(code, ninja_mode=ninja)
    except Exception as ex:
        import traceback
        return "ERROR: " + str(ex) + "\\n" + traceback.format_exc()
create_proxy(_do)
`);
                    self.postMessage({ type: 'progress', pct: 100, msg: '就绪' });
                    self.postMessage({ type: 'ready' });
                    loading = false;
                    return;
                } catch (err) {
                    lastErr = err;
                    self.postMessage({ type: 'progress', pct: 0, msg: `CDN ${i+1} 失败: ${err.message}` });
                }
            }
            throw lastErr || new Error('所有 CDN 失败');
        } catch (err) {
            loading = false;
            self.postMessage({ type: 'init_failed', msg: err.message });
        }
    } else if (type === 'obfuscate') {
        if (!doObfuscate) {
            self.postMessage({ type: 'result', ok: false, error: '引擎未就绪', id: payload.id });
            return;
        }
        try {
            // 心跳：大脚本混淆时定期向主线程发 alive 信号，主线程据此更新进度/避免看门狗杀页
            let beats = 0;
            const hb = setInterval(() => {
                beats++;
                self.postMessage({ type: 'heartbeat', beats, id: payload.id });
            }, 800);
            const result = doObfuscate(payload.code, !!payload.ninja);
            clearInterval(hb);
            self.postMessage({ type: 'result', ok: true, result, id: payload.id });
        } catch (err) {
            self.postMessage({ type: 'result', ok: false, error: err.message, id: payload.id });
        }
    }
};
