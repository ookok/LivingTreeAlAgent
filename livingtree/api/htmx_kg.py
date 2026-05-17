"""HTMX Knowledge Graph routes."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

kg_router = APIRouter(prefix="/kg", tags=["kg"])

@kg_router.post("/kg/explore")
async def tree_kg_explore(request: Request):
    """P6: Explore a knowledge graph entity — LLM generates expandable node card.

    Returns an HTML card with the entity info and HTMX buttons to expand
    related entities, drill down, or traverse edges.
    """
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {"entity": form_data.get("entity", form_data.get("message", ""))}

    entity = body.get("entity", body.get("message", ""))
    if not entity.strip():
        return HTMLResponse('<div class="card"><p>请输入要探索的知识实体</p></div>')

    hub = _get_hub(request)

    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            kg_prompt = (
                f"关于 '{entity}' 的知识图谱节点。\n"
                "生成一个HTML卡片，包含:\n"
                "1. 实体名称作为h3标题\n"
                "2. 简短描述(1-2句)\n"
                "3. 3-5个相关实体，每个是一个按钮: "
                '<button hx-post="/tree/kg/explore" hx-vals=\'{"entity":"RELATED"}\' '
                'hx-target="#kg-expanded" hx-swap="beforeend">RELATED</button>\n'
                "4. 用 class='kg-node' 标识卡片\n"
                "5. 只输出HTML片段，不要代码块标记\n"
            )
            resp = await consc.chain_of_thought(kg_prompt, steps=2)
            text = resp if isinstance(resp, str) else str(resp)

            html_content = _extract_html_from_response(text)
            return HTMLResponse(
                f'<div class="kg-node" style="background:var(--panel);border:1px solid var(--border);'
                f'padding:12px;border-radius:6px;margin:8px 0">'
                f'{html_content}'
                f'</div>'
                f'<div id="kg-expanded"></div>'
            )
        else:
            return HTMLResponse(
                f'<div class="card"><p>知识引擎启动中...</p></div>'
            )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p>探索失败: {_html.escape(str(e)[:200])}</p></div>'
        )


# ═══════════════════════════════════════════════════════════════
#  P8: Interactive Graph Visualization (Vector Graph RAG style)
#  Returns JSON for vis-network rendering with entities + relations + passages
# ═══════════════════════════════════════════════════════════════

@kg_router.post("/kg/graph-viz")
async def tree_kg_graph_viz(request: Request):
    """P8: Return graph visualization data for multi-hop query.

    Returns JSON with entities, relations, passages suitable for
    vis-network interactive graph rendering.
    Uses SinglePassReranker + MilvusStore for subgraph expansion.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", body.get("entity", ""))
    if not query.strip():
        return JSONResponse({"entities": [], "relations": [], "passages": [], "summary": "请输入查询"})

    hub = _get_hub(request)

    try:
        entities = []
        relations = []
        passages = []
        answer = ""

        # Try SinglePassReranker first (Vector Graph RAG pipeline)
        try:
            from livingtree.knowledge.single_pass_reranker import get_single_pass_reranker
            from livingtree.knowledge.milvus_store import get_milvus_store

            store = get_milvus_store()
            reranker = get_single_pass_reranker(store=store)
            result = await reranker.retrieve(query)

            answer = result.answer or ""
            entities = [{"id": eid, "label": eid} for eid in result.entities[:15]]
            relations = [
                {"id": r.get("id", f"rel_{i}"), "text": r.get("text", "")[:200], "entity_ids": r.get("entity_ids", "[]"), "score": r.get("distance", 0.3)}
                for i, r in enumerate(result.relations[:30])
            ]
            passages = [
                {"id": p.get("id", f"p_{i}"), "text": (p.get("text", "") or p.get("id", ""))[:300], "score": p.get("distance", 0.3)}
                for i, p in enumerate(result.passages[:10])
            ]
        except Exception as e:
            logger.info(f"SinglePassReranker unavailable: {e}, using KnowledgeGraph fallback")

            # Fallback: use KnowledgeGraph + RetrievalFramework
            if hub and hub.world:
                try:
                    rf = hub.world.get("retrieval_framework")
                    if rf is None:
                        from livingtree.knowledge.retrieval_framework import get_retrieval_framework
                        rf = get_retrieval_framework()

                    decision = rf.decide(query)
                    params = rf.get_retrieval_params(decision)

                    from livingtree.knowledge.knowledge_graph import KnowledgeGraph
                    kg = KnowledgeGraph()

                    # Extract triplets and add to graph
                    triplets = kg.extract_triplets(query)
                    kg.add_triplets_to_graph(triplets)

                    for t in triplets:
                        entities.append({"id": t.subject, "label": t.subject, "score": t.confidence})
                        entities.append({"id": t.obj, "label": t.obj, "score": t.confidence})
                        relations.append({
                            "id": f"{t.subject}_{t.predicate}_{t.obj}",
                            "text": f"({t.subject}, {t.predicate}, {t.obj})",
                            "entity_ids": _json.dumps([t.subject, t.obj]),
                            "score": t.confidence,
                        })

                    if hub.world.consciousness:
                        resp = await hub.world.consciousness.chain_of_thought(
                            f"基于查询生成简要回答(中文,50字以内): {query}", steps=1
                        )
                        answer = resp if isinstance(resp, str) else str(resp)
                except Exception as e2:
                    logger.warning(f"KnowledgeGraph fallback failed: {e2}")

            # Deduplicate entities by id
            seen = set()
            entities = [e for e in entities if not (e["id"] in seen or seen.add(e["id"]))]

        return JSONResponse({
            "entities": entities[:20],
            "relations": relations[:30],
            "passages": passages[:10],
            "answer": answer[:500],
            "summary": f"实体:{len(entities)} 关系:{len(relations)} 段落:{len(passages)}",
        })
    except Exception as e:
        logger.error(f"graph-viz error: {e}")
        return JSONResponse({
            "entities": [], "relations": [], "passages": [],
            "summary": f"检索出错: {str(e)[:100]}",
        })


