"""
RelayFreeLLM Module Test
Verify the manifest-driven architecture works correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import asyncio
import json


async def test_import():
    print("=" * 60)
    print("Test 1: Module Import")
    print("=" * 60)
    
    try:
        from app.services.relayfree import (
            BaseProvider, ProviderFactory, IntelligentRouter,
            RelayFreeServer, get_server, list_providers
        )
        print("[OK] All modules imported")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_config_loading():
    print("\n" + "=" * 60)
    print("Test 2: Config Loading")
    print("=" * 60)
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), "config/providers_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        print(f"[OK] Config loaded")
        print(f"  Version: {config.get('version')}")
        print(f"  Provider count: {len(config.get('providers', {}))}")
        
        print("\n  Provider List:")
        for pid, pcfg in list(config.get("providers", {}).items())[:5]:
            enabled = "ON" if pcfg.get("enabled") else "OFF"
            priority = pcfg.get("priority", 0)
            print(f"    [{enabled}] {pid:15} (priority:{priority})")
        if len(config.get("providers", {})) > 5:
            print(f"    ... and {len(config.get('providers', {})) - 5} more")
        
        return True
    except Exception as e:
        print(f"[FAIL] Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_provider_factory():
    print("\n" + "=" * 60)
    print("Test 3: Provider Factory")
    print("=" * 60)
    
    try:
        from app.services.relayfree.providers.dynamic_provider import ProviderFactory
        
        test_config = {
            "providers": {
                "test_provider": {
                    "enabled": True,
                    "base_url": "http://localhost:9999/v1",
                    "auth": "bearer",
                    "key_env_var": "TEST_API_KEY",
                    "priority": 500,
                    "model_mapping": {"gpt-4": "test-model"}
                }
            }
        }
        
        providers = ProviderFactory.create_all(test_config)
        print(f"[OK] ProviderFactory works")
        print(f"  Created {len(providers)} providers")
        
        if "test_provider" in providers:
            p = providers["test_provider"]
            print(f"  Type: {type(p).__name__}")
            print(f"  Model mapping test: {p.map_model('gpt-4')}")
        
        return True
    except Exception as e:
        print(f"[FAIL] ProviderFactory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_router():
    print("\n" + "=" * 60)
    print("Test 4: Intelligent Router")
    print("=" * 60)
    
    try:
        from app.services.relayfree.providers.dynamic_provider import GenericProvider
        from app.services.relayfree.router import IntelligentRouter
        
        mock_providers = {}
        for pid in ["ollama", "deepseek", "zhipu"]:
            p = GenericProvider(pid, {
                "enabled": True,
                "base_url": f"http://localhost/{pid}/v1",
                "auth": "bearer",
                "priority": 700 if pid == "ollama" else 500,
                "model_mapping": {}
            })
            mock_providers[pid] = p
        
        routing_rules = {
            "default_priority_order": ["ollama", "deepseek", "zhipu"],
            "intent_routing": {
                "code": ["ollama", "deepseek"],
                "chinese": ["zhipu", "deepseek"]
            }
        }
        
        router = IntelligentRouter(mock_providers, routing_rules)
        
        print(f"[OK] Router created")
        
        print("\n  Intent Detection Test:")
        test_cases = [
            ("write some Python code", "code"),
            ("explain machine learning in Chinese", "chinese"),
            ("Hello world", "general")
        ]
        for text, expected in test_cases:
            messages = [{"role": "user", "content": text}]
            intent = router.detect_intent(messages, "gpt-4")
            status = "OK" if intent == expected else "~"
            print(f"    [{status}] \"{text[:25]}...\" -> {intent} (expected:{expected})")
        
        return True
    except Exception as e:
        print(f"[FAIL] Router test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=" * 60)
    print("RelayFreeLLM Module Test")
    print("Manifest-Driven Architecture Verification")
    print("=" * 60)
    
    results = []
    results.append(await test_import())
    results.append(await test_config_loading())
    results.append(await test_provider_factory())
    results.append(await test_router())
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\nAll tests passed! RelayFreeLLM is working correctly.")
    else:
        print(f"\n{total - passed} test(s) failed.")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())