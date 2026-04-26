"""临时测试脚本 - 验证路由注册"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from client.src.presentation.router.routes import register_default_routes
from client.src.presentation.router.router import Router

r = Router()
register_default_routes(r)
routes = list(r._routes.values())

print("=" * 50)
print("Routes:")
for rt in routes:
    print(f"  [{rt.category}] {rt.emoji} {rt.name} ({rt.route_id})")
print(f"\nTotal: {len(routes)}")
print("=" * 50)

# 测试面板类是否能正确引用
print("\nPanel class tests:")
for rt in routes:
    panel_class = rt.panel_class
    if panel_class is None:
        print(f"  ❌ {rt.name}: panel_class is None")
    elif callable(panel_class):
        print(f"  ✅ {rt.name}: {panel_class}")
    else:
        print(f"  ⚠️ {rt.name}: {type(panel_class)}")