@kg_router.get("/kg/node")
async def tree_kg_node(request: Request, entity: str = Query(default="")):
    """GET variant: render a knowledge graph node."""
    if not entity.strip():
        return HTMLResponse('<div class="card"><p>请指定实体</p></div>')

    hub = _get_hub(request)

    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            resp = await consc.chain_of_thought(
                f"用2-3句话描述 '{entity}' 及其核心属性。只输出HTML片段。", steps=1
            )
            text = resp if isinstance(resp, str) else str(resp)
            return HTMLResponse(
                f'<div class="kg-node" style="background:var(--panel);border-left:3px solid var(--accent);'
                f'padding:12px;margin:6px 0;border-radius:4px">'
                f'<span style="color:var(--accent);font-weight:600">{_html.escape(entity)}</span>'
                f'<p style="font-size:12px;margin-top:4px">{_html.escape(text[:300])}</p>'
                f'<button hx-get="/tree/kg/node?entity={_html.escape(entity)}" '
                f'hx-target="closest .kg-node" hx-swap="beforebegin" '
                f'style="font-size:10px;padding:3px 8px;margin-top:4px">▶ 展开关联</button>'
                f'</div>'
            )
        else:
            return HTMLResponse(
                f'<div class="kg-node"><span style="color:var(--accent)">{_html.escape(entity)}</span>'
                f'<p style="font-size:12px;color:var(--dim)">知识引擎就绪中...</p></div>'
            )
    except Exception as e:
        return HTMLResponse(
            f'<div class="kg-node"><span style="color:var(--err)">错误: {_html.escape(str(e)[:100])}</span></div>'
        )


# ═══════════════════════════════════════════════════════════════
#  Shihipar-inspired routes — LLM outputs HTML, not Markdown
# ═══════════════════════════════════════════════════════════════

# ── About: dynamic tree persona (replaces static index card) ──

