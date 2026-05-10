# LivingTree AI Agent v5.0 — AGENTS.md

> 2026-05-10 | Python 3.14+ | FastAPI + HTMX + WebRTC | ~280 files

## OVERVIEW

Digital life form AI platform. Primary interface: **Living Canvas** — LLM-generated dynamic web UI.
TUI (Textual/Toad) retained for CLI-first workflows. All active code in `livingtree/`.

Core: 12-organ biological architecture + 7-layer self-evolution without model training.
32 new modules added in v5.0 across 4 layers: Core, Network, Management, UI.

## QUICK START

```bash
# Primary: Living Canvas web UI
python -m livingtree server           # http://localhost:8100 → /tree/living

# CLI/TUI
python -m livingtree tui              # Textual TUI
python -m livingtree client           # CLI chat

# Relay Server
python relay_server.py --port 8899    # P2P relay + front-end proxy

# Admin Console
http://localhost:8100/api/admin       # Full admin panel
```

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│                    Living Canvas (HTMX + WebRTC + PWA)      │
│  17 Business Panels · Dynamic Page Engine · Kami Theme      │
├─────────────────────────────────────────────────────────────┤
│                      Core Layer (18 modules)                │
│  dynamic_page · kami_theme · shell_env · interactive_tools  │
│  cognition_stream · perf_accel · adaptive_folder            │
│  anime_persona · living_presence · model_spec               │
│  creative_viz · final_polish · behavior_control             │
│  dpo_prefs · collective_intel · agent_qa                    │
│  resilience_brain · capability_scanner · universal_scanner  │
├─────────────────────────────────────────────────────────────┤
│                     Network Layer (8 modules)               │
│  nat_traverse · reach_gateway · swarm_coordinator           │
│  im_core · webrtc_remote · universal_pairing                │
│  message_bus (protobuf) · discovery (LAN UDP)               │
├─────────────────────────────────────────────────────────────┤
│                    Management Layer (4 modules)              │
│  admin_manager · autonomous_growth · admin_manager          │
├─────────────────────────────────────────────────────────────┤
│                Existing 45+ Modules (unchanged)             │
│  dna/ · knowledge/ · execution/ · treellm/ · capability/    │
│  economy/ · cell/ · network/ · tui/ · observability/        │
└─────────────────────────────────────────────────────────────┘
```

## COMPLETE MODULE INDEX

### Core Layer (new in v5.0)

| Module | Lines | Purpose | Adaptive Trigger |
|--------|-------|---------|-----------------|
| `dynamic_page.py` | ~250 | LLM generates complete HTML pages, no static templates | Page load / user input |
| `kami_theme.py` | ~260 | Kami design tokens: 3 themes, CSS gen, LLM constraints | Theme switch / UI gen |
| `shell_env.py` | ~330 | Env probe + safe shell exec + LocalFS bridge | Startup / mount / exec |
| `interactive_tools.py` | ~350 | AI-suggested interactive tools (map/draw/calc/code/table) | AI analyzes task context |
| `cognition_stream.py` | ~160 | SSE stream: intent→tools→memory→skills→execution | User submits question |
| `perf_accel.py` | ~300 | Stream render throttle + chunked file I/O + response cache | Auto: SSE→throttle, >100KB→chunk |
| `adaptive_folder.py` | ~150 | Context folding at natural boundaries (Neuroscience-based) | Context exceeds 4000 chars |
| `anime_persona.py` | ~340 | Unique SVG avatar per user + knowledge forest + page guide | Page load / conversations |
| `living_presence.py` | ~270 | Breathing rhythm + weather + particles + memory echoes | Page load / input / SSE |
| `model_spec.py` | ~170 | Constitution injected before every LLM call | Every LLM call |
| `creative_viz.py` | ~320 | Timeline + dream + swarm map + emotion + digital twin | User opens creative panel |
| `final_polish.py` | ~310 | Predictive precompute + session continuity + cost ladder + dedup | Auto: post-response / return / budget |
| `behavior_control.py` | ~350 | Guidelines (condition→action) + Journeys + ARQ verification | Every LLM output |
| `dpo_prefs.py` | ~280 | DPO preference learning (no RL needed) | Every ✓/✕/edit |
| `collective_intel.py` | ~320 | Memory HOT/WARM/COLD + crystallization + blueprints | Auto: conversations → memories → skills |
| `agent_qa.py` | ~300 | Metamorphic testing + golden traces + HITL bridge | On-demand / auto-regression |
| `resilience_brain.py` | ~230 | Network monitor + circuit breaker + predictive offline cache | 15s health probe |
| `capability_scanner.py` | ~220 | Auto-discover 18 external services, LLM capability analysis | 60s port scan |
| `universal_scanner.py` | ~280 | LLM-guided service discovery (OpenAI/MCP/DB/HTTP) | User describes service |
| `admin_manager.py` | ~200 | PBKDF2 password + JWT + Fernet credential vault | First run / admin login |

### Network Layer (new in v5.0)

| Module | Lines | Purpose |
|--------|-------|---------|
| `nat_traverse.py` | ~340 | RFC 5780 NAT classification + UDP hole-punching + relay pool |
| `reach_gateway.py` | ~400 | Cross-device WebSocket hub: AI pushes sensor tasks to mobile |
| `swarm_coordinator.py` | ~350 | Direct P2P: cell migration + knowledge sync + task distribution |
| `im_core.py` | ~400 | IM: friends/groups/voice/video/file/meeting via WebSocket |
| `webrtc_remote.py` | ~220 | Remote ops: terminal/files/monitor via WebRTC DataChannel |
| `universal_pairing.py` | ~320 | 4-way pairing: 8-digit code / QR / LAN auto / ultrasonic |
| `message_bus.py` | ~270 | Protobuf binary protocol (14x smaller, 10x faster than JSON) |
| `discovery.py` | ~200 | Real LAN UDP broadcast discovery (replaced stub) |

### Key Modified Files

| File | Changes |
|------|---------|
| `htmx_web.py` | 2000→3100 lines. 50+ new endpoints for all panels |
| `routes.py` | 990→1700 lines. IM WS, RTC signal, admin API, push, HITL, collective |
| `hub.py` | +50 lines. Auto-start resilience, scanner, growth, discovery, swarm |
| `dual_consciousness.py` | +5 lines. Constitution injection before every LLM call |
| `doc_engine.py` | +80 lines. LLM section generation + Kami render + config templates |
| `overnight_task.py` | 62→260 lines. Real execution engine with step tracking |
| `server.py` | +15 lines. PWA manifest/sw serving, admin page |
| `relay_server.py` | Default port 8888→8899, host configurable, front-end proxy |
| `p2p_node.py` | Default relay URL → port 8899, env-configurable |

### New Templates

| Template | Purpose |
|----------|---------|
| `living.html` | Living Canvas — the main unified interface |
| `reach_mobile.html` | Mobile PWA — AI sensory extension |
| `admin.html` | Admin console — login + config + services + credentials |

### New Config/Static Files

| File | Purpose |
|------|---------|
| `client/web/manifest.json` | PWA manifest with protocol_handlers + share_target |
| `client/web/sw.js` | Service worker: offline cache + push + badge |
| `client/web/assets/icon.svg` | PWA icon |
| `deploy/docker/Dockerfile.relay` | Relay server Docker image |
| `.livingtree/model_spec.md` | AI Constitution (5 core values) |

## BUSINESS PANELS (17 total)

```
User-visible (always shown):
  📄 行业报告  🔬 挂机任务  📱 感官扩展  💻 Shell
  💬 IM       🖥 远控      🔗 配对      🎨 创意

