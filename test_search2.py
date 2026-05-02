import sys
sys.path.insert(0, "client/src")

from business.tool_management import registry, resolver

print('=== 测试工具管理层调用高斯烟羽模型 ===')
print()

print('1. 搜索大气扩散:')
results = registry.search_by_intent('大气扩散')
print('   结果:', len(results), '个')
for r in results:
    print('   -', r.tool_id, ':', r.name)

print()
print('2. 通过工具管理层调用高斯烟羽模型:')
result = resolver.resolve('大气扩散', {
    'emission_rate': 0.1,
    'stack_height': 20.0,
    'wind_speed': 3.0,
    'wind_direction': 180.0,
    'stability_class': 'D'
})
print('   执行成功:', result.success)
if result.success:
    print('   输出:', result.outputs)
else:
    print('   错误:', result.error)

print()
print('✅ 测试完成！')
