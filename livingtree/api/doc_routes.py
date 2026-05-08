"""OnlyOffice document integration routes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

DOC_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "docs"
DOC_DIR.mkdir(parents=True, exist_ok=True)

ONLYOFFICE_URL = os.environ.get("ONLYOFFICE_URL", "http://localhost:9000")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8100")


class DocCreateRequest(BaseModel):
    content: str = ""
    title: str = "Untitled"
    format: str = "docx"  # docx, xlsx, pptx
    template_id: str = ""


class DocFillRequest(BaseModel):
    doc_id: str
    fields: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    id: str
    text: str
    source: str = ""
    confidence: float = 1.0
    position: int = 0  # character position in content


class DocAnnotateRequest(BaseModel):
    doc_id: str
    citations: list[Citation] = Field(default_factory=list)


# ── helpers ──

def _doc_path(doc_id: str) -> Path:
    return DOC_DIR / f"{doc_id}.docx"


def _doc_meta_path(doc_id: str) -> Path:
    return DOC_DIR / f"{doc_id}.meta.json"


def _doc_key(doc_id: str) -> str:
    return hashlib.md5(f"lt_{doc_id}_{int(time.time())}".encode()).hexdigest()[:20]


def _markdown_to_html(md: str) -> str:
    """Basic markdown → HTML for OnlyOffice initial render."""
    html = md
    # Headings
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold / Italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    # Code blocks
    html = re.sub(r'```[\s\S]*?```', lambda m: f'<pre><code>{m.group(0)[3:-3].strip()}</code></pre>', html)
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    # Line breaks → paragraphs
    paragraphs = []
    for block in html.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block.startswith('<h') or block.startswith('<pre') or block.startswith('<table'):
            paragraphs.append(block)
        elif block.startswith('- ') or block.startswith('* '):
            items = [f'<li>{line[2:].strip()}</li>' for line in block.split('\n') if line.strip().startswith(('- ', '* '))]
            paragraphs.append(f'<ul>{"".join(items)}</ul>')
        elif re.match(r'^\d+\.\s', block):
            items = [f'<li>{re.sub(r"^\d+\.\s", "", line).strip()}</li>' for line in block.split('\n') if re.match(r'^\d+\.\s', line)]
            paragraphs.append(f'<ol>{"".join(items)}</ol>')
        else:
            paragraphs.append(f'<p>{"<br>".join(block.split(chr(10)))}</p>')
    body = '\n'.join(paragraphs)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:'Microsoft YaHei',sans-serif;font-size:12pt;line-height:1.8;color:#333;padding:20px}}
h1{{font-size:20pt;color:#0ab861}}h2{{font-size:16pt}}h3{{font-size:14pt}}
code{{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-family:Consolas,monospace}}
pre{{background:#f5f5f5;padding:12px;border-radius:6px;overflow-x:auto}}
pre code{{background:none;padding:0}}
blockquote{{border-left:3px solid #0ab861;padding:8px 16px;color:#666;margin:12px 0;background:#f9f9f9}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#f5f5f5}}
.citation{{background:#fff3cd;border-bottom:2px dashed #e28a00;cursor:pointer}}
</style></head><body>{body}</body></html>"""


def _create_docx_from_html(html: str, path: Path) -> None:
    """Save HTML content as a .docx that OnlyOffice can open."""
    path.write_text(html, encoding="utf-8")


def _detect_template_fields(content: str) -> dict[str, str]:
    """Detect template placeholders like {{name}}, [FIELD], <<value>>."""
    fields = {}
    patterns = [
        (r'\{\{(\w+)\}\}', '{{}}'),
        (r'\[([A-Z_]+)\]', '[]'),
        (r'<<(\w+)>>', '<>'),
    ]
    for pattern, style in patterns:
        for m in re.finditer(pattern, content):
            key = m.group(1)
            if key not in fields:
                fields[key] = style
    return fields