Admin-only (⚙ login required):
  💰 费用节省  🧮 ROI计算   🕸️ 群体智能  🛡️ 韧性
  🌟 北极星    🧪 QA       🧠 CI        🛡️ 行为
  🎯 DPO
```

## ADAPTIVE ROUTING (self-triggered, no manual calls)

```
Page load → dynamic_page + kami_theme + living_presence + anime_persona
User types → debounceEcho (memory echoes) → cognition_stream (visible thinking)
LLM call  → model_spec (constitution prepend)
LLM reply → behavior_control (ARQ verify) → perf_accel (cache)
          → adaptive_folder (fold if >4000 chars)
          → final_polish (predict next, save checkpoint)
          → collective_intel (store memory, auto-classify)
          → anime_persona (plant tree in forest)
User ✓/✕  → dpo_prefs (update preference scores)
3 validations → collective_intel (crystallize memory → skill)
Network down → resilience_brain (degrade tier, pre-cache)
Service up   → capability_scanner (discover + analyze + register)
Device near  → universal_pairing (pair) → reach_gateway (sensor tasks)
Node found   → nat_traverse (hole-punch) → swarm_coordinator (direct P2P)
```

## KEY API ENDPOINTS

```
# Living Canvas
GET  /tree/living              Living Canvas main page
GET  /tree/dynamic?message=    LLM-generated dynamic page
GET  /tree/theme/{dark|light|kami}  Dynamic theme CSS

