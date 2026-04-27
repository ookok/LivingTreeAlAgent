"""验证 Hermes 增强模块功能"""
import sys
import os

# 测试 cron_scheduler
print("Testing cron_scheduler...")
exec(open('core/agent_skills/cron_scheduler.py', encoding='utf-8').read())
fields = CronParser.parse('0 9 * * *')
print(f'  CronParser: minute={fields["minute"]}, hour={fields["hour"]} - OK')
config = NaturalLanguageScheduler.parse('Every 1 hour')
print(f'  NaturalLanguageScheduler: interval={config.get("interval_seconds")}s - OK')
s = CronScheduler()
t = s.schedule_interval(name='Test', interval=60, command='test')
print(f'  CronScheduler.schedule_interval: {t.interval_seconds}s - OK')
print("  CronScheduler: PASSED")

# 测试 honcho_user_modeling
print("\nTesting honcho_user_modeling...")
exec(open('core/agent_skills/honcho_user_modeling.py', encoding='utf-8').read())
h = HonchoUserModeling()
p = h.get_profile('test')
print(f'  get_profile: {p.user_id} - OK')
h.record_interaction('test query', user_id='test')
print(f'  record_interaction: {p.total_interactions} - OK')
print("  HonchoUserModeling: PASSED")

# 测试 skill_registry
print("\nTesting skill_registry...")
exec(open('core/agent_skills/skill_registry.py', encoding='utf-8').read())
r = SkillRegistry()
m = r.register_from_dict({'id': 'test', 'name': 'Test', 'description': 't', 'category': 'review', 'agent': 'CodeExpert'})
print(f'  register_from_dict: {m.agent.value} - OK')
print("  SkillRegistry: PASSED")

print("\n" + "="*50)
print("All Hermes Enhancement Modules: PASSED")
print("="*50)
