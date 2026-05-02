"""
LivingTree Vue 前端桥接脚本
============================

在 client/src/frontend/ 中注入 LivingTree 后端连接的脚本。
通过 backend.js 暴露的 API 桥接到 livingtree/ 包的 LifeEngine。

使用方法：
1. 在 Vue 前端 index.html 中引入此脚本
2. 或者在 Vue 的 main.js 中 import
"""

# 此文件作为参考实现，实际 Vue 前端引入方式见下方 JS 版本
# 前端通过 backend.js 调用 livingtree 后端 API

VUE_BRIDGE_JS = r"""
// LivingTree Frontend Bridge
// 桥接 Vue 前端到 livingtree 后端 API

const LivingTreeBridge = {
  // 后端 API 基础 URL
  baseURL: window.location.origin + '/api',

  // 发送聊天消息
  async chat(message, sessionId) {
    try {
      const resp = await fetch(this.baseURL + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          session_id: sessionId || '',
        }),
      });
      return await resp.json();
    } catch (e) {
      return { type: 'error', error: e.message };
    }
  },

  // 健康检查
  async health() {
    try {
      const resp = await fetch(this.baseURL + '/health');
      return await resp.json();
    } catch (e) {
      return { status: 'error', error: e.message };
    }
  },

  // 获取可用工具列表
  async getTools() {
    try {
      const resp = await fetch(this.baseURL + '/tools');
      return await resp.json();
    } catch (e) {
      return { tools: [], error: e.message };
    }
  },

  // 获取可用技能列表
  async getSkills() {
    try {
      const resp = await fetch(this.baseURL + '/skills');
      return await resp.json();
    } catch (e) {
      return { skills: [], error: e.message };
    }
  },
};

// 挂载到全局
window.LivingTreeBridge = LivingTreeBridge;
"""


def get_vue_bridge_js():
    """返回前端桥接 JS 代码"""
    return VUE_BRIDGE_JS


def inject_bridge_into_vue(vue_index_path: str):
    """在 Vue 的 index.html 中注入桥接脚本"""
    import os

    if not os.path.exists(vue_index_path):
        print(f"[Bridge] Vue index.html not found: {vue_index_path}")
        return False

    with open(vue_index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已经注入
    if 'LivingTreeBridge' in content:
        print("[Bridge] Already injected, skipping")
        return True

    injection = f'\n<script>\n{VUE_BRIDGE_JS}\n</script>\n'

    # 在 </head> 或 </body> 前注入
    if '</body>' in content:
        content = content.replace('</body>', injection + '</body>')
    elif '</head>' in content:
        content = content.replace('</head>', injection + '</head>')
    else:
        content += injection

    with open(vue_index_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[Bridge] Injected LivingTree Bridge into {vue_index_path}")
    return True


__all__ = ["get_vue_bridge_js", "inject_bridge_into_vue", "VUE_BRIDGE_JS"]
