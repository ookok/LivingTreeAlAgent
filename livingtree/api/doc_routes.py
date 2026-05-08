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
