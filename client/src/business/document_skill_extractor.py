"""
DocumentSkillExtractor - document to Skill auto-extractor (generic, semantic analysis version)

Functionality:
1. Accepts any document type (notification/bulletin/expert opinion/report/email...)
2. Uses LLM semantic analysis to extract:
   - Document type (auto-detected, not hard-coded)
   - Core checking rules
   - Output template
   - Trigger semantic descriptions (for embedding matching)
3. Auto-generates SKILL.md file
4. Computes document embedding and saves it

Usage:
    from client.src.business.document_skill_extractor import DocumentSkillExtractor

    extractor = DocumentSkillExtractor()
    skill_path = extractor.extract_skill(
        document_text="notification text...",
        skill_name="meeting-notice-check-expert",
        save_dir=".livingtree/skills/meeting-notice-expert"
    )

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import requests

from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
from loguru import logger


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
SIMILARITY_THRESHOLD = 0.75


# --------------------------------------------------------------------------- #
# DocumentSkillExtractor
# --------------------------------------------------------------------------- #

class DocumentSkillExtractor:
    """
    Auto-extract Skill from any document (generic, semantic-analysis-based).

    Workflow:
    1. LLM semantic analysis of document -> extract structure, rules, template
    2. Generate SKILL.md (compatible with existing Skill format)
    3. Compute document embedding -> save to embedding.json
    4. Return skill directory path
    """

    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        self._router = GlobalModelRouter()
        self._ollama_url = ollama_url.rstrip("/")
        self._embedding_model = embedding_model

    # ==================================================================== #
    # Public interface
    # ==================================================================== #

    def extract_skill(
        self,
        document_text: str,
        skill_name: str,
        save_dir: str,
        description: str = "",
        extra_triggers: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Extract Skill from document and save.

        Args:
            document_text:  Original document text
            skill_name:     Skill name (e.g. "meeting-notice-check-expert")
            save_dir:      Save directory (relative to project root)
            description:   Skill trigger description (optional, LLM auto-generates)
            extra_triggers: Extra semantic trigger sentences (optional)

        Returns:
            (success: bool, message: str)
            message = skill directory path on success
        """
        # 1. LLM semantic analysis
        logger.info(f"[DocumentSkillExtractor] Start analyzing document -> {skill_name}")
        analysis = self._analyze_document_with_llm(document_text, skill_name)

        if not analysis:
            return False, "LLM analysis failed, please check if Ollama is running"

        # 2. Generate SKILL.md content
        skill_md = self._build_skill_markdown(
            skill_name=skill_name,
            analysis=analysis,
            document_text=document_text,
            description=description or analysis.get("auto_description", ""),
            extra_triggers=extra_triggers or [],
        )

        # 3. Save files
        abs_dir = self._resolve_path(save_dir)
        os.makedirs(abs_dir, exist_ok=True)

        skill_md_path = os.path.join(abs_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(skill_md)

        logger.info(f"[DocumentSkillExtractor] SKILL.md saved: {skill_md_path}")

        # 4. Compute and save embedding
        embedding = self._get_embedding(document_text[:2000])
        if embedding:
            embedding_path = os.path.join(abs_dir, "embedding.json")
            with open(embedding_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "model": self._embedding_model,
                        "embedding": embedding,
                        "triggers": analysis.get("semantic_triggers", []),
                        "document_sample": document_text[:500],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"[DocumentSkillExtractor] embedding saved: {embedding_path}")
        else:
            logger.warning("[DocumentSkillExtractor] embedding computation failed, skipped")

        return True, abs_dir

    def analyze_only(self, document_text: str, skill_name: str) -> Dict:
        """
        Analyze document only, do not save (for preview).

        Returns:
            Analysis result dict
        """
        return self._analyze_document_with_llm(document_text, skill_name)

    # ==================================================================== #
    # Internal method: LLM semantic analysis
    # ==================================================================== #

    def _analyze_document_with_llm(self, document_text: str, skill_name: str) -> Dict:
        """
        Use LLM to semantically analyze document and extract Skill core elements.

        Returns dict containing:
        - document_type:     document type (LLM auto-detected)
        - core_rules:       core checking rules (list)
        - output_template:  output template (string)
        - workflow:         workflow (list)
        - faq:             faq (list)
        - semantic_triggers: semantic trigger sentences (list, for embedding matching)
        - auto_description: auto-generated trigger description
        """
        prompt = self._build_analysis_prompt(document_text, skill_name)

        try:
            response = self._router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2,
            )

            # Try to parse JSON
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                # Non-JSON response, use text parsing fallback
                return self._parse_text_analysis(response, document_text)

        except Exception as e:
            logger.error(f"[DocumentSkillExtractor] LLM analysis failed: {e}")
            return {}

    def _build_analysis_prompt(self, document_text: str, skill_name: str) -> str:
        """Build LLM semantic analysis prompt"""
        example = {
            "document_type": "document type name (auto-detected)",
            "core_rules": ["rule 1", "rule 2", "..."],
            "output_template": "output template (Markdown format)",
            "workflow": ["step 1", "step 2", "..."],
            "faq": [{"q": "question", "a": "answer"}, "..."],
            "semantic_triggers": [
                "semantic trigger sentence 1 (user's possible question/need, for embedding matching)",
                "semantic trigger sentence 2",
                "semantic trigger sentence 3",
            ],
            "auto_description": "One-sentence description: trigger this Skill when user has X need",
        }

        parts = [
            "You are a professional document analysis expert. Please perform deep semantic analysis on the document below,",
            "and extract the core elements that can be used to build an 'Expert Skill'.",
            "",
            "[Requirements]",
            "1. Auto-detect document type (do NOT hard-code, judge based on content)",
            "2. Extract core checking rules from the document (i.e. what to check, how to check)",
            "3. Extract document output template (i.e. standard output format for this type of document)",
            "4. Generate semantic trigger sentences (3~5 sentences, used for embedding similarity matching later)",
            "",
            "[Output format (strict JSON)]",
            json.dumps(example, ensure_ascii=False, indent=2),
            "",
            "[Document to analyze]",
            document_text[:3000],
            "",
            "Please output ONLY the JSON, do NOT output any other content.",
        ]
        return "\n".join(parts)

    def _parse_text_analysis(self, response: str, document_text: str) -> Dict:
        """Fallback text parsing when LLM does not return JSON"""
        return {
            "document_type": "generic document",
            "core_rules": ["check document completeness", "check format specification"],
            "output_template": "# Document Analysis Report\n\n[content]\n",
            "workflow": ["read document", "analyze structure", "output conclusion"],
            "faq": [],
            "semantic_triggers": [
                document_text[:100],
                "please help me check this document",
                "please analyze this file",
            ],
            "auto_description": f"Trigger when user provides a document similar to '{document_text[:30]}...'",
        }

    # ==================================================================== #
    # Internal method: Build SKILL.md
    # ==================================================================== #

    def _build_skill_markdown(
        self,
        skill_name: str,
        analysis: Dict,
        document_text: str,
        description: str,
        extra_triggers: List[str],
    ) -> str:
        """
        Build SKILL.md content based on LLM analysis result.

        SKILL.md format is compatible with existing .livingtree/skills/ expert role files.
        """
        doc_type = analysis.get("document_type", "generic document")
        core_rules = analysis.get("core_rules", [])
        output_tpl = analysis.get("output_template", "")
        workflow = analysis.get("workflow", [])
        faq = analysis.get("faq", [])
        triggers = analysis.get("semantic_triggers", []) + extra_triggers
        auto_desc = description or analysis.get("auto_description", "")

        if not auto_desc:
            auto_desc = f"Trigger when user provides {doc_type} type documents for checking"

        lines = []
        # --- YAML frontmatter ---
        lines.append("---")
        lines.append(f"name: {skill_name}")
        lines.append(f"description: {auto_desc}")
        lines.append(f"location: {triggers[0] if triggers else 'auto-generated'}")
        lines.append(f"document_type: {doc_type}")
        lines.append(f"created_at: {self._now_iso()}")
        lines.append("---")
        lines.append("")

        # --- Body ---
        lines.append(f"# {skill_name}")
        lines.append("")
        lines.append(f"I am {skill_name}, specializing in deep analysis and checking of {doc_type}.")
        lines.append("")

        # Core capabilities
        if core_rules:
            lines.append("## Core Checking Rules")
            lines.append("")
            for i, rule in enumerate(core_rules, 1):
                lines.append(f"{i}. {rule}")
            lines.append("")

        # Workflow
        if workflow:
            lines.append("## Workflow")
            lines.append("")
            for i, step in enumerate(workflow, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        # Output template
        if output_tpl:
            lines.append("## Output Template")
            lines.append("")
            lines.append("```")
            lines.append(output_tpl)
            lines.append("```")
            lines.append("")

        # FAQ
        if faq:
            lines.append("## FAQ")
            lines.append("")
            for item in faq:
                lines.append(f"**Q: {item.get('q', '')}**")
                lines.append(f"A: {item.get('a', '')}")
                lines.append("")

        # Semantic trigger sentences (for system auto-matching)
        if triggers:
            lines.append("## Semantic Trigger Sentences (system auto-use, DO NOT modify)")
            lines.append("")
            for t in triggers:
                lines.append(f"- {t}")
            lines.append("")

        # Usage instructions
        lines.append("## Usage Instructions")
        lines.append("")
        lines.append(f"1. Provide {doc_type} related documents")
        lines.append("2. Describe your checking or analysis needs")
        lines.append("3. I will provide professional opinions based on extracted rules")
        lines.append("")
        lines.append("---")
        lines.append(f"*This Skill was auto-generated from document extraction, document type: **{doc_type}***")
        lines.append("")

        return "\n".join(lines)

    # ==================================================================== #
    # Internal method: Embedding computation (local Ollama)
    # ==================================================================== #

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Call Ollama Embedding API to compute text vector.

        API: POST http://localhost:11434/api/embeddings
        """
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": self._embedding_model, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if embedding:
                logger.info(f"[DocumentSkillExtractor] embedding computed successfully (dimension: {len(embedding)})")
                return embedding
            else:
                logger.warning(f"[DocumentSkillExtractor] embedding is empty: {data}")
                return None
        except Exception as e:
            logger.error(f"[DocumentSkillExtractor] embedding computation failed: {e}")
            return None

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ==================================================================== #
    # Utilities
    # ==================================================================== #

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _resolve_path(self, path: str) -> str:
        """Resolve path: relative to project root -> absolute path"""
        if os.path.isabs(path):
            return path
        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        return os.path.join(base, path)


# --------------------------------------------------------------------------- #
# Convenience functions
# --------------------------------------------------------------------------- #

def extract_skill_from_document(
    document_text: str,
    skill_name: str,
    save_dir: str,
) -> Tuple[bool, str]:
    """
    Convenience function: extract Skill from document.

    Args:
        document_text: Original document text
        skill_name:    Skill name
        save_dir:      Save directory (relative to project root)

    Returns:
        (success, message)
    """
    extractor = DocumentSkillExtractor()
    return extractor.extract_skill(document_text, skill_name, save_dir)
