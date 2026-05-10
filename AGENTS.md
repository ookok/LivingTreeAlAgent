# LivingTree AI Agent v2.3 — AGENTS.md

> 2026-05-10 | Python 3.14+ | FastAPI + HTMX + WebRTC | ~340 files

## OVERVIEW

Digital life form AI platform. Primary interface: **Living Canvas** — LLM-generated dynamic web UI.
12-organ biological architecture + 7-layer self-evolution without model training.

## QUICK START

```bash
# Primary: Living Canvas web UI
python -m livingtree web            # http://localhost:8100 → /tree/living

# One-click install
powershell -c "irm https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.ps1 | iex"
bash <(curl -fsSL https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.sh)

# Admin Console (unified)
http://localhost:8100/tree/admin    # All panels in one view

# CLI (CowAgent style)
livingtree start                    # Background daemon
livingtree stop                     # Stop service
livingtree status                   # Service status
livingtree logs 50                  # Last 50 log lines
livingtree skill hub                # Browse skill marketplace
livingtree skill install X          # Install skill
livingtree secrets set openrouter_api_key sk-or-v1-...
```

## ARCHITECTURE (v2.3 — 本对话新增)

```
┌──────────────────────────────────────────────────────────────────┐
│                   Living Canvas (HTMX + WebRTC + PWA)            │
│  Chat · Video Search · Voice Call · Pseudo-Upload · Admin Console│
├──────────────────────────────────────────────────────────────────┤
│  Core Engine (30+ new modules from 2026-05-10 session)           │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Chrome & Speech                                           │     │
│  │  chrome_dual.py (npx MCP / CDP)  voice_call.py (实时通话)   │     │
│  │  unified_speech.py (统一语音)    moss_tts_engine.py (GGUF) │     │
│  │  llamacpp_backend.py (本地LLM)  freebuff_provider.py(广告) │     │
│  ├─────────────────────────────────────────────────────────┤     │
│  │ AI Routing & Models                                       │     │
│  │  model_dashboard.py (LLMFit评估)  processing_framework.py   │     │
│  │  openrouter provider (300+模型)  DiLoCo decoupled_executor  │     │
│  │  context_budget.py (智能压缩)     auto_classifier.py (9领域) │     │
│  ├─────────────────────────────────────────────────────────┤     │
│  │ Knowledge & Quality                                       │     │
│  │  inline_parser.py (伪上传)       knowledge_lineage.py (血缘)│     │
│  │  quality_guard.py (6参数化测试)   skill_hub.py (插件生态)    │     │
│  │  video_search.py (B站+YT)        enhanced_skill_hub.py      │     │
│  ├─────────────────────────────────────────────────────────┤     │
│  │ Admin & Visualization                                     │     │
│  │  admin_console (统一面板)        organ_dashboard.py (12器官) │     │
│  │  creative_viz.py (知识气象图)    system_health.py (goodput)  │     │
│  │  emergence_detector.py (相变检测) predictability (语言视域)  │     │
│  ├─────────────────────────────────────────────────────────┤     │
│  │ Network & Channels                                        │     │
│  │  channel_bridge.py (6通道)       swarm_coordinator (片段同步)│     │
│  │  Scinet proxy (YouTube隧道)      anime_persona (语音驱动)    │     │
│  └─────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  Existing 45+ Modules (unchanged)                                │
│  dna/ · knowledge/ · execution/ · treellm/ · economy/ · cell/   │
└──────────────────────────────────────────────────────────────────┘
```

## KEY NEW MODULES (this session: ~40 files)

| Category | Module | Lines | Inspired by |
|----------|--------|-------|-------------|
| **Chrome** | chrome_dual.py + chrome_mcp_node.mjs | 750 | npx MCP / CDP dual-mode |
| **Voice** | voice_call.py + unified_speech.py | 630 | MiniMind-O speech-native |
| **TTS** | moss_tts_engine.py (GGUF Q4_K_M) | 490 | MOSS-TTS-Nano ~200MB |
| **LLM** | llamacpp_backend.py + freebuff_provider.py | 430 | llama.cpp + OpenRouter |
| **Models** | model_dashboard.py + auto_classifier.py | 560 | LLMFit + OpenMetadata |
| **Knowledge** | inline_parser.py + knowledge_lineage.py | 700 | QGIS pseudo-upload + OM lineage |
| **Processing** | processing_framework.py + decoupled_executor.py | 500 | QGIS toolbox + DiLoCo |
| **Admin** | enhanced_skill_hub.py + organ_dashboard.py | 580 | QGIS plugins + layer tree |
| **Channels** | channel_bridge.py + swarm fragment sync | 480 | CowAgent 7-channel |
| **Election** | context_budget.py + L4 smart fallback | 280 | CowAgent + route_layered upgrade |
| **Video** | video_search.py (Bilibili WBI + YT) | 330 | multi-source search |
| **Config** | skill_hub.py + secrets vault | 360 | encrypted key storage |

## COMMANDS (CowAgent style)

```bash
livingtree start|stop|restart|status|logs|update   # service mgmt
livingtree skill hub|list|install|search|uninstall  # skills
livingtree channel weixin|feishu|dingtalk|qq        # channels
livingtree secrets list|set|get|delete              # vault
livingtree config [key] [val]                       # config
```

## SECRETS

API keys stored encrypted in `config/secrets.enc` (Fernet + machine-derived key).
Never commit plaintext keys. Use: `livingtree secrets set KEY VALUE`

## CONVENTIONS

- **All new code** goes in `livingtree/` — never in `client/`
- **Secrets**: `livingtree secrets set` → `config/secrets.enc`
- **Admin**: `/tree/admin` unified console
- **WebSocket**: `/ws/voice` for calls, `/ws/im` for messaging, `/ws/reach` for sensors
- **Self-triggering**: New features auto-activate, no manual calls needed

## ANTI-PATTERNS

- ❌ Don't hardcode API keys — use `livingtree secrets set`
- ❌ Don't store audio/video on disk — use inline_parser / unified_speech
- ❌ Don't add static admin pages — use /tree/admin unified console
