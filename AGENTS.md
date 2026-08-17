# 项目核心指令（Agent 必读）

## 同步规则（最高优先级）

**每次修改/升级混淆器后，必须同步到以下两个位置，确保都是最新版：**

1. **GitHub 仓库**: `https://github.com/3958496320/cangmi-obfuscator-apk`（main 分支）
   - 推送方式: `gh auth setup-git && git push origin main`
2. **混淆网站**: `https://3958496320.github.io/cangmi-obfuscator-apk/`（GitHub Pages 自动部署）

### 同步清单（每次改动后逐项检查）

| 文件 | 作用 | 同步操作 |
|------|------|----------|
| `src/*.py` | 混淆器源码 | git commit + push |
| `docs/obfuscator_all.py` | 网页版引擎 bundle（单文件） | 运行 `python3 docs/_rebuild_bundle_p1.py` 重建后 commit + push |
| `docs/index.html` | 网站页面 | git commit + push |
| `docs/obfuscator-worker.js` | Worker 引擎（Pyodide 线程隔离） | git commit + push |

### 重建 bundle 流程

```bash
# 1. 修改 src/ 下任意 .py 后，必须重建 bundle
python3 docs/_rebuild_bundle_p1.py

# 2. 验证 bundle 语法 + 功能
python3 -c "compile(open('docs/obfuscator_all.py').read(), 'x', 'exec'); print('OK')"

# 3. 提交并推送
git add -A && git commit -m "..." && git push origin main
```

## 架构要点

- **混淆器**: 12 层混淆 + 付费级 VM（vm_pro），纯 Python 标准库实现
- **网站**: Pyodide（Python WASM）在 Web Worker 中运行混淆器，主线程不阻塞
- **大脚本保护**: >800 行自动关闭 VM 嵌套（防 OOM 闪退），保留 VM 本体
- **注入器兼容**: 反调试阈值已调宽（_G>20000、时间 1-3s），避免真实注入器误判