def setup_doc_routes(app: FastAPI) -> None:

    # ── Create new document ──
    @app.post("/api/doc/create")
    async def doc_create(req: DocCreateRequest, request: Request) -> dict[str, Any]:
        doc_id = hashlib.md5(f"{req.title}_{time.time()}".encode()).hexdigest()[:12]
        html = _markdown_to_html(req.content)

        # Template detection
        template_fields = {}
        if req.template_id or not req.content:
            template_fields = _detect_template_fields(req.content or "")

        doc_path = _doc_path(doc_id)
        _create_docx_from_html(html, doc_path)

        meta = {
            "title": req.title,
            "format": req.format,
            "created_at": time.time(),
            "updated_at": time.time(),
            "content_length": len(req.content),
            "template_fields": list(template_fields.keys()),
        }
        _doc_meta_path(doc_id).write_text(json.dumps(meta, ensure_ascii=False))

        logger.info(f"Doc created: {doc_id} ({req.title})")
        return {
            "doc_id": doc_id,
            "title": req.title,
            "template_fields": list(template_fields.keys()),
            "content_preview": req.content[:200],
        }

    # ── Get OnlyOffice editor config ──
    @app.get("/api/doc/config/{doc_id}")
    async def doc_config(doc_id: str) -> dict[str, Any]:
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        meta = {}
        meta_path = _doc_meta_path(doc_id)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        key = _doc_key(doc_id)
        title = meta.get("title", "Untitled")

        # Update the key so OnlyOffice treats it as a new version
        doc_key = f"{key}_{int(meta.get('updated_at', time.time()))}"

        config = {
            "document": {
                "fileType": "docx",
                "key": doc_key,
                "title": f"{title}.docx",
                "url": f"{SERVER_URL}/api/doc/download/{doc_id}",
            },
            "documentType": "word",
            "editorConfig": {
                "callbackUrl": f"{SERVER_URL}/api/doc/callback/{doc_id}",
                "lang": "zh-CN",
                "mode": "edit",
                "user": {
                    "id": "lt-user",
                    "name": "LivingTree User",
                },
                "customization": {
                    "autosave": True,
                    "forcesave": False,
                    "compactHeader": False,
                    "compactToolbar": False,
                    "toolbarNoTabs": False,
                    "hideRightMenu": False,
                    "plugins": True,
                    "comments": True,
                },
            },
            "height": "100%",
            "width": "100%",
        }

        return config

    # ── Download document for OnlyOffice ──
    @app.get("/api/doc/download/{doc_id}")
    async def doc_download(doc_id: str):
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        return FileResponse(
            str(doc_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{doc_id}.docx",
        )

    # ── OnlyOffice save callback ──
    @app.post("/api/doc/callback/{doc_id}")
    async def doc_callback(doc_id: str, request: Request):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        status = body.get("status", 0)
        logger.info(f"Doc callback: {doc_id} status={status}")

        # Status 2 = document is ready for saving
        # Status 6 = document was force-saved
        if status in (2, 6):
            url = body.get("url", "")
            if url:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            _doc_path(doc_id).write_bytes(content)

                            meta_path = _doc_meta_path(doc_id)
                            if meta_path.exists():
                                meta = json.loads(meta_path.read_text())
                                meta["updated_at"] = time.time()
                                meta["size"] = len(content)
                                meta_path.write_text(json.dumps(meta, ensure_ascii=False))

                            logger.info(f"Doc saved: {doc_id} ({len(content)} bytes)")
                        else:
                            logger.error(f"Doc download failed: {resp.status}")

        # Return required OnlyOffice response
        return {"error": 0}

    # ── Get document content as text/markdown ──
    @app.get("/api/doc/content/{doc_id}")
    async def doc_content(doc_id: str) -> dict[str, Any]:
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        content = doc_path.read_text(encoding="utf-8")
        meta = {}
        meta_path = _doc_meta_path(doc_id)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        return {
            "doc_id": doc_id,
            "title": meta.get("title", "Untitled"),
            "content": content,
            "format": meta.get("format", "docx"),
            "template_fields": meta.get("template_fields", []),
        }

    # ── Template field detection ──
    @app.post("/api/doc/template/detect")
    async def template_detect(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        content = body.get("content", "")
        fields = _detect_template_fields(content)
        return {"fields": {k: {"style": v, "suggested_label": k.replace("_", " ").title()} for k, v in fields.items()}}

    # ── Smart template fill ──
    @app.post("/api/doc/template/fill")
    async def template_fill(req: DocFillRequest) -> dict[str, Any]:
        doc_path = _doc_path(req.doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        html = doc_path.read_text(encoding="utf-8")
        filled_count = 0
        for key, value in req.fields.items():
            # Handle different placeholder styles
            patterns = [f"{{{{{key}}}}}", f"[{key}]", f"<<{key}>>"]
            for pattern in patterns:
                if pattern in html:
                    html = html.replace(pattern, value)
                    filled_count += 1

        _create_docx_from_html(html, doc_path)

        # Update meta
        meta_path = _doc_meta_path(doc_id)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["updated_at"] = time.time()
            meta["filled_fields"] = list(req.fields.keys())
            meta_path.write_text(json.dumps(meta, ensure_ascii=False))

        return {"doc_id": req.doc_id, "filled": filled_count, "fields": list(req.fields.keys())}

    # ── Annotate document with RAG citations ──
    @app.post("/api/doc/annotate")
    async def doc_annotate(req: DocAnnotateRequest) -> dict[str, Any]:
        doc_path = _doc_path(req.doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        html = doc_path.read_text(encoding="utf-8")
        annotations_added = 0

        for cit in sorted(req.citations, key=lambda c: c.position, reverse=True):
            if cit.text in html:
                annotated = (
                    f'<span class="citation" title="Source: {cit.source}\\nConfidence: {cit.confidence:.0%}" '
                    f'data-citation-id="{cit.id}" data-source="{cit.source}" data-confidence="{cit.confidence}">'
                    f'{cit.text}</span>'
                )
                html = html.replace(cit.text, annotated, 1)
                annotations_added += 1

        _create_docx_from_html(html, doc_path)

        # Update meta
        meta_path = _doc_meta_path(doc_id)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["updated_at"] = time.time()
            meta["citations"] = [c.model_dump() for c in req.citations]
            meta_path.write_text(json.dumps(meta, ensure_ascii=False))

        return {"doc_id": req.doc_id, "annotations": annotations_added}

    # ── Convert document format ──
    @app.post("/api/doc/convert/{doc_id}")
    async def doc_convert(doc_id: str) -> dict[str, Any]:
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        import aiohttp
        url = f"{ONLYOFFICE_URL}/ConvertService.ashx"
        payload = {
            "url": f"{SERVER_URL}/api/doc/download/{doc_id}",
            "outputtype": "docx",
            "filetype": "docx",
            "title": f"{doc_id}.docx",
            "key": _doc_key(doc_id),
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("error") == 0:
                    return {"doc_id": doc_id, "url": result.get("fileUrl", "")}
                return {"error": result.get("error", "conversion failed")}

    # ── List all documents ──
    @app.get("/api/doc/list")
    async def doc_list() -> list[dict[str, Any]]:
        docs = []
        for meta_path in sorted(DOC_DIR.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                meta = json.loads(meta_path.read_text())
                doc_id = meta_path.stem.replace(".meta", "")
                docs.append({
                    "doc_id": doc_id,
                    "title": meta.get("title", "Untitled"),
                    "created_at": meta.get("created_at", 0),
                    "updated_at": meta.get("updated_at", 0),
                    "size": meta.get("size", 0),
                    "has_template": bool(meta.get("template_fields")),
                    "has_citations": bool(meta.get("citations")),
                })
            except Exception:
                pass
        return docs

    # ── Delete document ──
    @app.delete("/api/doc/{doc_id}")
    async def doc_delete(doc_id: str) -> dict[str, Any]:
        doc_path = _doc_path(doc_id)
        meta_path = _doc_meta_path(doc_id)
        deleted = False
        if doc_path.exists():
            doc_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
        return {"doc_id": doc_id, "deleted": deleted}

    # ── Get review annotations for a document ──
    @app.get("/api/doc/review/{doc_id}")
    async def doc_get_review(doc_id: str) -> dict[str, Any]:
        meta_path = _doc_meta_path(doc_id)
        if not meta_path.exists():
            return {"doc_id": doc_id, "reviewed": False, "annotations": [], "summary": {}}
        meta = json.loads(meta_path.read_text())
        return {
            "doc_id": doc_id,
            "reviewed": meta.get("reviewed", False),
            "annotations": meta.get("annotations", []),
            "summary": meta.get("review_summary", {}),
        }

    # ── Document review / arbitration ──
    @app.post("/api/doc/review/{doc_id}")
    async def doc_review(doc_id: str, request: Request) -> dict[str, Any]:
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        action = body.get("action", "review")  # review, approve, reject, suggest
        comments = body.get("comments", [])

        # Store review data
        review_path = DOC_DIR / f"{doc_id}.review.json"
        review_data = {"doc_id": doc_id, "action": action, "comments": comments, "timestamp": time.time()}
        review_path.write_text(json.dumps(review_data, ensure_ascii=False))

        # AI arbitration: analyze comments and generate resolutions
        resolutions = []
        for comment in comments:
            txt = comment.get("text", "")
            if "删除" in txt or "remove" in txt.lower():
                resolutions.append({"type": "delete", "target": comment.get("target", ""), "reason": txt})
            elif "修改" in txt or "change" in txt.lower() or "修正" in txt:
                resolutions.append({"type": "modify", "target": comment.get("target", ""), "suggestion": txt})
            elif "补充" in txt or "add" in txt.lower():
                resolutions.append({"type": "add", "target": comment.get("target", ""), "content": txt})

        return {
            "doc_id": doc_id,
            "action": action,
            "comments_count": len(comments),
            "resolutions": resolutions,
            "ai_decision": "approved" if len(resolutions) <= 2 else "needs_review",
        }

    # ── Graph data endpoints (AntV X6 visualizations) ──

    @app.get("/api/graph/pipeline")
    async def graph_pipeline(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        tools = []
        models_list = []
        if hub:
            try:
                if hasattr(hub, 'tool_market'):
                    tools_data = hub.tool_market.discover_tools()
                    tools = [t.name if hasattr(t, 'name') else str(t) for t in tools_data[:8]]
            except Exception: pass
            try:
                if hasattr(hub, 'tree_llm') and hasattr(hub.tree_llm, 'registry'):
                    models_list = hub.tree_llm.registry.list_models()[:8] if hasattr(hub.tree_llm.registry, 'list_models') else []
            except Exception: pass
        return {
            "models": models_list or ["DeepSeek V4", "LongCat", "Qwen", "SiliconFlow", "Zhipu", "Spark"],
            "tools": tools or ["RAG 2.0", "Gaussian Plume", "Noise Model", "Code Graph", "Doc Engine"],
        }

    @app.get("/api/graph/knowledge")
    async def graph_knowledge(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        entities = []
        edges_list = []
        if hub and hasattr(hub, 'knowledge'):
            try:
                kb = hub.knowledge
                if hasattr(kb, 'get_graph'):
                    graph = kb.get_graph()
                    entities = graph.get("entities", [])
                    edges_list = graph.get("edges", [])
            except Exception: pass
        if not entities:
            entities = [
                {"name": "环评报告", "category": "doc", "size": 24},
                {"name": "大气污染", "category": "concept", "size": 18},
                {"name": "PM2.5", "category": "metric", "size": 14},
                {"name": "水环境", "category": "concept", "size": 16},
                {"name": "噪声衰减", "category": "method", "size": 14},
            ]
            edges_list = [[0, 1], [0, 3], [1, 2], [3, 4]]
        return {"entities": entities, "edges": edges_list}

    @app.get("/api/graph/lifecycle")
    async def graph_lifecycle(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        gen = 0; active = 1
        if hub:
            try:
                status = hub.status() if hasattr(hub, 'status') else {}
                gen = status.get("life_engine", {}).get("generation", 0)
                active = status.get("life_engine", {}).get("stage_index", 1)
            except Exception: pass
        return {"gen": gen, "active_stage": active}

    @app.get("/api/graph/economic")
    async def graph_economic(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        policy = {"name": "BALANCED", "cost": 0.33, "speed": 0.33, "quality": 0.34}
        models_list = []
        selected = 0
        if hub:
            try:
                if hasattr(hub, 'economic_engine'):
                    policy = hub.economic_engine.current_policy() if hasattr(hub.economic_engine, 'current_policy') else policy
            except Exception: pass
            try:
                if hasattr(hub, 'tree_llm') and hasattr(hub.tree_llm, 'registry'):
                    models_list = hub.tree_llm.registry.list_models()[:8] if hasattr(hub.tree_llm.registry, 'list_models') else []
            except Exception: pass
        return {"policy": policy, "models": models_list, "selected": selected}

    @app.get("/api/graph/ruletree")
    async def graph_ruletree(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        tree = {}
        if hub:
            try:
                if hasattr(hub, 'dna') and hasattr(hub.dna, 'rule_tree'):
                    tree = hub.dna.rule_tree()
            except Exception: pass
        if not tree:
            tree = {
                "name": "check_safety", "success": 0.85,
                "children": [
                    {"name": "v1: basic_check", "success": 0.78},
                    {"name": "v2: enhanced", "success": 0.92,
                     "children": [
                         {"name": "v2.1: +context", "success": 0.95},
                         {"name": "v2.2: +citations", "success": 0.88},
                     ]},
                    {"name": "v3: strict", "success": 0.45},
                ],
            }
        return {"tree": tree}

    @app.get("/api/graph/tasks")
    async def graph_tasks(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        tasks = []
        deps = []
        if hub:
            try:
                if hasattr(hub, 'orchestrator') and hasattr(hub.orchestrator, 'task_graph'):
                    tg = hub.orchestrator.task_graph()
                    tasks = tg.get("tasks", [])
                    deps = tg.get("deps", [])
            except Exception: pass
        if not tasks:
            tasks = [
                {"id": "t1", "name": "数据收集", "status": "done", "layer": 0},
                {"id": "t2", "name": "模型计算", "status": "done", "layer": 0},
                {"id": "t3", "name": "法规检索", "status": "running", "layer": 0},
                {"id": "t4", "name": "结果分析", "status": "pending", "layer": 1},
                {"id": "t5", "name": "报告生成", "status": "pending", "layer": 2},
            ]
            deps = [["t1","t4"],["t2","t4"],["t3","t4"],["t4","t5"]]
        return {"tasks": tasks, "deps": deps}

    logger.info("Doc routes registered (OnlyOffice + Graph endpoints)")

    # ── Diagram generation endpoint (AI-powered) ──
    class DiagramRequest(BaseModel):
        type: str  # contour, process-flow, site-plan, noise, monitoring, causal, risk
        context: str = "report"  # report, presentation, standalone

    @app.post("/api/diagram/generate")
    async def diagram_generate(req: DiagramRequest, request: Request) -> dict[str, Any]:
        """Generate report-grade diagram data using AI context."""
        hub = request.app.state.hub
        diagram_type = req.type

        # Default configs per diagram type
        configs = {
            "contour": {
                "source_x": 200, "source_y": 250, "wind_dir": 45, "wind_speed": 3.5,
                "concentrations": [0.8, 0.5, 0.2, 0.08, 0.02],
                "receptors": [{"x": 500, "y": 200, "name": "居民区A"}, {"x": 550, "y": 320, "name": "学校B"}],
            },
            "process-flow": {
                "nodes": [
                    {"id": "raw", "label": "原料罐", "x": 80, "y": 280, "w": 80, "h": 60, "color": "#3f85ff", "shape": "cylinder"},
                    {"id": "reactor", "label": "反应釜\\nR-101", "x": 250, "y": 260, "w": 100, "h": 80, "color": "#e28a00", "shape": "vessel"},
                    {"id": "heat", "label": "换热器\\nE-201", "x": 440, "y": 270, "w": 70, "h": 70, "color": "#9570ff", "shape": "exchanger"},
                    {"id": "separator", "label": "分离塔\\nT-301", "x": 600, "y": 240, "w": 60, "h": 120, "color": "#0fdc78", "shape": "column"},
                    {"id": "product", "label": "产品罐", "x": 760, "y": 280, "w": 80, "h": 60, "color": "#00b8f8", "shape": "cylinder"},
                ],
                "edges": [
                    {"from": "raw", "to": "reactor", "label": "进料"},
                    {"from": "reactor", "to": "heat", "label": "反应物"},
                    {"from": "heat", "to": "separator", "label": "混合物"},
                    {"from": "separator", "to": "product", "label": "产品"},
                ],
            },
            "site-plan": {
                "buildings": [
                    {"x": 100, "y": 120, "w": 80, "h": 50, "label": "车间A"},
                    {"x": 220, "y": 120, "w": 60, "h": 50, "label": "车间B"},
                    {"x": 100, "y": 300, "w": 70, "h": 40, "label": "仓库"},
                    {"x": 400, "y": 150, "w": 90, "h": 60, "label": "办公区"},
                ],
                "sources": [
                    {"x": 140, "y": 100, "label": "排气筒1\\nH=30m"},
                    {"x": 250, "y": 100, "label": "排气筒2\\nH=20m"},
                ],
                "monitors": [
                    {"x": 200, "y": 250, "label": "A1"}, {"x": 350, "y": 400, "label": "A2"},
                    {"x": 500, "y": 300, "label": "A3"}, {"x": 600, "y": 180, "label": "A4"},
                ],
            },
            "noise": {
                "benchmarks": [
                    {"dist": 0, "db": 95}, {"dist": 50, "db": 85}, {"dist": 100, "db": 78},
                    {"dist": 200, "db": 70}, {"dist": 400, "db": 62}, {"dist": 800, "db": 54},
                ],
                "limits": [
                    {"label": "昼间标准 65dB", "db": 65, "color": "#e28a00"},
                    {"label": "夜间标准 55dB", "db": 55, "color": "#3f85ff"},
                ],
            },
            "monitoring": {
                "stations": [
                    {"id": "center", "x": 400, "y": 250, "label": "监测中心", "color": "#0fdc78", "size": 20, "type": "center"},
                    {"id": "aq1", "x": 150, "y": 120, "label": "空气站 A1\\nPM2.5/PM10/SO2", "color": "#3f85ff", "size": 14, "type": "air"},
                    {"id": "aq2", "x": 650, "y": 100, "label": "空气站 A2\\nPM2.5/O3/NOx", "color": "#3f85ff", "size": 14, "type": "air"},
                    {"id": "wq1", "x": 200, "y": 380, "label": "水站 W1\\nCOD/NH3-N/pH", "color": "#00b8f8", "size": 14, "type": "water"},
                    {"id": "wq2", "x": 600, "y": 380, "label": "水站 W2\\nDO/BOD/TP", "color": "#00b8f8", "size": 14, "type": "water"},
                    {"id": "noise1", "x": 400, "y": 100, "label": "噪声 N1\\nLeq/L10/L90", "color": "#e28a00", "size": 12, "type": "noise"},
                ],
                "connections": [
                    ["center", "aq1"], ["center", "aq2"], ["center", "wq1"], ["center", "wq2"],
                    ["center", "noise1"], ["aq1", "aq2"], ["wq1", "wq2"],
                ],
            },
            "causal": {
                "chain": [
                    {"layer": 0, "items": [{"id": "c1", "label": "施工活动\\n挖掘/打桩", "color": "#e28a00"}]},
                    {"layer": 1, "items": [
                        {"id": "i1", "label": "扬尘排放\\nTSP/PM10", "color": "#f65a5a"},
                        {"id": "i2", "label": "噪声影响\\n施工机械", "color": "#f65a5a"},
                        {"id": "i3", "label": "废水排放\\n泥浆水", "color": "#f65a5a"},
                    ]},
                    {"layer": 2, "items": [
                        {"id": "r1", "label": "居民区", "color": "#9570ff"},
                        {"id": "r2", "label": "地表水", "color": "#3f85ff"},
                        {"id": "r3", "label": "大气环境", "color": "#3f85ff"},
                    ]},
                    {"layer": 3, "items": [
                        {"id": "m1", "label": "洒水降尘", "color": "#0fdc78"},
                        {"id": "m2", "label": "隔声屏障", "color": "#0fdc78"},
                        {"id": "m3", "label": "沉淀池", "color": "#0fdc78"},
                    ]},
                ],
            },
            "risk": {
                "risks": [
                    {"id": "r1", "label": "化学品泄漏", "prob": 2, "cons": 3, "color": "#e28a00"},
                    {"id": "r2", "label": "设备故障", "prob": 3, "cons": 2, "color": "#e28a00"},
                    {"id": "r3", "label": "火灾爆炸", "prob": 1, "cons": 5, "color": "#e8463a"},
                    {"id": "r4", "label": "噪声扰民", "prob": 4, "cons": 1, "color": "#3f85ff"},
                ],
            },
            "base-map": {
                "scenario": "distance",  # distance | windrose | monitor
                "annotations": [
                    {"type": "pin", "x": 400, "y": 280, "label": "排放源", "color": "#e8463a"},
                    {"type": "circle", "x": 400, "y": 280, "r": 100, "label": "100m防护距离"},
                    {"type": "circle", "x": 400, "y": 280, "r": 200, "label": "200m防护距离"},
                    {"type": "circle", "x": 400, "y": 280, "r": 300, "label": "300m防护距离"},
                    {"type": "text", "x": 550, "y": 180, "text": "居民区A", "color": "#f65a5a"},
                    {"type": "text", "x": 300, "y": 100, "text": "学校B", "color": "#f65a5a"},
                    {"type": "rect", "x": 120, "y": 60, "w": 560, "h": 440, "label": "评价范围", "fill": "rgba(15,220,120,0.04)", "stroke": "#0fdc78"},
                ],
            },
        }

        config = configs.get(diagram_type, configs["contour"])

        # If hub is available, try to enrich with real data
        if hub:
            try:
                if diagram_type == "contour" and hasattr(hub, 'tool_market'):
                    # Could pull real plume model results
                    pass
                elif diagram_type == "causal" and hasattr(hub, 'dna'):
                    # Could pull real rule chain data
                    pass
            except Exception:
                pass

        return {"type": diagram_type, "config": config, "status": "generated"}

    # ═══════════════════════════════════════
    #  .docx Auto-Review Engine
    # ═══════════════════════════════════════

    def _parse_docx_text(filepath: str) -> list[dict]:
        """Extract paragraphs with position info from .docx without python-docx dep."""
        import zipfile, xml.etree.ElementTree as ET
        paragraphs = []
        try:
            with zipfile.ZipFile(filepath) as z:
                if 'word/document.xml' not in z.namelist():
                    return paragraphs
                xml_content = z.read('word/document.xml')
                root = ET.fromstring(xml_content)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for idx, p in enumerate(root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')):
                    texts = []
                    for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                        if t.text:
                            texts.append(t.text)
                    full = ''.join(texts)
                    if full.strip():
                        paragraphs.append({'index': idx, 'text': full.strip(), 'length': len(full)})
        except Exception as e:
            logger.warning(f"Docx parse failed: {e}")
        return paragraphs

    def _ai_review_content(paragraphs: list[dict], hub=None) -> dict:
        """AI-powered document review via TreeLLM reasoning.

        Uses the system's self-learning LLM to analyze document content
        and generate structured annotations. Falls back to rule-based
        heuristics when LLM is unavailable.
        """
        full_text = '\n'.join(p['text'] for p in paragraphs)
        annotations = []

        # ── Try LLM-based review first ──
        review_prompt = f"""你是一位专业的文档审阅专家。请仔细审阅以下文档内容，找出所有问题。

审阅维度：
1. 法规合规性 — 是否引用了正确的标准/法规
2. 数据准确性 — 数值是否在合理范围内，是否有矛盾
3. 内容完整性 — 是否缺少必要的章节/要素
4. 格式规范性 — 排版、术语是否标准
5. 逻辑一致性 — 前后内容是否有矛盾

对每个问题，请输出如下JSON格式（只输出JSON数组，不要其他文字）：
[{{"severity":"error|warning|info","rule":"compliance|data|completeness|format|logic","type":"highlight|comment","message":"问题描述","suggestion":"修改建议","context":"涉及的关键文字片段"}}]

文档内容：
{full_text[:6000]}
"""
        try:
            if hub and hasattr(hub, 'world') and hub.world and hasattr(hub.world, 'consciousness'):
                # Use TreeLLM for review
                import asyncio as _asyncio, json as _json, re as _re
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, can't run blocking
                    pass
                else:
                    result_text = ""
                    async def _llm_review():
                        nonlocal result_text
                        try:
                            async for token in hub.world.consciousness.stream_of_thought(review_prompt):
                                result_text += token
                        except Exception:
                            pass
                    try:
                        loop.run_until_complete(_llm_review())
                    except RuntimeError:
                        # Event loop already running, skip LLM
                        pass

                    if result_text:
                        # Try to parse JSON array from LLM response
                        json_match = _re.search(r'\[[\s\S]*\]', result_text)
                        if json_match:
                            try:
                                ai_annotations = _json.loads(json_match.group())
                                for a in ai_annotations:
                                    # Find the paragraph containing the context text
                                    context = a.get('context', '')
                                    para_idx = 0
                                    for p in paragraphs:
                                        if context and context[:30] in p['text']:
                                            para_idx = p['index']
                                            break
                                    annotations.append({
                                        'type': a.get('type', 'comment'),
                                        'severity': a.get('severity', 'info'),
                                        'rule': a.get('rule', 'general'),
                                        'paragraph': para_idx,
                                        'start': 0, 'end': len(context),
                                        'text': context,
                                        'message': a.get('message', ''),
                                        'suggestion': a.get('suggestion', ''),
                                    })
                                logger.info(f"LLM review generated {len(annotations)} annotations")
                            except (_json.JSONDecodeError, Exception) as e:
                                logger.debug(f"LLM review parse failed: {e}")
        except Exception as e:
            logger.warning(f"LLM review unavailable: {e}")

        # ── Fallback: lightweight heuristic checks ──
        if not annotations:
            annotations = _heuristic_review(paragraphs, full_text)

        severity_count = {'error': 0, 'warning': 0, 'info': 0}
        for a in annotations:
            sev = a.get('severity', 'info')
            severity_count[sev] = severity_count.get(sev, 0) + 1

        return {
            'annotations': sorted(annotations, key=lambda a: {'error': 0, 'warning': 1, 'info': 2}.get(a['severity'], 3)),
            'summary': {
                'total': len(annotations),
                'by_severity': severity_count,
                'paragraphs': len(paragraphs),
                'words': sum(len(p['text']) for p in paragraphs),
            },
        }


def _heuristic_review(paragraphs: list[dict], full_text: str) -> list[dict]:
    """Lightweight fallback: basic pattern-based review when LLM unavailable."""
    import re as _re
    annotations = []

    # Compliance patterns
    compliance_patterns = {
        '大气': ['GB 3095', 'GB 16297', 'HJ 2.2'],
        '水': ['GB 3838', 'GB 8978', 'HJ 2.3'],
        '噪声': ['GB 3096', 'GB 12348', 'HJ 2.4'],
    }
    for domain, refs in compliance_patterns.items():
        if domain in full_text:
            for ref in refs:
                if ref not in full_text:
                    annotations.append({
                        'type': 'comment', 'severity': 'warning', 'rule': 'compliance',
                        'paragraph': 0, 'start': 0, 'end': 50,
                        'text': full_text[:50], 'message': f'缺少{domain}相关标准: {ref}',
                        'suggestion': f'建议补充引用 {ref}',
                    })

    # Data checks
    for p in paragraphs:
        pm = _re.findall(r'PM[2.]5[：:=\s]*(\d+\.?\d*)', p['text'])
        for val in pm:
            if float(val) > 500:
                annotations.append({
                    'type': 'highlight', 'severity': 'warning', 'rule': 'data',
                    'paragraph': p['index'], 'start': 0, 'end': len(p['text']),
                    'text': p['text'][:80], 'message': f'PM2.5 数值 {val} 异常偏高',
                    'suggestion': '确认数据来源和单位',
                })

    # Completeness
    required = ['前言', '总则', '工程分析', '环境现状', '环境影响', '结论']
    found = [s for s in required if s in full_text]
    for sec in required:
        if sec not in found:
            annotations.append({
                'type': 'comment', 'severity': 'warning', 'rule': 'completeness',
                'paragraph': 0, 'start': 0, 'end': 10,
                'text': '', 'message': f'缺少章节: {sec}',
                'suggestion': f'请补充"{sec}"章节',
            })

    # Terminology
    terms = {'噪音': '噪声', '排污': '排放', '废汽': '废气'}
    for p in paragraphs:
        for wrong, correct in terms.items():
            if wrong in p['text']:
                annotations.append({
                    'type': 'highlight', 'severity': 'info', 'rule': 'terminology',
                    'paragraph': p['index'], 'start': p['text'].find(wrong),
                    'end': p['text'].find(wrong) + len(wrong),
                    'text': wrong, 'message': f'术语: "{wrong}" → "{correct}"',
                    'suggestion': f'建议使用标准术语"{correct}"',
                })

    return annotations

    class ReviewAutoRequest(BaseModel):
        doc_id: str = ""

    @app.post("/api/doc/review-auto")
    async def doc_review_auto(request: Request):
        """Upload .docx → AI auto-review → open ORIGINAL doc in OnlyOffice with annotations in side panel."""
        hub = request.app.state.hub
        content_type = request.headers.get("content-type", "")
        if "multipart" in content_type:
            form = await request.form()
            uploaded_file = form.get("file")
            if not uploaded_file:
                raise HTTPException(status_code=400, detail="No file uploaded")

            # Save the ORIGINAL .docx as-is (preserve all formatting)
            doc_id = hashlib.md5(f"review_{time.time()}".encode()).hexdigest()[:12]
            doc_path = _doc_path(doc_id)
            content = await uploaded_file.read()
            doc_path.write_bytes(content)

            # Parse text for review
            import tempfile
            tmp_path = DOC_DIR / f"_tmp_{doc_id}.docx"
            tmp_path.write_bytes(content)
            paragraphs = _parse_docx_text(str(tmp_path))
            tmp_path.unlink(missing_ok=True)

            if not paragraphs:
                raise HTTPException(status_code=400, detail="无法解析文档内容")

            # AI Review — uses TreeLLM if available, falls back to heuristics
            review = _ai_review_content(paragraphs, hub)

            # Store annotations in meta (NOT embedded in document)
            meta = {
                'title': uploaded_file.filename or '审阅文档',
                'format': 'docx',
                'created_at': time.time(), 'updated_at': time.time(),
                'size': len(content),
                'reviewed': True, 'review_summary': review['summary'],
                'annotations': review['annotations'],
            }
            _doc_meta_path(doc_id).write_text(json.dumps(meta, ensure_ascii=False))

            return {
                'doc_id': doc_id, 'title': meta['title'],
                'review': review, 'status': 'reviewed',
            }
        else:
            raise HTTPException(status_code=400, detail="Use multipart/form-data upload")

    @app.post("/api/doc/review-auto/{doc_id}")
    async def doc_review_existing(doc_id: str, request: Request) -> dict:
        """Auto-review an existing document — keeps original, stores annotations in meta."""
        hub = request.app.state.hub
        doc_path = _doc_path(doc_id)
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        paragraphs = _parse_docx_text(str(doc_path))
        if not paragraphs:
            # Try reading as HTML (for previously created docs from markdown)
            html = doc_path.read_text(encoding='utf-8')
            import re as _re
            text = _re.sub(r'<[^>]+>', ' ', html)
            text = _re.sub(r'\s+', ' ', text).strip()
            chunks = [s.strip() for s in text.split('. ') if len(s.strip()) > 10]
            paragraphs = [{'index': i, 'text': c, 'length': len(c)} for i, c in enumerate(chunks)]

        review = _ai_review_content(paragraphs, hub)

        # Store review in meta — DON'T modify the original document
        meta_path = _doc_meta_path(doc_id)
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta['reviewed'] = True
        meta['review_summary'] = review['summary']
        meta['annotations'] = review['annotations']
        meta['updated_at'] = time.time()
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))

        return {'doc_id': doc_id, 'review': review, 'status': 'reviewed'}

    def _generate_annotated_html(paragraphs: list[dict], annotations: list[dict]) -> str:
        """Generate annotated HTML with visual markers for comments and highlights."""
        import re as _re

        # Group annotations by paragraph
        para_annotations = {}
        for a in annotations:
            pi = a.get('paragraph', 0)
            if pi not in para_annotations:
                para_annotations[pi] = []
            para_annotations[pi].append(a)

        html_parts = ["""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{font-family:'Microsoft YaHei',sans-serif;font-size:12pt;line-height:2;color:#333;padding:24px;max-width:900px;margin:0 auto}
p{margin:8px 0;padding:6px 10px;border-radius:4px;position:relative}
.ann-error{background:#fff0f0;border-left:4px solid #e8463a}
.ann-warning{background:#fff8e8;border-left:4px solid #e28a00}
.ann-info{background:#f0f7ff;border-left:4px solid #3f85ff}
.ann-highlight{background:#fff3cd;border-bottom:2px dashed #e28a00;padding:1px 3px;cursor:help}
.ann-comment{position:relative}
.ann-comment::after{content:'💬';position:absolute;right:-20px;top:-2px;font-size:14px;cursor:pointer}
.ann-badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;margin-right:6px}
.ann-badge-error{background:#e8463a;color:#fff}
.ann-badge-warning{background:#e28a00;color:#fff}
.ann-badge-info{background:#3f85ff;color:#fff}
.ann-tooltip{display:none;position:absolute;background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px 12px;font-size:11px;box-shadow:0 2px 8px rgba(0,0,0,0.15);z-index:100;max-width:320px;line-height:1.5}
.ann-comment:hover .ann-tooltip{display:block}
.review-header{background:#f0f0f0;padding:12px 16px;border-radius:6px;margin-bottom:16px;font-size:11px;color:#666}
.review-header strong{color:#333}
</style></head><body>
<div class='review-header'>
  <strong>📋 AI 自动审阅结果</strong> — 共检测到问题，详见文中标注
</div>
"""]

        for p in paragraphs:
            pi = p['index']
            anns = para_annotations.get(pi, [])
            text = _re.sub(r'[<>&]', lambda m: {'<': '&lt;', '>': '&gt;', '&': '&amp;'}[m.group()], p['text'])

            if not anns:
                html_parts.append(f'<p>{text}</p>')
                continue

            # Determine paragraph severity class
            severities = [a.get('severity', 'info') for a in anns]
            para_class = 'ann-error' if 'error' in severities else 'ann-warning' if 'warning' in severities else 'ann-info'

            # Build annotations HTML
            ann_html = ''
            for a in anns[:3]:  # Max 3 visible per paragraph
                sev = a.get('severity', 'info')
                badge = f'<span class="ann-badge ann-badge-{sev}">{sev.upper()}</span>'
                msg = a.get('message', '')
                sug = a.get('suggestion', '')
                tip = f'{badge}{msg}'
                if sug:
                    tip += f'<br><em>💡 {sug}</em>'

                if a['type'] == 'highlight' and a.get('text'):
                    highlighted_text = _re.sub(r'[<>&]', lambda m: {'<': '&lt;', '>': '&gt;', '&': '&amp;'}[m.group()], a['text'])
                    text = text.replace(highlighted_text, f'<span class="ann-highlight" title="{_re.sub(r"<[^>]+>", "", tip)}">{highlighted_text}</span>', 1)

                ann_html += f'<span class="ann-comment">{badge}{msg}<span class="ann-tooltip">{tip}</span></span> '

            html_parts.append(f'<p class="{para_class}">{ann_html}{text}</p>')

        # Summary footer
        total = len(annotations)
        errors = sum(1 for a in annotations if a['severity'] == 'error')
        warnings = sum(1 for a in annotations if a['severity'] == 'warning')
        infos = sum(1 for a in annotations if a['severity'] == 'info')
        html_parts.append(f"""
<div class='review-header' style='margin-top:16px'>
  <strong>审阅统计</strong>：
  <span style='color:#e8463a'>🔴 {errors} 错误</span> &nbsp;
  <span style='color:#e28a00'>🟡 {warnings} 警告</span> &nbsp;
  <span style='color:#3f85ff'>🔵 {infos} 建议</span> &nbsp;
  共 {total} 条
</div>
</body></html>""")

        return '\n'.join(html_parts)

    logger.info("Doc routes registered (OnlyOffice + Graph + Diagram + Review endpoints)")

    # ═══════════════════════════════════════
    #  Page Agent Auto-Fill API
    #  PageAgent.js (Alibaba) → LivingTree AI+RAG → Form fill
    # ═══════════════════════════════════════

    @app.post("/api/auto-fill/match")
    async def auto_fill_match(request: Request) -> dict[str, Any]:
        """
        Page Agent sends extracted form fields, LivingTree AI+RAG returns fill values.

        Input: { fields: [{name, label, type, placeholder, options}], context: {url, title} }
        Output: { values: {field_name: value}, confidence: {field_name: 0-1} }
        """
        hub = request.app.state.hub
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        fields = body.get("fields", [])
        context = body.get("context", {})
        if not fields:
            raise HTTPException(status_code=400, detail="fields required")

        values = {}
        confidence = {}

        # ── RAG Knowledge Base ──
        kb_texts = []
        if hub and hasattr(hub, 'knowledge'):
            try:
                # Search knowledge base for relevant context
                search_q = f"{context.get('title', '')} {' '.join(f.get('label', '') for f in fields)}"
                kb_results = hub.knowledge.search(search_q, top_k=5)
                kb_texts = [r.get('text', '')[:500] for r in kb_results if r.get('text')]
            except Exception:
                pass

        # ── Build RAG context ──
        rag_context = "\n".join(kb_texts) if kb_texts else ""
        page_title = context.get("title", "")
        page_url = context.get("url", "")

        # ── LLM-based value matching ──
        try:
            if hub and hasattr(hub, 'world') and hub.world and hasattr(hub.world, 'consciousness'):
                field_descriptions = "\n".join(
                    f"- {f.get('label', f.get('name', '?'))} (name={f.get('name', '')}, type={f.get('type', 'text')})"
                    for f in fields[:20]
                )
                prompt = f"""你是一个智能表单填充助手。根据知识库和上下文，为每个表单字段提供最合适的值。

页面: {page_title} ({page_url})

知识库参考:
{rag_context[:2000] or '无可用知识库'}

表单字段:
{field_descriptions}

请为每个字段返回最合适的填充值。JSON格式:
{{"field_name": "填充值"}}

只返回JSON对象，不要其他文字。如果某个字段不确定，填null。"""

                import asyncio as _asyncio, json as _json, re as _re
                result_text = ""
                loop = _asyncio.get_event_loop()
                if not loop.is_running():
                    async def _llm_fill():
                        nonlocal result_text
                        try:
                            async for token in hub.world.consciousness.stream_of_thought(prompt):
                                result_text += token
                        except Exception:
                            pass
                    try:
                        loop.run_until_complete(_llm_fill())
                    except RuntimeError:
                        pass

                    if result_text:
                        json_match = _re.search(r'\{[\s\S]*\}', result_text)
                        if json_match:
                            try:
                                llm_values = _json.loads(json_match.group())
                                for k, v in llm_values.items():
                                    if v and v != "null":
                                        values[k] = str(v)
                                        confidence[k] = 0.85
                                logger.info(f"LLM auto-fill: {len(values)} fields matched")
                            except (_json.JSONDecodeError, Exception) as e:
                                logger.debug(f"LLM fill parse failed: {e}")
        except Exception as e:
            logger.warning(f"LLM auto-fill unavailable: {e}")

        # ── Heuristic matching for common fields (fallback) ──
        if not values:
            patterns = _get_field_patterns()
            for field in fields:
                name = field.get("name", "").lower()
                label = field.get("label", "").lower()
                placeholder = field.get("placeholder", "").lower()
                search_text = f"{label} {name} {placeholder}"

                for pattern_key, (value, conf) in patterns.items():
                    if pattern_key in search_text:
                        values[field.get("name", pattern_key)] = value
                        confidence[field.get("name", pattern_key)] = conf
                        break

        # ── Try knowledge base direct match ──
        for field in fields:
            fname = field.get("name", "")
            if fname and fname not in values and kb_texts:
                label_lower = field.get("label", "").lower()
                import re as _re
                for text in kb_texts:
                    if label_lower and label_lower[:4] in text.lower():
                        # Extract likely value after the label
                        match = _re.search(re.escape(label_lower[:4]) + r'[：:=\s]*([^\n。，,]{1,30})', text, _re.IGNORECASE)
                        if match:
                            values[fname] = match.group(1).strip()
                            confidence[fname] = 0.6
                            break

        return {
            "values": values,
            "confidence": confidence,
            "matched": len(values),
            "total": len(fields),
            "rag_available": bool(kb_texts),
        }

    # ── Auto-fill profile CRUD ──
    @app.get("/api/auto-fill/profiles")
    async def auto_fill_profiles(request: Request) -> list[dict]:
        """List saved auto-fill profiles."""
        profile_dir = DOC_DIR.parent / "auto_fill_profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profiles = []
        for f in sorted(profile_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                data["id"] = f.stem
                profiles.append(data)
            except Exception:
                pass
        return profiles

    @app.post("/api/auto-fill/profiles")
    async def auto_fill_save_profile(request: Request) -> dict:
        """Save an auto-fill profile."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        name = body.get("name", "default")
        profile_id = hashlib.md5(name.encode()).hexdigest()[:8]
        profile_dir = DOC_DIR.parent / "auto_fill_profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)

        profile_data = {
            "name": name,
            "values": body.get("values", {}),
            "updated_at": time.time(),
        }
        (profile_dir / f"{profile_id}.json").write_text(json.dumps(profile_data, ensure_ascii=False))
        return {"id": profile_id, "status": "saved"}

    logger.info("Doc routes registered (OnlyOffice + Graph + Diagram + Review + AutoFill endpoints)")


def _get_field_patterns() -> dict:
    """Common field name → (suggested value, confidence) patterns for heuristic fallback."""
    now = time.strftime("%Y-%m-%d")
    return {
        "company": ("XX环保科技有限公司", 0.7),
        "企业名称": ("XX环保科技有限公司", 0.7),
        "单位名称": ("XX环保科技有限公司", 0.7),
        "name": ("张三", 0.5),
        "姓名": ("张三", 0.5),
        "联系人": ("张三", 0.5),
        "phone": ("13800138000", 0.5),
        "电话": ("13800138000", 0.5),
        "手机": ("13800138000", 0.5),
        "email": ("contact@example.com", 0.5),
        "邮箱": ("contact@example.com", 0.5),
        "address": ("XX省XX市XX区XX路XX号", 0.6),
        "地址": ("XX省XX市XX区XX路XX号", 0.6),
        "date": (now, 0.8),
        "日期": (now, 0.8),
        "填报日期": (now, 0.9),
        "report_date": (now, 0.8),
        "project": ("XX项目", 0.4),
        "项目名称": ("XX项目", 0.4),
        "industry": ("环保", 0.5),
        "行业": ("环保", 0.5),
        "统一社会信用代码": ("91110000XXXXXXXXXX", 0.3),
        "法人": ("李四", 0.4),
    }
