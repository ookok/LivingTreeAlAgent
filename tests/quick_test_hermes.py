"""Hermes Agent 增强功能快速测试"""
import sys
import os
# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)

def test_imports():
    """测试导入 - 直接导入避免项目语法错误"""
    print('Testing imports...')
    
    import importlib.util
    
    # 直接加载模块
    def load_module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    # 加载 skill_registry
    registry_path = os.path.join(project_root, 'core', 'agent_skills', 'skill_registry.py')
    sr_module = load_module('skill_registry', registry_path)
    print('  skill_registry.py: OK')
    
    # 加载 auto_evolution_skill
    ae_path = os.path.join(project_root, 'core', 'agent_skills', 'auto_evolution_skill.py')
    ae_module = load_module('auto_evolution_skill', ae_path)
    print('  auto_evolution_skill.py: OK')
    
    # 加载 honcho_user_modeling
    honcho_path = os.path.join(project_root, 'core', 'agent_skills', 'honcho_user_modeling.py')
    honcho_module = load_module('honcho_user_modeling', honcho_path)
    print('  honcho_user_modeling.py: OK')
    
    # 加载 cron_scheduler
    cron_path = os.path.join(project_root, 'core', 'agent_skills', 'cron_scheduler.py')
    cron_module = load_module('cron_scheduler', cron_path)
    print('  cron_scheduler.py: OK')
    
    return sr_module, ae_module, honcho_module, cron_module

def test_skill_registry(module):
    """测试技能注册"""
    SkillRegistry = module.SkillRegistry
    AgentType = module.AgentType
    
    registry = SkillRegistry()
    skill_data = {
        'id': 'test-skill',
        'name': 'Test Skill',
        'description': 'Test skill description',
        'category': 'review',
        'agent': 'CodeExpert',
        'inputs': [{'name': 'query', 'description': 'Query'}],
        'outputs': [{'type': 'text'}],
        'tools': ['read_file'],
    }
    manifest = registry.register_from_dict(skill_data)
    
    assert manifest.agent == AgentType.CODE_EXPERT
    print('  SkillRegistry.register_from_dict: OK')
    
    stats = registry.get_stats()
    assert stats['total_skills'] == 1
    print('  SkillRegistry.get_stats: OK')

def test_honcho(module):
    """测试用户建模"""
    HonchoUserModeling = module.HonchoUserModeling
    
    honcho = HonchoUserModeling()
    profile = honcho.get_profile('test')
    
    assert profile.user_id == 'test'
    print('  HonchoUserModeling.get_profile: OK')
    
    honcho.record_interaction('Test query', user_id='test')
    assert profile.total_interactions == 1
    print('  HonchoUserModeling.record_interaction: OK')
    
    adapted = honcho.adapt_response('Long response with lots of details', user_id='test')
    print('  HonchoUserModeling.adapt_response: OK')

def test_cron(module):
    """测试定时任务"""
    CronParser = module.CronParser
    NaturalLanguageScheduler = module.NaturalLanguageScheduler
    CronScheduler = module.CronScheduler
    
    # 测试 Cron 解析
    fields = CronParser.parse('0 9 * * *')
    assert 0 in fields['minute']
    assert 9 in fields['hour']
    print('  CronParser.parse: OK')
    
    # 测试自然语言解析
    config = NaturalLanguageScheduler.parse('Every 1 hour')
    assert config.get('interval_seconds') == 3600
    print('  NaturalLanguageScheduler.parse: OK')
    
    # 测试任务创建
    scheduler = CronScheduler()
    task = scheduler.schedule_interval(
        name='Test Task',
        interval=60,
        command='test'
    )
    assert task.interval_seconds == 60
    print('  CronScheduler.schedule_interval: OK')
    
    stats = scheduler.get_stats()
    assert stats['total_tasks'] == 1
    print('  CronScheduler.get_stats: OK')

def main():
    print('=' * 50)
    print('Hermes Agent Enhancement Tests')
    print('=' * 50)
    print()
    
    try:
        sr_module, ae_module, honcho_module, cron_module = test_imports()
        print()
        test_skill_registry(sr_module)
        print()
        test_honcho(honcho_module)
        print()
        test_cron(cron_module)
        print()
        print('=' * 50)
        print('All tests passed!')
        print('=' * 50)
        return 0
    except Exception as e:
        print()
        print('=' * 50)
        print(f'Test failed: {e}')
        import traceback
        traceback.print_exc()
        print('=' * 50)
        return 1

if __name__ == '__main__':
    exit(main())