# Cognition & Tools
GET  /tree/sse/cognition?message=   SSE cognition stream
GET  /tree/tools/suggest?context=   AI tool suggestions
POST /tree/tools/result             Tool result → AI feedback

# Shell & Environment
GET  /tree/shell/env           Environment toolchain probe
POST /tree/shell/exec          Safe shell execution
POST /tree/shell/mount         Mount local folder

# IM & Communication
WSS  /ws/im                    IM WebSocket (DM/group/call/meeting)
WSS  /ws/rtc-signal            WebRTC signaling + remote ops
GET  /tree/im/panel            IM panel

# P2P & Swarm
GET  /tree/swarm/panel         Swarm intelligence panel
POST /api/swarm/cell/receive   Receive cell (binary protobuf)
POST /api/swarm/task/distribute Distribute task to peers
GET  /tree/p2p/status          NAT type + relay health

# Push & PWA
GET  /api/push/vapid-key       VAPID public key
POST /api/push/subscribe       Store push subscription
POST /api/push/send            Send push notification

# Admin
GET  /api/admin                Admin console
POST /api/admin/login          Admin login (JWT)
POST /api/admin/config/chat    Conversational config (LLM-powered)
POST /api/admin/services/discover  Discover external service

# Collective Intelligence
POST /api/collective/publish   Publish agent blueprint
POST /api/collective/import/{id} Import blueprint

# HITL
POST /api/hitl/approve         Approve HITL request
POST /api/hitl/reject          Reject HITL request

# Pairing
GET  /tree/pair/all-methods    All 4 pairing methods
GET  /api/pairing/audio        Ultrasonic pairing signal
POST /api/pairing/code         Verify 8-digit code

# Creative Visualizations
GET  /tree/creative/timeline   Memory timeline
GET  /tree/creative/dream      Dream canvas
GET  /tree/creative/emotion    Emotion gauge
GET  /tree/creative/twin       Digital twin mirror

# Presence
GET  /tree/persona             Unique anime avatar
GET  /tree/persona/forest      Personal knowledge forest
GET  /tree/presence/living-layer Breathing + weather + particles
```

## RUN COMMANDS

```bash
# Living Canvas (primary)
python -m livingtree server              # http://localhost:8100 → /tree/living

# TUI (Textual, legacy)
python -m livingtree tui
python -m livingtree tui --direct

# CLI
python -m livingtree client
python -m livingtree quick "message"

# Relay Server
python relay_server.py --port 8899
python relay_server.py --port 8899 --host 0.0.0.0
docker run -p 8899:8899 livingtree-relay

# Build relay EXE
.venv\Scripts\python.exe build_relay_exe.py

# Admin
http://localhost:8100/api/admin

# Tests
pytest
```

## SELF-EVOLUTION WITHOUT MODEL TRAINING

The architecture proves that industry expertise and continuous improvement
do NOT require model fine-tuning. Seven mechanisms achieve this:

1. **Memory Tiering** (HOT/WARM/COLD) — frequency-driven with time decay
2. **Memory → Skill Crystallization** — validated 3x → auto-registered skill
3. **DPO Preference Learning** — every ✓/✕ updates scores, no RL needed
4. **Model Spec / Constitution** — values injected before every call
5. **Cell Mitosis + Blueprints** — successful patterns replicate
6. **Swarm Knowledge Sync** — one node learns, all benefit
7. **Adaptive Context Folding** — compress at boundaries, save tokens

## CONVENTIONS

- **All new code** goes in `livingtree/` — never in `client/`
- **Imports**: `from livingtree.core import ...`
- **WebSocket**: `/ws`, `/ws/im`, `/ws/rtc-signal`, `/ws/reach`
- **Protobuf**: All P2P messages use binary (message_bus.py)
- **Self-triggering**: New features auto-activate, no manual calls needed
- **Kami design**: All UI follows Kami token system
- **Admin panels**: Hidden by default, ⚙ button to unlock

## ANTI-PATTERNS

- ❌ Don't hardcode tools or templates — use AI-driven discovery
- ❌ Don't train models for behavior — use Constitution + Guidelines
- ❌ Don't use JSON for P2P — use protobuf (message_bus.py)
- ❌ Don't add static pages — use dynamic_page.py (LLM generates)
- ❌ Don't expose admin panels to end users — ⚙ gate required