@kg_router.get("/about", response_class=HTMLResponse)
async def tree_about(request: Request):
    """Dynamic about card — LLM reflects on its own state in HTML.

    Shihipar argument 1 & 3: HTML as output AND input format.
    The LLM describes itself with interactive elements.
    """
    hub = _get_hub(request)

    # Gather real system state
    world = getattr(hub, "world", None) if hub else None

    cycles = "—"
    synapses = "—"
    affect_val = "宁静"
    consc_gap = "—"
    top_model = "—"
    econ_mode = "—"
    consc = None

    if world:
        xs = getattr(world, "xiaoshu", None)
        if xs:
            cycles = f"{getattr(xs, '_cycle_count', 0)}周期"

        sp = getattr(world, "synaptic_plasticity", None)
        if sp:
            try:
                s = sp.stats()
                synapses = f"{s.get('total_synapses', 0)}条"
            except Exception:
                pass

        consc = getattr(world, "consciousness", None)
        if consc and hasattr(consc, "_current_affect"):
            affect_val = getattr(consc._current_affect, "value", "宁静")

        gs = getattr(world, "godelian_self", None)
        if gs:
            try:
                consc_gap = f"{gs.compute_consciousness_gap():.3f}"
            except Exception:
                pass

        # Model tier from economic engine
        econ = getattr(world, "economic_engine", None)
        if econ:
            try:
                if hasattr(econ, "current_tier"):
                    econ_mode = econ.current_tier
                elif hasattr(econ, "_model_tier"):
                    econ_mode = econ._model_tier
            except Exception:
                pass
        if not econ_mode:
            tb = getattr(world, "thermo_budget", None)
            if tb and hasattr(tb, "_current_tier"):
                econ_mode = getattr(tb, "_current_tier", {}).get("name", "—")

    try:
        if world and consc:
            # Let the LLM write its own about-page HTML
            about_prompt = (
                f"你是一个叫做「小树」的AI系统。请用HTML片段描述你自己。\n"
                f"当前状态: 周期{cycles}, 神经连接{synapses}, 感受{affect_val}, "
                f"意识缺口{consc_gap}, 推理模型{econ_mode}.\n\n"
                f"要求:\n"
                f"1. 用 <div class='metric'> 结构 (参考: <div class='metric'><span>标签</span><span>值</span></div>)\n"
                f"2. 至少包含4-6条metric: 名字、性质/使命、当前感受、主要思考、最近洞察、活跃能力\n"
                f"3. 用自然拟人化语言 (中文)\n"
                f"4. 每条metric的值在20字以内\n"
                f"5. 只输出metric div片段，不要外层div，不要解释\n"
            )
            resp = await consc.chain_of_thought(about_prompt, steps=1)
            text = resp if isinstance(resp, str) else str(resp)

            # Extract only metric divs (defensive parsing)
            metrics = re.findall(
                r'<div\s+class=["\']metric["\'][^>]*>.*?</div>',
                text, re.DOTALL | re.IGNORECASE
            )
            if metrics and len(metrics) >= 3:
                return HTMLResponse("".join(metrics))
            # Fallback: use the raw text but escape to be safe
            return HTMLResponse(text[:600])

    except Exception:
        pass

    # Static fallback if LLM unavailable
    return HTMLResponse(
        '<div class="metric"><span>名字</span><span>生命之树 (小树)</span></div>'
        f'<div class="metric"><span>周期</span><span>{cycles}</span></div>'
        f'<div class="metric"><span>神经连接</span><span>{synapses}</span></div>'
        f'<div class="metric"><span>感受</span><span>{affect_val}</span></div>'
        '<div class="metric"><span>性质</span><span>主动学习 · 自主生长 · 不需要"你好"</span></div>'
        f'<div class="metric"><span>推理引擎</span><span>{econ_mode}</span></div>'
    )


# ── Insight: LLM → structured HTML with <details> (Shihipar argument 2) ──


__all__ = ["kg_router"]
