import sys
sys.path.insert(0, 'client/src')

from business.encrypted_config import get_config_manager, load_model_config, save_model_config

manager = get_config_manager()

print('📋 已保存的配置列表:', manager.list_configs())

print()
print('🔍 DeepSeek 配置:')
ds_cfg = load_model_config('deepseek')
if ds_cfg:
    api_key = ds_cfg.get('api_key', '')
    print(f'API Key: {api_key[:10]}...')
    print(f'Base URL: {ds_cfg.get("base_url", "")}')
    print(f'Models: {list(ds_cfg.get("models", {}).keys())}')
else:
    print('DeepSeek 配置不存在，正在创建...')
    ds_cfg = {
        'api_key': 'sk-f05ded8271b74091a499831999d34437',
        'base_url': 'https://api.deepseek.com',
        'models': {
            'flash': {
                'model_id': 'deepseek_v4_flash',
                'model_name': 'DeepSeek-V4-Flash',
                'capabilities': ['chat', 'content_generation', 'summarization', 'translation', 'code_generation'],
                'max_tokens': 8192,
                'context_length': 32768,
                'quality_score': 0.8,
                'speed_score': 0.9,
                'cost_score': 0.7,
                'timeout': 60,
            },
            'pro': {
                'model_id': 'deepseek_v4_pro',
                'model_name': 'DeepSeek-V4-Pro',
                'capabilities': ['chat', 'document_planning', 'content_generation', 'reasoning', 'planning', 'code_generation', 'code_review'],
                'max_tokens': 16384,
                'context_length': 65536,
                'quality_score': 0.95,
                'speed_score': 0.5,
                'cost_score': 0.4,
                'timeout': 120,
            }
        }
    }
    save_model_config('deepseek', ds_cfg)
    print('✅ DeepSeek 配置已保存!')

print()
print('🔍 Ollama 配置:')
ollama_cfg = load_model_config('ollama')
if ollama_cfg:
    servers = ollama_cfg.get('servers', [])
    print(f'Servers: {len(servers)}')
    for srv in servers:
        print(f"  - {srv.get('url')} (priority: {srv.get('priority')})")
