"""Professional Document Learning Orchestrator.

NO new templates. NO new logic. Just orchestrates existing capabilities:
  - industrial_doc_engine.py (516行): batch gen, template versioning, approval, compliance, KB, cost
  - doc_engine.py (367行): DocEngine + Context-Folding
  - document_intelligence.py: read Excel, document processing
  - multimodal_parser.py: parse documents with descriptions
  - intelligent_kb.py: knowledge retrieval
  - selfplay_skill.py: skill discovery from context
  - capability_graph.py: register learned capabilities
  - context_biology.py: DNA/mutation for context artifacts
  - local folder analysis (routes.py): scan project folders
  - file operations (routes.py): read/write/exec

Flow: User selects folder → lifeform learns → generates using learned patterns.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class DocLearner:
    """Orchestrates existing capabilities for professional document learning."""

    async def learn_from_folder(self, folder_path: str, hub=None) -> dict:
        """Point the lifeform at a folder of reports → it learns.

        Uses existing: document_intelligence (Word/Excel), document_understanding
        (5-dim semantic analysis), industrial_doc_engine, multimodal_parser,
        selfplay_skill, capability_graph.
        """
        result = {"path": folder_path, "learned": {}, "started_at": time.time()}
        folder = Path(folder_path)
        if not folder.exists():
            return {"error": f"Folder not found: {folder_path}"}

        # Step 1: Scan + structural reading
        docs = await self._scan_documents(folder)
        result["documents_found"] = len(docs)

        # Step 2: DEEP semantic understanding (document_understanding.py)
        deep_analysis = await self._deep_understand(docs, hub)
        result["deep_analysis"] = deep_analysis

        # Step 3: Learn structure + terminology
        structures = await self._learn_structures(docs)
        terms = await self._extract_terminology(docs)

        # Step 4: Register in capability_graph
        registered = await self._register_capabilities(structures, terms)

        # Step 5: Persist all learned content into 6-layer memory
        persisted = await self._persist_learned(docs, structures, terms, deep_analysis)

        # Step 6: Build project KB
        kb_built = await self._build_project_kb(folder_path)

        result["learned"] = {
            "structures": len(structures),
            "terminology": len(terms),
            "capabilities": registered,
            "findings": deep_analysis.get("total_findings", 0),
        }
        result["persisted"] = persisted
        result["duration_ms"] = round((time.time() - result["started_at"]) * 1000)
        return result

    async def generate_from_learned(
        self, doc_type: str, project_data: dict, hub=None
    ) -> dict:
        """Generate a document using patterns learned from the folder.

        Uses existing: industrial_doc_engine (batch gen, approval, compliance),
        doc_engine (Context-Folding), capability_graph (learned patterns).
        """
        result = {"doc_type": doc_type, "started_at": time.time()}

        # Use industrial_doc_engine for batch generation with learned templates
        try:
            from livingtree.capability.industrial_doc_engine import (
                IndustrialBatchGenerator, ComplianceChecker, ApprovalWorkflow,
            )

            # Generate using learned patterns
            generator = IndustrialBatchGenerator()

            # Build params from project data
            params = self._build_params(doc_type, project_data)

            # Generate
            job = await generator.submit(
                template=doc_type,
                params=params,
            )
            result["job_id"] = job.id
            result["status"] = job.status.value

            # Check compliance (existing)
            if hub:
                checker = ComplianceChecker()
                issues = checker.check(job.result)
                result["compliance_issues"] = len(issues)

            # Start approval workflow (existing)
            workflow = ApprovalWorkflow()
            approval = workflow.submit(job.id, job.result)
            result["approval_stage"] = approval.current_stage

        except Exception as e:
            # Fallback: use doc_engine directly
            try:
                from livingtree.capability.doc_engine import DocEngine
                engine = DocEngine()
                report = await engine.generate_report(
                    template_type=doc_type,
                    data=project_data,
                    fold=True,
                )
                result["generated"] = True
                result["sections"] = len(report.get("sections", []))
            except Exception as e2:
                result["error"] = str(e2)

        result["duration_ms"] = round((time.time() - result["started_at"]) * 1000)
        return result

    # ── Internal: orchestrate existing modules ──

    async def _deep_understand(self, docs: list[dict], hub=None) -> dict:
        """Deep semantic understanding using document_understanding.py.

        Five-dimensional analysis per document:
          1. Section classification — what is each section for?
          2. Cross-section consistency — Ch3 data vs Ch5 conclusions?
          3. Regulatory gaps — missing GB standard references?
          4. Numeric validation — calculations correct? Limits exceeded?
          5. Expert recommendations — what to improve?
        """
        total_findings = 0
        all_issues = {"critical": 0, "warning": 0, "suggestion": 0}

        for doc in docs[:10]:  # Limit to 10 docs for performance
            filepath = str(Path(doc.get("_folder", ".")) / doc["path"])
            if not Path(filepath).exists():
                continue

            try:
                from .document_understanding import (
                    DocumentUnderstanding, FindingSeverity,
                )
                # Use hub's consciousness if available
                consciousness = getattr(
                    getattr(hub, 'world', None), 'consciousness', None
                ) if hub else None

                du = DocumentUnderstanding(consciousness=consciousness)
                analysis = await du.analyze(filepath)

                total_findings += len(analysis.findings)
                for f in analysis.findings:
                    if f.severity == FindingSeverity.CRITICAL:
                        all_issues["critical"] += 1
                    elif f.severity == FindingSeverity.WARNING:
                        all_issues["warning"] += 1
                    else:
                        all_issues["suggestion"] += 1

                # Feed findings to selfplay_skill for learning
                from ..dna.selfplay_skill import get_skill_discoverer
                discoverer = get_skill_discoverer()
                for f in analysis.findings[:5]:
                    discoverer.discover_from_context(
                        f"{f.severity.value}: {f.message} → {f.suggestion}",
                        source=filepath,
                    )

                logger.info(
                    f"DocLearner: understood {doc['path']} — "
                    f"{len(analysis.findings)} findings "
                    f"(critical={all_issues['critical']}, "
                    f"warn={all_issues['warning']}, "
                    f"suggestion={all_issues['suggestion']})"
                )

            except Exception as e:
                logger.debug(f"DocLearner: deep understand failed for {doc['path']}: {e}")

        return {
            "documents_analyzed": min(10, len(docs)),
            "total_findings": total_findings,
            "breakdown": all_issues,
        }

    async def _scan_documents(self, folder: Path) -> list[dict]:
        """Scan folder using existing multimodal_parser + document_intelligence."""
        docs = []
        supported = {".docx", ".doc", ".pdf", ".txt", ".md", ".xlsx", ".xls", ".html"}

        for f in folder.rglob("*"):
            if f.suffix.lower() in supported and f.is_file():
                try:
                    # Use existing document parser
                    from livingtree.capability.multimodal_parser import (
                        DocumentParser, ParsedDocument,
                    )
                    parser = DocumentParser()
                    parsed = await parser.parse_with_descriptions(str(f))
                    docs.append({
                        "path": str(f.relative_to(folder)),
                        "size": f.stat().st_size,
                        "type": f.suffix,
                        "parsed": parsed,
                    })
                except Exception:
                    # Read raw text
                    try:
                        content = f.read_text("utf-8")[:10000]
                        docs.append({
                            "path": str(f.relative_to(folder)),
                            "size": f.stat().st_size,
                            "type": f.suffix,
                            "text": content,
                        })
                    except Exception:
                        pass

        logger.info(f"DocLearner: scanned {len(docs)} documents in {folder}")
        return docs

    async def _learn_structures(self, docs: list[dict]) -> dict:
        """Extract document structures using existing selfplay_skill."""
        structures = {}
        from livingtree.dna.selfplay_skill import get_skill_discoverer
        discoverer = get_skill_discoverer()

        for doc in docs:
            text = doc.get("text", str(doc.get("parsed", "")))
            if not text:
                continue

            # Extract section headings as structural patterns
            sections = []
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("#") or (len(line) < 50 and (
                    "概述" in line or "总则" in line or "结论" in line or
                    "评价" in line or "分析" in line or "措施" in line or
                    "标准" in line or "依据" in line or "监测" in line
                )):
                    sections.append(line.lstrip("# ").strip())

            if sections:
                structures[doc["path"]] = sections

                # Feed to selfplay_skill for pattern discovery
                for section in sections[:10]:
                    discoverer.discover_from_context(
                        section, source=doc["path"],
                    )

        return structures

    async def _extract_terminology(self, docs: list[dict]) -> dict:
        """Extract domain terminology via existing capability_graph."""
        from livingtree.dna.capability_graph import get_capability_graph
        graph = get_capability_graph()

        terms = {}
        for doc in docs:
            text = doc.get("text", str(doc.get("parsed", "")))
            if not text:
                continue

            # Extract GB standard references
            import re
            gb_refs = re.findall(r'GB[/\s]?\d+[\.-]?\d*', text)
            if gb_refs:
                terms[doc["path"]] = {"gb_standards": list(set(gb_refs))}

                # Register as capabilities
                for gb in gb_refs[:5]:
                    graph.register_tool(
                        f"standard_{gb}",
                        f"GB标准 {gb}",
                    )

        return terms

    async def _register_capabilities(self, structures: dict, terms: dict) -> int:
        """Register learned patterns in capability_graph."""
        from livingtree.dna.capability_graph import get_capability_graph
        graph = get_capability_graph()

        count = 0
        for path, sections in structures.items():
            for section in sections[:5]:
                graph.register_skill(
                    f"doc_section_{section[:20]}",
                    f"文档章节模板: {section}",
                )
                count += 1

        return count

    async def _build_project_kb(self, folder_path: str) -> dict:
        """Build project knowledge base using existing industrial_doc_engine."""
        try:
            from livingtree.capability.industrial_doc_engine import (
                get_industrial_engine,
            )
            engine = get_industrial_engine()
            kb = engine.build_project_kb(folder_path)
            return {"built": True, "knowledge_nodes": len(kb) if kb else 0}
        except Exception as e:
            return {"built": False, "error": str(e)}

    @staticmethod
    def _build_params(doc_type: str, project_data: dict) -> dict:
        """Build generation params from project data."""
        return {
            "doc_type": doc_type,
            "project_name": project_data.get("name", ""),
            "project_location": project_data.get("location", ""),
            "project_scale": project_data.get("scale", ""),
            "applicable_standards": project_data.get("standards", []),
            "monitoring_data": project_data.get("monitoring", {}),
            **project_data,
        }

    # ── 6-Layer Memory Persistence ──

    async def _persist_learned(
        self, docs: list[dict], structures: dict, terms: dict, deep_analysis: dict
    ) -> dict:
        """Persist everything learned into the 6-layer memory system.

        Layer 1: document_kb.py — chunked full-text + vector hybrid
        Layer 2: engram_store.py — O(1) key facts
        Layer 3: knowledge_graph.py — entity relationships
        Layer 4: vector_store.py — FAISS embeddings
        Layer 5: struct_mem.py — PrecisionTier FULL findings
        Layer 6: capability_graph.py — terminology as capabilities
        """
        result = {f"layer{i}": 0 for i in range(1, 7)}

        # ── Layer 1: DocumentKB — chunked storage with FTS5 + embeddings ──
        try:
            from ..knowledge.document_kb import DocumentKB
            kb = DocumentKB()
            doc_count = 0
            for doc in docs:
                text = doc.get("text", str(doc.get("parsed", "")))
                if text:
                    kb.add_document(doc["path"], text)
                    doc_count += 1
            result["layer1"] = doc_count
        except Exception as e:
            logger.debug(f"DocLearner persist L1: {e}")

        # ── Layer 2: EngramStore — O(1) direct query facts ──
        try:
            from ..knowledge.engram_store import get_engram_store
            engram = get_engram_store(seed=False)
            fact_count = 0
            # Store key GB standards as engrams
            for doc_path, doc_terms in terms.items():
                for gb in doc_terms.get("gb_standards", []):
                    engram.insert(f"standard:{gb}", gb, category="regulatory")
                    fact_count += 1
            # Store section structures
            for path, sections in structures.items():
                for s in sections[:3]:
                    engram.insert(f"section:{s[:30]}", s, category="structure")
                    fact_count += 1
            result["layer2"] = fact_count
        except Exception as e:
            logger.debug(f"DocLearner persist L2: {e}")

        # ── Layer 3: KnowledgeGraph — entity relationships ──
        try:
            from ..knowledge.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph()
            edge_count = 0
            for path, sections in structures.items():
                for i in range(len(sections) - 1):
                    kg.add_edge(sections[i][:50], sections[i+1][:50],
                               relation="followed_by")
                    edge_count += 1
            result["layer3"] = edge_count
        except Exception as e:
            logger.debug(f"DocLearner persist L3: {e}")

        # ── Layer 4: VectorStore — FAISS embeddings ──
        try:
            from ..knowledge.vector_store import VectorStore
            vs = VectorStore()
            vec_count = 0
            for path, sections in structures.items():
                for s in sections[:5]:
                    vs.add(s, metadata={"source": path, "type": "document_section"})
                    vec_count += 1
            result["layer4"] = vec_count
        except Exception as e:
            logger.debug(f"DocLearner persist L4: {e}")

        # ── Layer 5: StructMem — FULL precision findings ──
        try:
            from ..knowledge.struct_mem import get_struct_mem, EventEntry
            mem = get_struct_mem()
            finding_count = 0
            for doc in docs[:5]:
                text = doc.get("text", str(doc.get("parsed", "")))
                if text and len(text) > 100:
                    entry = EventEntry(
                        id=f"doc_{doc['path']}",
                        session_id="doc_learner",
                        role="system",
                        content=f"Learned from {doc['path']}: {text[:500]}",
                    )
                    mem._buffer.add(entry)
                    finding_count += 1
            result["layer5"] = finding_count
        except Exception as e:
            logger.debug(f"DocLearner persist L5: {e}")

        # ── Layer 6: CapabilityGraph — terminology + GB standards ──
        try:
            from ..dna.capability_graph import get_capability_graph
            graph = get_capability_graph()
            cap_count = 0
            for doc_path, doc_terms in terms.items():
                for gb in doc_terms.get("gb_standards", []):
                    graph.register_tool(
                        f"standard_{gb.replace('/', '_')}",
                        f"国家标准 {gb}",
                    )
                    cap_count += 1
            result["layer6"] = cap_count
        except Exception as e:
            logger.debug(f"DocLearner persist L6: {e}")

        total = sum(result.values())
        logger.info(f"DocLearner: persisted {total} items across 6 memory layers")
        return result
        """Build generation params from project data."""
        return {
            "doc_type": doc_type,
            "project_name": project_data.get("name", ""),
            "project_location": project_data.get("location", ""),
            "project_scale": project_data.get("scale", ""),
            "applicable_standards": project_data.get("standards", []),
            "monitoring_data": project_data.get("monitoring", {}),
            **project_data,
        }


# ── Singleton ──

_learner: Optional[DocLearner] = None


def get_doc_learner() -> DocLearner:
    global _learner
    if _learner is None:
        _learner = DocLearner()
    return _learner
