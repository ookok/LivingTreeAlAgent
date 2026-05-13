# LivingTree AI Agent v2.4 — AGENTS.md

> 2026-05-13 | Python 3.14+ | FastAPI + HTMX + WebRTC | 36 treellm modules | 18 LLM providers

## OVERVIEW

Digital life form AI platform. 12-organ biological architecture + self-evolving agentic system.
TreeLLM: multi-LLM orchestration with cognitive forcing, competitive elimination, stigmergy memory.

## QUICK START
```bash
python -m livingtree web            # http://localhost:8100
livingtree secrets set deepseek_api_key sk-xxx
livingtree vitals                   # 7-organ health check
```

## ARCHITECTURE (v2.4)

```
TreeLLM (36 modules, 18 providers)
├── Routing: core + holistic_election + bandit_router + classifier + providers
├── Enhancement: deep_probe + adversarial_selfplay + depth_grading + reasoning_budget
├── Competition: competitive_eliminator + joint_evolution
├── Aggregation: synapse_aggregator + reasoning_dependency_graph
├── Strategy: strategic_orchestrator + fluid_collective
├── Interaction: concurrent_stream + micro_turn_aware + proactive_interject
└── Health: vital_signs (7-organ check)
```

## KEY IMPROVEMENTS (2026-05-13 session)

| Category | Count | Description |
|----------|-------|-------------|
| Critical bugs fixed | 5 | election await, ProviderScore iteration, embedding scorer import, empty chat fallback, ping cache |
| Modules created | 17 | deep_probe, adversarial_selfplay, depth_grading, synapse_aggregator, competitive_eliminator, joint_evolution, strategic_orchestrator, reasoning_dependency_graph, fluid_collective, concurrent_stream, micro_turn_aware, proactive_interject, reasoning_budget, vital_signs, learning_sources, NatureLearner, classifier(SkillRouter) |
| Modules deleted | 12 | freebuff_provider, hifloat8_provider, provider_registry, local_scanner, gateway, bootstrap, flash_first_stream, parallel_drafter, mtp_drafter, structured_enforcer, prompt_cache, cache_safe_prompt |
| Providers configured | 18 | deepseek, longcat, xiaomi, aliyun, zhipu, hunyuan, baidu, spark, siliconflow, mofang, nvidia, modelscope, bailing, stepfun, internlm, sensetime, openrouter, dmxapi |

## RESEARCH PAPERS INTEGRATED
- Sun et al. "Robot Cognitive Learning" (3-body P→C→B framework)
- Werfel "Fluid Thinking about Collective Intelligence" (stigmergy)
- TML "Interaction Models" (micro-turn + concurrent streaming)
- DeepSeek-V4 Technical Report (3-tier reasoning budget)
- Klang et al. "Orchestrated Multi Agents" (multi-agent > single-agent)
- Buehler "PRefLexOR" (recursive self-reflection)
- Fang et al. "Self-Evolving AI Agents Survey" (4-component framework)
- Yona et al. "Hallucinations Undermine Trust" (metacognitive certainty)

## CONVENTIONS
- All new code in `livingtree/`
- Secrets: `livingtree secrets set KEY VALUE` → `config/secrets.enc`
- API: `/tree/living` (canvas), `/tree/admin` (console)
- Test: `python test_queries.py` (3-turn conversation test)
