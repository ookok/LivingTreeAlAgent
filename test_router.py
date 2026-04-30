import sys
sys.path.insert(0, 'client/src')

from business.global_model_router import GlobalModelRouter, ModelCapability, ModelTier

print('🚀 初始化全局模型路由器...')
router = GlobalModelRouter()

print()
print('=' * 60)
print('📋 已加载的模型:')
print('=' * 60)
for model_id, model in router.models.items():
    status = '✅' if model.is_available else '❌'
    print(f'{status} {model.name}')
    print(f'   - ID: {model_id}')
    print(f'   - 后端: {model.backend.value}')
    caps = [c.value for c in model.capabilities]
    print(f'   - 能力: {", ".join(caps)}')
    print(f'   - 质量: {model.quality_score}, 速度: {model.speed_score}, 成本: {model.cost_score}')
    print()

print('=' * 60)
print('🏢 分层路由配置 (L0-L4):')
print('=' * 60)
for tier in ['L0', 'L1', 'L2', 'L3', 'L4']:
    model_id = router.tier_routing.get(tier)
    if model_id and model_id in router.models:
        model = router.models[model_id]
        print(f'{tier} → {model.name}')
    else:
        print(f'{tier} → 未配置')

print()
print('=' * 60)
print('🔍 路由测试 (CHAT 能力):')
print('=' * 60)
result = router.route(ModelCapability.CHAT)
if result:
    print(f'推荐模型: {result.name}')
    print(f'模型ID: {result.model_id}')
    print(f'后端类型: {result.backend.value}')
else:
    print('无可用模型')

print()
print('=' * 60)
print('🔍 路由测试 (CODE_GENERATION 能力):')
print('=' * 60)
result = router.route(ModelCapability.CODE_GENERATION)
if result:
    print(f'推荐模型: {result.name}')
else:
    print('无可用模型')

print()
print('=' * 60)
print('🔍 路由决策解释:')
print('=' * 60)
explanation = router.explain_routing(ModelCapability.CHAT)
print(f"策略: {explanation['strategy']}")
print(f"权重: {explanation['weights']}")
print("\n候选模型评分:")
for candidate in explanation['candidates'][:3]:
    print(f"  {candidate['name']}:")
    print(f"    能力评分: {candidate['capability']}")
    print(f"    成本评分: {candidate['cost']}")
    print(f"    延迟评分: {candidate['latency']}")
    print(f"    综合评分: {candidate['combined']}")
